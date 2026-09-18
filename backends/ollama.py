"""Ollama cleanup backend."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .shared import (
    CLEANUP_RESPONSE_SCHEMA,
    Cleanup,
    build_cleanup_prompt,
    validate_cleanup,
)


DEFAULT_OLLAMA_MODEL = "qwen3:4b"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
OLLAMA_TIMEOUT_SECONDS = 180


class OllamaBackend:
    name = "ollama"

    def __init__(
        self,
        model: str = DEFAULT_OLLAMA_MODEL,
        base_url: str = DEFAULT_OLLAMA_URL,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def clean(self, item: dict[str, Any]) -> Cleanup:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": build_cleanup_prompt(item)}],
            "stream": False,
            "think": False,
            "format": CLEANUP_RESPONSE_SCHEMA,
            "options": {
                "temperature": 0.1,
                "repeat_penalty": 1.1,
                "num_predict": 256,
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=OLLAMA_TIMEOUT_SECONDS
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {self.base_url}: {exc.reason}"
            ) from exc

        try:
            content = payload["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Ollama returned no message content: {payload}") from exc
        return validate_cleanup(json.loads(content))
