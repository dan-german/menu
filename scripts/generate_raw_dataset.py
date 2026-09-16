#!/usr/bin/env python3
"""Generate raw synthetic restaurant menus with the Google Gemini API."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "raw_dataset_generation.md"
MENU_OUTPUT_PATH = ROOT / "data" / "raw" / "synthetic_menus.json"
SUMMARY_PATH = ROOT / "data" / "raw" / "summary.json"
KEY_FILE = ROOT / ".gemini_api_key"
MODEL = "gemini-3.5-flash-lite"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
RESTAURANTS_PER_CUISINE = 2
ITEMS_PER_MENU = 20
MAX_OUTPUT_TOKENS = 8192
REQUEST_TIMEOUT_SECONDS = 60

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


def read_api_key() -> str:
    key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or (
            KEY_FILE.read_text(encoding="utf-8").strip()
            if KEY_FILE.exists()
            else ""
        )
    )
    if not key:
        raise SystemExit("Missing Gemini API key.")
    return key


def normalize_key(value: str) -> str:
    """
    Lowercase, replace each non-alphanumeric sequence with a single space and trim.
    """
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def extract_text(response: dict[str, Any]) -> str:
    for step in response.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for content in step.get("content", []):
            if content.get("type") == "text" and (
                text := content.get("text", "").strip()
            ):
                return text
    raise ValueError(f"Gemini interaction returned no text: {response}")


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


def clean_menu(menu: Any) -> dict[str, Any] | None:
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
        return {"restaurant": restaurant.strip(), "items": clean_items}
    return None


def call_gemini_interaction(api_key: str, prompt: str) -> list[Any]:
    body = {
        "model": MODEL,
        "input": prompt,
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": RESPONSE_SCHEMA,
        },
        "generation_config": {
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        },
    }
    request = urllib.request.Request(
        GEMINI_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail}") from exc

    menus = json.loads(extract_text(payload))
    if not isinstance(menus, list):
        raise ValueError("Gemini response must be a JSON array")
    return menus


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
    return {
        "total_restaurants": len(menus),
        "total_items": len(items),
        "model": MODEL,
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
    api_key = read_api_key()
    base_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    menus: list[dict[str, Any]] = []
    restaurant_keys: list[str] = []

    for cuisine in CUISINES:
        prompt = build_batch_prompt(base_prompt, cuisine, restaurant_keys)
        raw_batch = call_gemini_interaction(api_key, prompt)

        unique_menus: list[dict[str, Any]] = []
        for raw_menu in raw_batch:
            if (menu := clean_menu(raw_menu)) is None:
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


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    menus = generate_dataset()

    MENU_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_json(MENU_OUTPUT_PATH, menus)
    write_json(SUMMARY_PATH, summarize(menus))
    print(f"Wrote {len(menus)} menus to {MENU_OUTPUT_PATH}")
    print(f"Wrote summary to {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
