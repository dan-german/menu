#!/usr/bin/env python3
"""Clean menu items with Gemini or a local Ollama model."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backends import CleanupBackend, GeminiBackend, OllamaBackend  # noqa: E402
from backends.gemini import DEFAULT_GEMINI_MODEL  # noqa: E402
from backends.ollama import DEFAULT_OLLAMA_MODEL  # noqa: E402
from utils import GEMINI_CLEANUP_RESULTS_PATH, MESSY_SET_PATH, read_json, write_json


def create_backend(name: str, model: str | None) -> CleanupBackend:
    if name == "gemini":
        return GeminiBackend(model or DEFAULT_GEMINI_MODEL)
    if name == "ollama":
        return OllamaBackend(model or DEFAULT_OLLAMA_MODEL)
    raise ValueError(f"unsupported backend: {name}")


def default_results_path(backend: CleanupBackend) -> Path:
    if backend.name == "gemini" and backend.model == DEFAULT_GEMINI_MODEL:
        return GEMINI_CLEANUP_RESULTS_PATH
    model_slug = re.sub(r"[^a-z0-9]+", "_", backend.model.lower()).strip("_")
    return ROOT / "eval" / "results" / f"{backend.name}_{model_slug}_cleanup.json"


def build_batch_record(
    item: dict[str, Any], *, backend: CleanupBackend
) -> dict[str, Any]:
    started = time.perf_counter()
    output = None
    status = "success"
    error = None
    try:
        output = backend.clean(item["messy_item"])
    except Exception as exc:
        status = "error"
        error = f"{type(exc).__name__}: {exc}"

    original = item["original_item"]
    return {
        "item_id": item["item_id"],
        "backend": backend.name,
        "model": backend.model,
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
    items: list[dict[str, Any]], *, backend: CleanupBackend
) -> list[dict[str, Any]]:
    return [build_batch_record(item, backend=backend) for item in items]


def _item_command(args: argparse.Namespace, backend: CleanupBackend) -> int:
    item = {
        "name": args.name,
        "description": args.description,
    }
    print(json.dumps(backend.clean(item), indent=2, ensure_ascii=True))
    return 0


def _batch_command(args: argparse.Namespace, backend: CleanupBackend) -> int:
    items = read_json(args.input)
    if not isinstance(items, list):
        raise ValueError("batch input must be a JSON array")
    if args.limit is not None:
        items = items[: args.limit]

    results = run_batch(items, backend=backend)
    output_path = args.output or default_results_path(backend)
    write_json(output_path, results)
    succeeded = sum(record["status"] == "success" for record in results)
    print(f"Wrote {len(results)} results to {output_path} ({succeeded} succeeded)")
    return 0 if succeeded == len(results) else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("gemini", "ollama"), default="gemini")
    parser.add_argument("--model", help="override the backend's default model")
    commands = parser.add_subparsers(dest="command", required=True)

    item = commands.add_parser("item", help="clean one menu item")
    item.add_argument("--name", required=True)
    item.add_argument("--description", default="")
    item.set_defaults(handler=_item_command)

    batch = commands.add_parser("batch", help="clean an evaluation-set batch")
    batch.add_argument("--input", type=Path, default=MESSY_SET_PATH)
    batch.add_argument("--output", type=Path)
    batch.add_argument("--limit", type=int)
    batch.set_defaults(handler=_batch_command)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if getattr(args, "limit", None) is not None and args.limit < 1:
        print("ERROR: --limit must be at least 1", file=sys.stderr)
        return 2
    try:
        backend = create_backend(args.backend, args.model)
        return args.handler(args, backend)
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
