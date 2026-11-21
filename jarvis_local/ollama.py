"""Minimal Ollama HTTP client (stdlib only)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable


class OllamaDown(Exception):
    """Ollama isn't running (or isn't installed)."""

    def __init__(self, msg: str = "Ollama isn't running. Start the Ollama app, then try again."):
        super().__init__(msg)


@dataclass(frozen=True)
class ModelInfo:
    name: str
    size_bytes: int


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout: float = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _open(self, method: str, path: str, body: dict | None = None, timeout: float | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            return urllib.request.urlopen(req, timeout=timeout or self.timeout)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
            raise OllamaDown() from e

    def _json(self, method, path, body=None, timeout=None):
        with self._open(method, path, body, timeout) as r:
            raw = r.read()
        return json.loads(raw) if raw.strip() else {}

    def available(self) -> bool:
        try:
            self._json("GET", "/api/tags", timeout=3)
            return True
        except Exception:
            return False

    def list(self) -> list[ModelInfo]:
        data = self._json("GET", "/api/tags", timeout=10)
        return [ModelInfo(m["name"], int(m.get("size", 0))) for m in data.get("models", [])]

    def pull(self, name: str, on_progress: Callable[[dict], None] | None = None) -> None:
        with self._open("POST", "/api/pull", {"name": name, "stream": True}, timeout=3600) as r:
            for line in r:
                line = line.strip()
                if line:
                    msg = json.loads(line)
                    if on_progress:
                        on_progress(msg)
                    if msg.get("error"):
                        raise RuntimeError(msg["error"])

    def remove(self, name: str) -> None:
        self._json("DELETE", "/api/delete", {"name": name}, timeout=30)

    def chat(self, model: str, messages: list[dict], json: bool = False) -> str:  # noqa: A002
        body = {"model": model, "messages": messages, "stream": False}
        if json:
            body["format"] = "json"
        data = self._json("POST", "/api/chat", body)
        return data.get("message", {}).get("content", "")

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        data = self._json("POST", "/api/embed", {"model": model, "input": texts})
        return data.get("embeddings", [])
