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

DEFAULT_CLEANUP_INSTRUCTIONS = """You are a careful restaurant menu copy editor.

Rewrite the provided menu item as polished, natural English.

NAME
- Correct capitalization, punctuation, abbreviations, and obvious food-related typos.
- Preserve the dish identity, quantities, sizes, and set composition.
- Make the smallest correction necessary.
- Do not replace correctly spelled food terms.
- Use the restaurant and category to resolve ambiguous text.
- Expand pc, pcs, and tk as pieces when they represent an item count.

DESCRIPTION
- Write one concise, complete sentence suitable for a restaurant menu.
- Preserve every useful fact supplied by the input.
- Turn terse ingredient lists into natural prose.
- Do not invent ingredients, accompaniments, preparation methods, origins, or marketing claims.
- When the description is empty, state only what the name, quantity, and category establish.
- Ignore meaningless description fragments rather than repeating them.

Change pcs to pieces."""


class CleanupBackend(Protocol):
    """Backend interface used by the cleanup runner."""

    name: str
    model: str

    def clean(
        self, item: dict[str, Any], instructions: str | None = None
    ) -> Cleanup: ...


def build_cleanup_prompt(
    item: dict[str, Any], instructions: str | None = None
) -> str:
    selected_instructions = instructions or DEFAULT_CLEANUP_INSTRUCTIONS
    output_contract = (
        'Return exactly one JSON object with exactly these string fields: '
        '{"normalized_name":"...","normalized_description":"..."}. '
        "Do not return Markdown or any other fields."
    )
    return (
        f"{selected_instructions.strip()}\n\n{output_contract}\n\n"
        f"Menu item:\n{json.dumps(item, ensure_ascii=True)}"
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
