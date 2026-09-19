#!/usr/bin/env python3
"""Build the milestone 2 messy-menu evaluation set."""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any

from utils import (
    CATEGORY_TAXONOMY,
    EVAL_SAMPLE_SEED,
    EVAL_SPOTCHECK_ITEMS,
    EVAL_SPOTCHECK_PATH,
    EVAL_TOTAL_ITEMS,
    MESSY_SET_PATH,
    RAW_MENUS_PATH,
    call_gemini_json,
    read_json,
    write_json,
)


LABEL_BATCH_SIZE = 20
MAX_ATTEMPTS = 3
CORRUPTION_TYPES = (
    "typo",
    "inconsistent_casing",
    "abbreviation",
    "dropped_description",
    "garbled_description",
    "punctuation_noise",
    "spacing_noise",
    "wrong grammar"
)

LABEL_RESPONSE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "messy_name": {"type": "string"},
            "messy_description": {"type": "string"},
            "category": {"type": "string", "enum": list(CATEGORY_TAXONOMY)},
            "applied_corruptions": {
                "type": "array",
                "items": {"type": "string", "enum": list(CORRUPTION_TYPES)},
            },
        },
        "required": [
            "messy_name",
            "messy_description",
            "category",
            "applied_corruptions",
        ],
        "additionalProperties": False,
    },
}


