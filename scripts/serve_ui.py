#!/usr/bin/env python3
"""Serve the local cleanup endpoint used by the comparison UI."""

from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backends import GeminiBackend, OllamaBackend  # noqa: E402


BACKENDS = {
    "gemini": GeminiBackend(),
}
OLLAMA_MODELS = {
    "qwen3:4b",
    "qwen3.5:9b",
    "ministral-3:8b",
    "gemma3:12b",
}


class CleanupHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/api/cleanup":
            self._send_json(404, {"error": "not found"})
            return

        try:
            payload = self._read_json()
            backend_id = payload["backend"]
            model = payload.get("model")
            item = payload["item"]
            instructions = payload.get("prompt")
            backend = self._get_backend(backend_id, model)
            if not isinstance(item, dict):
                raise ValueError("item must be an object")
            if not isinstance(instructions, str) or not instructions.strip():
                raise ValueError("prompt must be a non-empty string")

            started = time.perf_counter()
            output = backend.clean(item, instructions=instructions)
            self._send_json(
                200,
                {
                    "output": output,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            self._send_json(400, {"error": f"{type(exc).__name__}: {exc}"})
        except Exception as exc:
            self._send_json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def _get_backend(self, backend_id: str, model: Any):
        if backend_id == "gemini":
            return BACKENDS["gemini"]
        if backend_id != "ollama" or model not in OLLAMA_MODELS:
            raise ValueError(f"unsupported model: {model}")
        if model not in BACKENDS:
            BACKENDS[model] = OllamaBackend(model)
        return BACKENDS[model]

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def _send_json(self, status: int, value: dict[str, Any]) -> None:
        body = json.dumps(value, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), CleanupHandler)
    print("Cleanup API running at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
