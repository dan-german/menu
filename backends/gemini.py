"""Gemini cleanup backend."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .shared import (
    CLEANUP_RESPONSE_SCHEMA,
    Cleanup,
    build_cleanup_prompt,
    validate_cleanup,
)


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_MAX_OUTPUT_TOKENS = 8192
GEMINI_TIMEOUT_SECONDS = 90
KEY_FILE = Path(__file__).resolve().parents[1] / ".gemini_api_key"


class GeminiBackend:
    name = "gemini"

    def __init__(self, model: str = DEFAULT_GEMINI_MODEL) -> None:
        self.model = model

    def clean(self, item: dict[str, Any]) -> Cleanup:
        value = self.generate_json(
            prompt=build_cleanup_prompt(item), schema=CLEANUP_RESPONSE_SCHEMA
        )
        return validate_cleanup(value)

    def generate_json(self, *, prompt: str, schema: dict[str, Any]) -> Any:
        body = {
            "model": self.model,
            "input": prompt,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": schema,
            },
            "generation_config": {"max_output_tokens": GEMINI_MAX_OUTPUT_TOKENS},
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
            with urllib.request.urlopen(
                request, timeout=GEMINI_TIMEOUT_SECONDS
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach Gemini: {exc.reason}") from exc

        return json.loads(_extract_text(payload))


def _read_api_key() -> str:
    key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or (KEY_FILE.read_text(encoding="utf-8").strip() if KEY_FILE.exists() else "")
    )
    if not key:
        raise RuntimeError("Missing Gemini API key")
    return key


def _extract_text(response: dict[str, Any]) -> str:
    for step in response.get("steps", []):
        if step.get("type") != "model_output":
            continue
        for content in step.get("content", []):
            text = content.get("text", "").strip()
            if content.get("type") == "text" and text:
                return text
    raise ValueError(f"Gemini interaction returned no text: {response}")