def flatten_items(menus: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Flatten top-level items while retaining their source coordinates."""
    flattened: list[dict[str, Any]] = []
    for cuisine, restaurants in menus.items():
        for restaurant in restaurants:
            raw_item_index = 0
            for category in restaurant.get("categories", []):
                for source_item in category.get("items", []):
                    flattened.append(
                        {
                            "item_id": source_item["id"],
                            "source_cuisine": cuisine,
                            "restaurant": restaurant["name"],
                            "restaurant_id": restaurant["id"],
                            "category_source": category["name"],
                            "raw_item_index": raw_item_index,
                            "original_item": {
                                "name": source_item["name"],
                                "description": source_item.get("description") or "",
                            },
                        }
                    )
                    raw_item_index += 1
    return flattened


def sample_items(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if not 1 <= limit <= len(items):
        raise ValueError(f"limit must be between 1 and {len(items)}")

    by_restaurant: dict[int, list[dict[str, Any]]] = {}
    for item in items:
        by_restaurant.setdefault(item["restaurant_id"], []).append(item)

    rng = random.Random(EVAL_SAMPLE_SEED)
    groups = list(by_restaurant.values())

    for group in groups:
        rng.shuffle(group)

    sampled = [item for round_items in zip(*groups) for item in round_items]

    if len(sampled) < limit:
        raise ValueError(
            "limit requires more items than the smallest menu provides")

    return sorted(sampled[:limit], key=lambda item: item["item_id"])


def build_prompt(items: list[dict[str, Any]]) -> str:
    prompt_items = [
        {
            "item_id": item["item_id"],
            "source_cuisine": item["source_cuisine"],
            "restaurant": item["restaurant"],
            "category_source": item["category_source"],
            **item["original_item"],
        }
        for item in items
    ]
    return f"""Create messy evaluation inputs and normalized categories for menu items.

Return exactly one object for every input item, in the same order.

Messy-input rules:
- Preserve the dish identity. Do not translate it or replace it with another dish.
- Apply 1-3 realistic corruptions from: {list(CORRUPTION_TYPES)}.
- messy_name and messy_description must differ from the original name. Prefer plausible typos, casing, spacing,
  punctuation, or common abbreviations; keep it recognizable.
- applied_corruptions must list only transformations actually applied.

Category rules:
- category must be exactly one value from: {list(CATEGORY_TAXONOMY)}.
- Map category_source to the closest normalized category, using the item name and
  description to resolve vague or promotional source categories.

Items:
{json.dumps(prompt_items, indent=2, ensure_ascii=True)}
"""


def call_batch(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = call_gemini_json(prompt=build_prompt(
                batch), schema=LABEL_RESPONSE_SCHEMA)
            if not isinstance(result, list):
                raise ValueError("Gemini response was not an array")
            if len(result) != len(batch):
                raise ValueError(
                    f"Gemini returned {len(result)} items for a batch of {len(batch)}"
                )
            return result
        except Exception:
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(2 ** (attempt - 1))
    raise AssertionError("unreachable")


def assemble_item(source: dict[str, Any], label: dict[str, Any]) -> dict[str, Any]:
    messy_name = label["messy_name"]
    corruptions = list(dict.fromkeys(label["applied_corruptions"]))
    if messy_name == source["original_item"]["name"]:
        messy_name = _change_name_casing(messy_name)
        corruptions = [
            corruption for corruption in corruptions if corruption != "typo"
        ]
        if "inconsistent_casing" not in corruptions:
            corruptions.append("inconsistent_casing")
    if not source["original_item"]["description"]:
        corruptions = [
            corruption
            for corruption in corruptions
            if corruption != "dropped_description"
        ]
    if not corruptions:
        corruptions = ["abbreviation"]
    return {
        **source,
        "messy_item": {
            "name": messy_name,
            "description": label["messy_description"],
        },
        "normalized_category": label["category"],
        "applied_corruptions": corruptions,
    }


def _change_name_casing(name: str) -> str:
    for index, character in enumerate(name):
        if character.isalpha():
            replacement = character.lower() if character.isupper() else character.upper()
            return name[:index] + replacement + name[index + 1:]
    return name + " "


def reusable_output(path: Path, sampled: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    existing = read_json(path)
    if not isinstance(existing, list):
        return None
    expected_ids = [item["item_id"] for item in sampled]
    if [item.get("item_id") for item in existing] != expected_ids:
        return None
    required = {
        "original_item",
        "messy_item",
        "normalized_category",
        "applied_corruptions",
    }
    if not all(required <= set(item) for item in existing):
        return None
    return existing


def print_distribution(items: list[dict[str, Any]]) -> None:
    cuisines = Counter(item["source_cuisine"] for item in items)
    restaurants = Counter(item["restaurant_id"] for item in items)
    print(f"Selected {len(items)} primary items")
    print("By cuisine: " +
          ", ".join(f"{key}={value}" for key, value in sorted(cuisines.items())))
    count_range = (min(restaurants.values()), max(restaurants.values()))
    print(
        f"Across {len(restaurants)} restaurants: {count_range[0]}-{count_range[1]} items each")


def write_spotcheck(items: list[dict[str, Any]], path: Path) -> None:
    rng = random.Random(EVAL_SAMPLE_SEED)
    write_json(path, rng.sample(items, min(EVAL_SPOTCHECK_ITEMS, len(items))))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="regenerate even when output is complete")
    args = parser.parse_args()

    sampled = sample_items(
        flatten_items(read_json(RAW_MENUS_PATH)), EVAL_TOTAL_ITEMS
    )
    print_distribution(sampled)

    if not args.force and (
        existing := reusable_output(MESSY_SET_PATH, sampled)
    ) is not None:
        write_spotcheck(existing, EVAL_SPOTCHECK_PATH)
        print(f"Reused complete eval set at {MESSY_SET_PATH}")
        print(f"Wrote spot-check sample to {EVAL_SPOTCHECK_PATH}")
        return 0

    completed: list[dict[str, Any]] = []
    for start in range(0, len(sampled), LABEL_BATCH_SIZE):
        batch = sampled[start: start + LABEL_BATCH_SIZE]
        labels = call_batch(batch)
        completed.extend(
            assemble_item(item, label) for item, label in zip(batch, labels)
        )
        print(f"Generated {len(completed)}/{len(sampled)} items")

    write_json(MESSY_SET_PATH, completed)
    write_spotcheck(completed, EVAL_SPOTCHECK_PATH)
    print(f"Wrote eval set to {MESSY_SET_PATH}")
    print(f"Wrote spot-check sample to {EVAL_SPOTCHECK_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
