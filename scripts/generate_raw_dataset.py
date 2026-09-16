#!/usr/bin/env python3
"""Generate raw synthetic restaurant menus with the Google Gemini API."""

from __future__ import annotations

import json
from typing import Any

from utils import GEMINI_MODEL, ROOT, call_gemini_json, normalize_key, write_json


PROMPT_PATH = ROOT / "prompts" / "raw_dataset_generation.md"
MENU_OUTPUT_PATH = ROOT / "data" / "raw" / "synthetic_menus.json"
SUMMARY_PATH = ROOT / "data" / "raw" / "summary.json"
RESTAURANTS_PER_CUISINE = 2
ITEMS_PER_MENU = 20

MENU_REQUIRED_FIELDS = {"restaurant", "items"}
ITEM_REQUIRED_FIELDS = {"item_name", "description", "price"}
AMBIGUOUS_NAME_MARKERS = [
    "chef s special",
    "house special",
    "house bowl",
    "combo plate",
    "lunch special",
]
RESPONSE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "restaurant": {"type": "string"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_name": {"type": "string"},
                        "description": {"type": "string"},
                        "price": {"type": "number"},
                    },
                    "required": ["item_name", "description", "price"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["restaurant", "items"],
        "additionalProperties": False,
    },
}
CUISINES = [
    "Indian",
    "Mexican",
    "Thai",
    "Japanese",
    "Chinese",
    "Italian",
    "Mediterranean",
    "American diner",
    "Korean",
    "Middle Eastern",
]


def clean_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict) or set(item) != ITEM_REQUIRED_FIELDS:
        return None

    item_name = item.get("item_name")
    description = item.get("description")
    price = item.get("price")

    if not isinstance(item_name, str) or not item_name.strip():
        return None
    if not isinstance(description, str):
        return None
    if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
        return None

    return {
        "item_name": item_name.strip(),
        "description": description.strip(),
        "price": round(float(price), 2),
    }


def clean_menu(menu: Any, cuisine: str) -> dict[str, Any] | None:
    if not isinstance(menu, dict) or set(menu) != MENU_REQUIRED_FIELDS:
        return None

    restaurant = menu.get("restaurant")
    items = menu.get("items")
    if (
        not isinstance(restaurant, str)
        or not restaurant.strip()
        or not isinstance(items, list)
    ):
        return None

    clean_items: list[dict[str, Any]] = []
    seen_items = set()
    for item in items:
        clean = clean_item(item)
        if clean is None:
            continue
        if (key := normalize_key(clean["item_name"])) in seen_items:
            continue
        seen_items.add(key)
        clean_items.append(clean)

    if len(clean_items) == ITEMS_PER_MENU:
        return {
            "restaurant": restaurant.strip(),
            "cuisine": cuisine,
            "items": clean_items,
        }
    return None


def build_batch_prompt(base_prompt: str, cuisine: str, restaurant_keys: list[str]) -> str:
    avoid = "\n".join(f"- {key}" for key in restaurant_keys) or "- none yet"
    return f"""{base_prompt}
    Generate exactly {RESTAURANTS_PER_CUISINE} restaurant menus for this hidden cuisine focus: {cuisine}.
    Each restaurant must have exactly {ITEMS_PER_MENU} menu items.
    The cuisine focus is only for variety. Do not add a cuisine field.
    Avoid repeating these existing restaurant names:
    {avoid}
    """


def summarize(menus: list[dict[str, Any]]) -> dict[str, Any]:
    items = [item for menu in menus for item in menu["items"]]
    item_counts = [len(menu["items"]) for menu in menus]
    cuisines = sorted({menu["cuisine"] for menu in menus})
    return {
        "total_restaurants": len(menus),
        "total_items": len(items),
        "model": GEMINI_MODEL,
        "cuisines": cuisines,
        "items_per_menu_min": min(item_counts) if item_counts else 0,
        "items_per_menu_max": max(item_counts) if item_counts else 0,
        "missing_descriptions": sum(1 for item in items if not item["description"]),
        "uppercase_item_names": sum(
            1 for item in items if str(item["item_name"]).isupper()
        ),
        "likely_ambiguous_item_names": sum(
            1
            for item in items
            if any(
                marker in normalize_key(item["item_name"])
                for marker in AMBIGUOUS_NAME_MARKERS
            )
        ),
    }


def generate_dataset() -> list[dict[str, Any]]:
    base_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    menus: list[dict[str, Any]] = []
    restaurant_keys: list[str] = []

    for cuisine in CUISINES:
        prompt = build_batch_prompt(base_prompt, cuisine, restaurant_keys)
        raw_batch = call_gemini_json(prompt=prompt, schema=RESPONSE_SCHEMA)

        unique_menus: list[dict[str, Any]] = []
        for raw_menu in raw_batch:
            if (menu := clean_menu(raw_menu, cuisine)) is None:
                continue
            if (key := normalize_key(menu["restaurant"])) in restaurant_keys:
                continue
            restaurant_keys.append(key)
            unique_menus.append(menu)
            if len(unique_menus) == RESTAURANTS_PER_CUISINE:
                break

        if len(unique_menus) != RESTAURANTS_PER_CUISINE:
            raise RuntimeError(
                f"{cuisine}: expected {RESTAURANTS_PER_CUISINE} valid menus, "
                f"accepted {len(unique_menus)} from {len(raw_batch)}"
            )

        menus.extend(unique_menus)

        print(
            f"{cuisine}: accepted {len(unique_menus)}/{len(raw_batch)} menus "
            f"({len(menus)} total)"
        )

    return menus


def main() -> int:
    menus = generate_dataset()

    write_json(MENU_OUTPUT_PATH, menus)
    write_json(SUMMARY_PATH, summarize(menus))
    print(f"Wrote {len(menus)} menus to {MENU_OUTPUT_PATH}")
    print(f"Wrote summary to {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
