"""Long-term memory: text + embeddings in SQLite, cosine search."""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class Memory:
    def __init__(self, db_path, client, embed_model: str = "nomic-embed-text"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.client = client
        self.embed_model = embed_model
        conn = self._conn()
        try:
            with conn:
                conn.execute("CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                             " text TEXT NOT NULL, meta TEXT NOT NULL, vec TEXT NOT NULL)")
        finally:
            conn.close()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _embed(self, text: str) -> list[float]:
        vecs = self.client.embed(self.embed_model, [text])
        if not vecs:
            raise RuntimeError("The embedding model returned nothing.")
        return list(vecs[0])

    def add(self, text: str, meta: dict | None = None) -> int:
        vec = self._embed(text)
        conn = self._conn()
        try:
            with conn:
                cur = conn.execute("INSERT INTO memory (text, meta, vec) VALUES (?,?,?)",
                                   (text, json.dumps(meta or {}), json.dumps(vec)))
            return int(cur.lastrowid)
        finally:
            conn.close()

    def search(self, query: str, k: int = 5) -> list[tuple[float, str, dict]]:
        q = self._embed(query)
        conn = self._conn()
        try:
            rows = conn.execute("SELECT text, meta, vec FROM memory").fetchall()
        finally:
            conn.close()
        scored = [(_cos(q, json.loads(v)), t, json.loads(m)) for t, m, v in rows]
        scored.sort(key=lambda r: r[0], reverse=True)
        return scored[:max(0, k)]
