"""Shared helpers for menu dataset scripts."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RAW_MENUS_PATH = ROOT / "data" / "raw" / "synthetic_menus.json"
KEY_FILE = ROOT / ".gemini_api_key"
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_MAX_OUTPUT_TOKENS = 8192
GEMINI_TIMEOUT_SECONDS = 90

EVAL_SAMPLE_SEED = 42
EVAL_ITEMS_PER_RESTAURANT = 5
EVAL_TOTAL_ITEMS = 100

DIETARY_TAGS = (
    "vegetarian",
    "vegan",
    "gluten_free",
    "contains_dairy",
    "contains_nuts",
    "contains_shellfish",
    "contains_pork",
    "contains_meat",
    "spicy",
    "unknown",
)

def normalize_key(value: str) -> str:
    """Normalize loose menu text for matching and validation."""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def item_id(restaurant_index: int, item_index: int) -> str:
    """Build the stable ID used to link eval items to raw menu items."""
    return f"r{restaurant_index + 1:03d}_i{item_index + 1:03d}"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _read_api_key() -> str:
    key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or (KEY_FILE.read_text(encoding="utf-8").strip() if KEY_FILE.exists() else "")
    )
    if not key:
        raise SystemExit("Missing Gemini API key.")
    return key


def _extract_text(response: dict[str, Any]) -> str:
    for step in response.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for content in step.get("content", []):
            if content.get("type") == "text" and (text := content.get("text", "").strip()):
                return text
    raise ValueError(f"Gemini interaction returned no text: {response}")


def call_gemini_json(
    *,
    prompt: str,
    schema: dict[str, Any],
) -> Any:
    body = {
        "model": GEMINI_MODEL,
        "input": prompt,
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": schema,
        },
        "generation_config": {
            "max_output_tokens": GEMINI_MAX_OUTPUT_TOKENS,
        },
    }
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": _read_api_key(),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=GEMINI_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail}") from exc

    return json.loads(_extract_text(payload))
