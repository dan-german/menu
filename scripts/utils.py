"""Shared helpers for menu dataset scripts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backends.gemini import DEFAULT_GEMINI_MODEL, GeminiBackend  # noqa: E402


RAW_MENUS_PATH = ROOT / "data" / "raw" / "menus.json"
GEMINI_MODEL = DEFAULT_GEMINI_MODEL

EVAL_SAMPLE_SEED = 42
EVAL_TOTAL_ITEMS = 200
EVAL_SPOTCHECK_ITEMS = 20
MESSY_SET_PATH = ROOT / "eval" / "messy_set.json"
EVAL_SPOTCHECK_PATH = ROOT / "eval" / "spotcheck_sample.json"
GEMINI_CLEANUP_RESULTS_PATH = ROOT / "eval" / "results" / "gemini_cleanup.json"

CATEGORY_TAXONOMY = (
    "appetizer",
    "bakery",
    "beverage",
    "breakfast",
    "burger",
    "dessert",
    "main_course",
    "noodles",
    "pizza",
    "rice_dish",
    "salad",
    "sandwich",
    "side",
    "snack",
    "soup",
    "sushi",
    "taco",
    "unknown",
)

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def call_gemini_json(
    *,
    prompt: str,
    schema: dict[str, Any],
) -> Any:
    """Compatibility helper for the milestone 2 dataset builder."""
    return GeminiBackend().generate_json(prompt=prompt, schema=schema)
