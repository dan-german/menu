#!/usr/bin/env python3
"""Validate the milestone 2 messy-menu evaluation set."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from build_messy_eval_set import CORRUPTION_TYPES, flatten_items
from utils import (
    CATEGORY_TAXONOMY,
    EVAL_TOTAL_ITEMS,
    MESSY_SET_PATH,
    RAW_MENUS_PATH,
    read_json,
)


REQUIRED_FIELDS = {
    "item_id",
    "source_cuisine",
    "restaurant",
    "restaurant_id",
    "category_source",
    "raw_item_index",
    "original_item",
    "messy_item",
    "normalized_category",
    "applied_corruptions",
}
DIFFERENCE_THRESHOLD = 0.9


def validate_eval_set(
    eval_items: list[dict[str, Any]], raw_items: list[dict[str, Any]], expected: int
) -> list[str]:
    errors: list[str] = []
    if len(eval_items) != expected:
        errors.append(f"expected {expected} items, found {len(eval_items)}")

    raw_lookup = {item["item_id"]: item for item in raw_items}
    changed = 0
    for index, item in enumerate(eval_items):
        label = item.get("item_id", f"item at index {index}")
        missing = REQUIRED_FIELDS - set(item)
        if missing:
            errors.append(f"{label}: missing fields {sorted(missing)}")
            continue

        source = raw_lookup.get(item["item_id"])
        if source is None:
            errors.append(f"{label}: item_id does not exist in raw menus")
            continue
        for field in (
            "source_cuisine",
            "restaurant",
            "restaurant_id",
            "category_source",
            "raw_item_index",
            "original_item",
        ):
            if item[field] != source[field]:
                errors.append(f"{label}: {field} drifted from raw data")

        original = item["original_item"]
        messy = item["messy_item"]
        if not isinstance(messy, dict) or set(messy) != {"name", "description", "price"}:
            errors.append(f"{label}: messy_item must contain name, description, and price")
            continue
        if not isinstance(messy["name"], str) or not messy["name"].strip():
            errors.append(f"{label}: messy name must be a non-empty string")
        if not isinstance(messy["description"], str):
            errors.append(f"{label}: messy description must be a string")
        if messy["price"] != original["price"]:
            errors.append(f"{label}: messy price must preserve the original numeric price")
        if messy["name"] != original["name"] or messy["description"] != original["description"]:
            changed += 1
        else:
            errors.append(f"{label}: messy item is identical to the original item")

        if item["normalized_category"] not in CATEGORY_TAXONOMY:
            errors.append(
                f"{label}: invalid normalized_category "
                f"{item['normalized_category']!r}"
            )
        applied_corruptions = item["applied_corruptions"]
        if not isinstance(applied_corruptions, list) or not applied_corruptions:
            errors.append(f"{label}: applied_corruptions must be a non-empty list")
        else:
            invalid_corruptions = sorted(
                set(applied_corruptions) - set(CORRUPTION_TYPES)
            )
            if invalid_corruptions:
                errors.append(f"{label}: invalid corruption labels {invalid_corruptions}")
            if len(applied_corruptions) != len(set(applied_corruptions)):
                errors.append(
                    f"{label}: applied_corruptions must not contain duplicates"
                )
            if (
                not original["description"]
                and "dropped_description" in applied_corruptions
            ):
                errors.append(
                    f"{label}: cannot drop an already-empty original description"
                )

    if eval_items and changed / len(eval_items) < DIFFERENCE_THRESHOLD:
        errors.append(
            f"only {changed}/{len(eval_items)} items differ from original inputs; "
            f"expected at least {DIFFERENCE_THRESHOLD:.0%}"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_MENUS_PATH)
    parser.add_argument("--messy-set", type=Path, default=MESSY_SET_PATH)
    parser.add_argument("--expected", type=int, default=EVAL_TOTAL_ITEMS)
    args = parser.parse_args()

    raw_items = flatten_items(read_json(args.raw))
    eval_items = read_json(args.messy_set)
    if not isinstance(eval_items, list):
        print("ERROR: eval set must be a JSON array")
        return 1
    errors = validate_eval_set(eval_items, raw_items, args.expected)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Validated {len(eval_items)} eval items from {args.messy_set}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
