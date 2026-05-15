"""SQLite storage for the Healf agent."""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Iterable

from healf_agent.models import Image, Product, Review

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    handle TEXT PRIMARY KEY,
    gid TEXT UNIQUE NOT NULL,
    json TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    product_gid TEXT NOT NULL,
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reviews_gid ON reviews(product_gid);
CREATE TABLE IF NOT EXISTS corpus (
    handle TEXT PRIMARY KEY,
    product_type TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_corpus_type ON corpus(product_type);
CREATE TABLE IF NOT EXISTS review_themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_gid TEXT NOT NULL,
    polarity TEXT NOT NULL,
    label TEXT NOT NULL,
    summary TEXT NOT NULL,
    review_ids TEXT NOT NULL,
    weight REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS hitl_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_handle TEXT NOT NULL,
    original_description TEXT NOT NULL,
    drafted_description TEXT NOT NULL,
    gap_summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS eval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    score REAL NOT NULL,
    detail TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


def _vec_to_blob(vec: list[float]) -> bytes:
    import array
    return array.array("f", vec).tobytes()


def _blob_to_vec(blob: bytes) -> list[float]:
    import array
    a = array.array("f")
    a.frombytes(blob)
    return list(a)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


class Storage:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- products ----
    def upsert_product(self, p: Product) -> None:
        import time
        payload = p.model_dump(mode="json")
        self.conn.execute(
            "INSERT INTO products(handle, gid, json, fetched_at) VALUES(?,?,?,?) "
            "ON CONFLICT(handle) DO UPDATE SET gid=excluded.gid, json=excluded.json, fetched_at=excluded.fetched_at",
            (p.handle, p.gid, json.dumps(payload), time.time()),
        )
        self.conn.commit()

    def get_product(self, handle: str) -> Product | None:
        row = self.conn.execute("SELECT json FROM products WHERE handle=?", (handle,)).fetchone()
        if not row:
            return None
        return Product.model_validate(json.loads(row["json"]))

    # ---- reviews ----
    def upsert_reviews(self, reviews: Iterable[Review]) -> None:
        rows = [
            (r.review_id, r.product_gid, json.dumps(r.model_dump(mode="json")))
            for r in reviews
        ]
        self.conn.executemany(
            "INSERT INTO reviews(review_id, product_gid, json) VALUES(?,?,?) "
            "ON CONFLICT(review_id) DO UPDATE SET json=excluded.json",
            rows,
        )
        self.conn.commit()

    def get_reviews(self, product_gid: str) -> list[Review]:
        rows = self.conn.execute(
            "SELECT json FROM reviews WHERE product_gid=?", (product_gid,)
        ).fetchall()
        return [Review.model_validate(json.loads(r["json"])) for r in rows]

    # ---- corpus ----
    def upsert_corpus_entry(
        self,
        handle: str,
        product_type: str,
        title: str,
        text: str,
        embedding: list[float],
    ) -> None:
        self.conn.execute(
            "INSERT INTO corpus(handle, product_type, title, text, embedding) VALUES(?,?,?,?,?) "
            "ON CONFLICT(handle) DO UPDATE SET product_type=excluded.product_type, title=excluded.title, text=excluded.text, embedding=excluded.embedding",
            (handle, product_type, title, text, _vec_to_blob(embedding)),
        )
        self.conn.commit()

    def knn(self, *, product_type: str, query_vec: list[float], k: int = 5) -> list[dict]:
        rows = self.conn.execute(
            "SELECT handle, title, text, embedding FROM corpus WHERE product_type=?",
            (product_type,),
        ).fetchall()
        scored = [
            {
                "handle": r["handle"],
                "title": r["title"],
                "text": r["text"],
                "score": _cosine(query_vec, _blob_to_vec(r["embedding"])),
            }
            for r in rows
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]
