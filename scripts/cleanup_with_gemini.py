#!/usr/bin/env python3
"""Clean one menu item or the messy evaluation set with Gemini."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

from utils import (
    GEMINI_CLEANUP_RESULTS_PATH,
    MESSY_SET_PATH,
    call_gemini_json,
    read_json,
    write_json,
)


CLEANUP_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "normalized_name": {"type": "string"},
        "normalized_description": {"type": "string"},
    },
    "required": ["normalized_name", "normalized_description"],
    "additionalProperties": False,
}

Cleanup = dict[str, str]
GeminiCaller = Callable[..., Any]


def build_prompt(item: dict[str, Any]) -> str:
    return f"Clean up this menu item. Concisely elaborate short descriptions. Avoid subjective language.\n{json.dumps(item, ensure_ascii=True)}"


def validate_cleanup(value: Any) -> Cleanup:
    if not isinstance(value, dict):
        raise ValueError("cleanup response must be an object")
    expected_fields = {"normalized_name", "normalized_description"}
    if set(value) != expected_fields:
        raise ValueError(
            "cleanup response must contain only normalized_name and "
            "normalized_description"
        )
    if not isinstance(value["normalized_name"], str):
        raise ValueError("normalized_name must be a string")
    if not isinstance(value["normalized_description"], str):
        raise ValueError("normalized_description must be a string")
    if not value["normalized_name"].strip():
        raise ValueError("normalized_name must not be empty")
    return {
        "normalized_name": value["normalized_name"],
        "normalized_description": value["normalized_description"],
    }


def clean_item(
    item: dict[str, Any], *, caller: GeminiCaller = call_gemini_json
) -> Cleanup:
    prompt = build_prompt(item)
    print(prompt)
    response = caller(prompt=build_prompt(
        item), schema=CLEANUP_RESPONSE_SCHEMA)
    return validate_cleanup(response)


def build_batch_record(
    item: dict[str, Any],
    *,
    cleaner: Callable[[dict[str, Any]], Cleanup] = clean_item,
) -> dict[str, Any]:
    started = time.perf_counter()
    output: Cleanup | None = None
    status = "success"
    error: str | None = None
    try:
        output = cleaner(item["messy_item"])
    except Exception as exc:
        status = "error"
        error = f"{type(exc).__name__}: {exc}"

    original = item["original_item"]
    return {
        "item_id": item["item_id"],
        "source": {
            "source_cuisine": item["source_cuisine"],
            "restaurant": item["restaurant"],
            "restaurant_id": item["restaurant_id"],
            "category_source": item["category_source"],
            "raw_item_index": item["raw_item_index"],
        },
        "input": item["messy_item"],
        "expected": {
            "normalized_name": original["name"],
            "normalized_description": original["description"],
        },
        "output": output,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "status": status,
        "error": error,
    }


def run_batch(
    items: list[dict[str, Any]],
    *,
    cleaner: Callable[[dict[str, Any]], Cleanup] = clean_item,
) -> list[dict[str, Any]]:
    return [build_batch_record(item, cleaner=cleaner) for item in items]


def _item_command(args: argparse.Namespace) -> int:
    item = {
        "name": args.name,
        "description": args.description,
        "price": args.price,
    }
    print(json.dumps(clean_item(item), indent=2, ensure_ascii=True))
    return 0


def _batch_command(args: argparse.Namespace) -> int:
    items = read_json(args.input)
    if not isinstance(items, list):
        raise ValueError("batch input must be a JSON array")
    if args.limit is not None:
        items = items[: args.limit]

    results = run_batch(items)
    write_json(args.output, results)
    succeeded = sum(record["status"] == "success" for record in results)
    print(
        f"Wrote {len(results)} results to {args.output} ({succeeded} succeeded)")
    return 0 if succeeded == len(results) else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    item = commands.add_parser("item", help="clean one menu item")
    item.add_argument("--name", required=True)
    item.add_argument("--description", default="")
    item.add_argument("--price", type=float)
    item.set_defaults(handler=_item_command)

    batch = commands.add_parser("batch", help="clean an evaluation-set batch")
    batch.add_argument("--input", type=Path, default=MESSY_SET_PATH)
    batch.add_argument("--output", type=Path,
                       default=GEMINI_CLEANUP_RESULTS_PATH)
    batch.add_argument("--limit", type=int)
    batch.set_defaults(handler=_batch_command)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if getattr(args, "limit", None) is not None and args.limit < 1:
        print("ERROR: --limit must be at least 1", file=sys.stderr)
        return 2
    try:
        return args.handler(args)
    except (KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
