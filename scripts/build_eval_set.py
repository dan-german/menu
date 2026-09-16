#!/usr/bin/env python3
"""Build the milestone 2 evaluation set from raw synthetic menus."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from utils import (
    DIETARY_TAGS,
    EVAL_ITEMS_PER_RESTAURANT,
    EVAL_SAMPLE_SEED,
    RAW_MENUS_PATH,
    ROOT,
    call_gemini_json,
    item_id,
    read_json,
    write_json,
)


EVAL_OUTPUT_PATH = ROOT / "eval" / "eval_set.json"

LABEL_BATCH_SIZE = 20

LABEL_RESPONSE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "item_id": {"type": "string"},
            "normalized_name": {"type": "string"},
            "normalized_description": {"type": "string"},
            "category": {"type": "string"},
            "cuisine_tags": {"type": "array", "items": {"type": "string"}},
            "dietary_tags": {"type": "array", "items": {"type": "string"}},
            "ingredients": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "item_id",
            "normalized_name",
            "normalized_description",
            "category",
            "cuisine_tags",
            "dietary_tags",
            "ingredients",
        ],
        "additionalProperties": False,
    },
}


def sample_items(menus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rng = random.Random(EVAL_SAMPLE_SEED)
    sampled: list[dict[str, Any]] = []
    for restaurant_index, menu in enumerate(menus):
        chosen_indexes = sorted(
            rng.sample(range(len(menu["items"])), EVAL_ITEMS_PER_RESTAURANT)
        )
        for item_index in chosen_indexes:
            raw_item = menu["items"][item_index]
            sampled.append(
                {
                    "item_id": item_id(restaurant_index, item_index),
                    "restaurant_id": f"r{restaurant_index + 1:03d}",
                    "restaurant": menu["restaurant"],
                    "raw_item_index": item_index,
                    "item_name": raw_item["item_name"],
                    "description": raw_item["description"],
                    "price": raw_item["price"],
                    "source_cuisine": menu["cuisine"],
                }
            )
    return sampled


def build_label_prompt(items: list[dict[str, Any]]) -> str:
    return f"""Create gold evaluation labels for these raw restaurant menu items.

Return exactly one JSON array element per input item_id.

Rules:
- normalized_name: corrected display name, preserving dish identity.
- normalized_description: clean one-sentence menu description. Expand abbreviations and infer only obvious missing context from the item name and restaurant cuisine. Use an empty string only when the item is genuinely unknowable.
- category: short category such as Curry, Taco, Ramen, Dessert, Beverage, Appetizer, Sandwich, Bowl, Noodles, Rice Dish, Pizza, Salad, or Entree.
- cuisine_tags: one or more cuisine labels. Include Fusion when appropriate.
- dietary_tags: only use values from this list: {list(DIETARY_TAGS)}. Use unknown only when the menu text is too vague.
- ingredients: likely core ingredients only, lowercase strings, no quantities, no preparation steps. Ingredients must never be empty; use ["unknown"] only for truly vague items like Chef's Special.

Items:
{json.dumps(items, indent=2, ensure_ascii=True)}
"""


def label_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected_ids = {item["item_id"] for item in items}
    labels_by_id: dict[str, dict[str, Any]] = {}
    for start in range(0, len(items), LABEL_BATCH_SIZE):
        batch = items[start: start + LABEL_BATCH_SIZE]
        batch_ids = {item["item_id"] for item in batch}
        label_batch = call_gemini_json(
            prompt=build_label_prompt(batch),
            schema=LABEL_RESPONSE_SCHEMA)
        for label in label_batch:
            returned_id = label["item_id"]
            if returned_id not in batch_ids:
                raise RuntimeError(
                    f"Gemini returned unexpected item_id: {returned_id}")
            if returned_id in labels_by_id:
                raise RuntimeError(
                    f"Gemini returned duplicate item_id: {returned_id}")
            labels_by_id[returned_id] = label

    missing = sorted(expected_ids - set(labels_by_id))
    if missing:
        raise RuntimeError(f"Gemini did not label item_ids: {missing}")

    return [
        {
            **item,
            **labels_by_id[item["item_id"]],
        }
        for item in items
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_MENUS_PATH)
    parser.add_argument("--output", type=Path, default=EVAL_OUTPUT_PATH)
    args = parser.parse_args()

    sampled_items = sample_items(read_json(args.raw))
    labeled_items = label_items(sampled_items)
    write_json(args.output, labeled_items)
    print(f"Wrote {len(labeled_items)} eval items to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
