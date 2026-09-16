#!/usr/bin/env python3
"""Validate the milestone 2 evaluation set."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from utils import (
    DIETARY_TAGS,
    EVAL_ITEMS_PER_RESTAURANT,
    EVAL_TOTAL_ITEMS,
    RAW_MENUS_PATH,
    ROOT,
    item_id,
    read_json,
)


EVAL_SET_PATH = ROOT / "eval" / "eval_set.json"

REQUIRED_FIELDS = {
    "item_id",
    "restaurant_id",
    "restaurant",
    "raw_item_index",
    "item_name",
    "description",
    "price",
    "source_cuisine",
    "normalized_name",
    "normalized_description",
    "category",
    "cuisine_tags",
    "dietary_tags",
    "ingredients",
}


def build_raw_lookup(menus: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup = {}
    for restaurant_index, menu in enumerate(menus):
        restaurant_id = f"r{restaurant_index + 1:03d}"
        for item_index, item in enumerate(menu["items"]):
            raw_item_id = item_id(restaurant_index, item_index)
            lookup[raw_item_id] = {
                "item_id": raw_item_id,
                "restaurant_id": restaurant_id,
                "restaurant": menu["restaurant"],
                "raw_item_index": item_index,
                "item_name": item["item_name"],
                "description": item["description"],
                "price": item["price"],
                "source_cuisine": menu["cuisine"],
            }
    return lookup


def validate_eval_set(eval_items: list[dict[str, Any]], raw_lookup: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if len(eval_items) != EVAL_TOTAL_ITEMS:
        errors.append(f"expected {EVAL_TOTAL_ITEMS} items, found {len(eval_items)}")

    item_ids = [item.get("item_id") for item in eval_items]
    duplicate_item_ids = [item_id for item_id, count in Counter(item_ids).items() if count > 1]
    if duplicate_item_ids:
        errors.append(f"duplicate item_ids: {duplicate_item_ids}")

    restaurant_counts = Counter(item.get("restaurant_id") for item in eval_items)
    for restaurant_id, count in sorted(restaurant_counts.items()):
        if count != EVAL_ITEMS_PER_RESTAURANT:
            errors.append(
                f"{restaurant_id}: expected {EVAL_ITEMS_PER_RESTAURANT} items, found {count}"
            )

    if len(restaurant_counts) != EVAL_TOTAL_ITEMS // EVAL_ITEMS_PER_RESTAURANT:
        errors.append(f"expected 20 restaurants, found {len(restaurant_counts)}")

    for index, item in enumerate(eval_items):
        item_label = item.get("item_id", f"item at index {index}")
        missing_fields = REQUIRED_FIELDS - set(item)
        if missing_fields:
            errors.append(f"{item_label}: missing fields {sorted(missing_fields)}")
            continue

        raw_item = raw_lookup.get(item["item_id"])
        if raw_item is None:
            errors.append(f"{item_label}: item_id does not exist in raw menus")
            continue

        for field, expected_value in raw_item.items():
            if item[field] != expected_value:
                errors.append(
                    f"{item_label}: {field} drifted from raw data "
                    f"(expected {expected_value!r}, found {item[field]!r})"
                )

        if not isinstance(item["price"], (int, float)) or isinstance(item["price"], bool):
            errors.append(f"{item_label}: price must be a number")
        if not isinstance(item["normalized_name"], str) or not item["normalized_name"].strip():
            errors.append(f"{item_label}: normalized_name must be a non-empty string")
        if not isinstance(item["normalized_description"], str):
            errors.append(f"{item_label}: normalized_description must be a string")
        if not isinstance(item["category"], str) or not item["category"].strip():
            errors.append(f"{item_label}: category must be a non-empty string")
        if not isinstance(item["cuisine_tags"], list) or not item["cuisine_tags"]:
            errors.append(f"{item_label}: cuisine_tags must be a non-empty list")
        elif not all(isinstance(tag, str) and tag.strip() for tag in item["cuisine_tags"]):
            errors.append(f"{item_label}: cuisine_tags must contain non-empty strings")

        dietary_tags = item["dietary_tags"]
        if not isinstance(dietary_tags, list):
            errors.append(f"{item_label}: dietary_tags must be a list")
        else:
            invalid_tags = sorted(set(dietary_tags) - set(DIETARY_TAGS))
            if invalid_tags:
                errors.append(f"{item_label}: invalid dietary_tags {invalid_tags}")

        ingredients = item["ingredients"]
        if not isinstance(ingredients, list) or not ingredients:
            errors.append(f"{item_label}: ingredients must be a non-empty list")
        else:
            for ingredient in ingredients:
                if not isinstance(ingredient, str) or not ingredient:
                    errors.append(f"{item_label}: ingredients must contain non-empty strings")
                elif ingredient != ingredient.strip() or ingredient != ingredient.lower():
                    errors.append(f"{item_label}: ingredient must be lowercase and trimmed: {ingredient!r}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_MENUS_PATH)
    parser.add_argument("--eval", type=Path, default=EVAL_SET_PATH)
    args = parser.parse_args()

    raw_menus = read_json(args.raw)
    eval_items = read_json(args.eval)
    errors = validate_eval_set(eval_items, build_raw_lookup(raw_menus))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"Validated {len(eval_items)} eval items from {args.eval}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
