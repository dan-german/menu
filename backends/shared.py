"""Shared cleanup prompt, schema, and backend contract."""

from __future__ import annotations

import json
from typing import Any, Protocol


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


class CleanupBackend(Protocol):
    """Backend interface used by the cleanup runner."""

    name: str
    model: str

    def clean(self, item: dict[str, Any]) -> Cleanup: ...


def build_cleanup_prompt(item: dict[str, Any]) -> str:
    return ( 
        "Clean this. "
        "Correct spelling & casing. "
        "Concisely elaborate short descriptions (1 sentence)."
        "No information like price. "
        "No subjective language. \n"
        f"{json.dumps(item, ensure_ascii=True)}"
    )


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
