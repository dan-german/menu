#!/usr/bin/env python3
"""Summarize cuisines, restaurants, and menu items."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from utils import read_json, write_json


ROOT = Path(__file__).resolve().parents[1]
MENUS_PATH = ROOT / "data" / "raw" / "menus.json"
SUMMARY_PATH = ROOT / "data" / "raw" / "summary.json"


def count_restaurant_items(restaurant: dict[str, Any]) -> int:
    return sum(len(category["items"]) for category in restaurant["categories"])


def count_items(restaurants: list[dict[str, Any]]) -> int:
    return sum(count_restaurant_items(restaurant) for restaurant in restaurants)


def summarize(menus_by_cuisine: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    restaurant_count_by_cuisine = {
        cuisine: len(restaurants)
        for cuisine, restaurants in sorted(menus_by_cuisine.items())
    }
    item_count_by_cuisine = {
        cuisine: count_items(restaurants)
        for cuisine, restaurants in sorted(menus_by_cuisine.items())
    }
    restaurant_item_counts = [
        count_restaurant_items(restaurant)
        for restaurants in menus_by_cuisine.values()
        for restaurant in restaurants
    ]

    return {
        "total_cuisines": len(menus_by_cuisine),
        "total_restaurants": sum(restaurant_count_by_cuisine.values()),
        "total_items": sum(item_count_by_cuisine.values()),
        "min_items_per_restaurant": min(restaurant_item_counts, default=0),
        "max_items_per_restaurant": max(restaurant_item_counts, default=0),
        "restaurants_by_cuisine": restaurant_count_by_cuisine,
        "items_by_cuisine": item_count_by_cuisine,
    }


def print_summary(summary: dict[str, Any]) -> None:
    print(f"Cuisines: {summary['total_cuisines']}")
    print(f"Restaurants: {summary['total_restaurants']}")
    print(f"Items: {summary['total_items']}")
    print(f"Min items per restaurant: {summary['min_items_per_restaurant']}")
    print(f"Max items per restaurant: {summary['max_items_per_restaurant']}")
    print("\nBy cuisine:")
    for cuisine, restaurants in summary["restaurants_by_cuisine"].items():
        items = summary["items_by_cuisine"][cuisine]
        print(f"- {cuisine}: {restaurants} restaurants, {items} items")


def main() -> None:
    summary = summarize(read_json(MENUS_PATH))
    print_summary(summary)
    write_json(SUMMARY_PATH, summary)
    print(f"\nWrote summary to {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
