"""SQLite storage for the Healf agent."""
from __future__ import annotations

import json
import math
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from healf_agent.models import HITLEntry, Image, Product, Review

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
    created_at REAL NOT NULL,
    reviewer_note TEXT,
    reviewed_at REAL
);
CREATE TABLE IF NOT EXISTS eval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    score REAL NOT NULL,
    detail TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    product_handle TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated ON chat_sessions(updated_at DESC);
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    trace_json TEXT,
    debug_json TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, created_at);
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
        for col, decl in [("reviewer_note", "TEXT"), ("reviewed_at", "REAL")]:
            try:
                self.conn.execute(f"ALTER TABLE hitl_queue ADD COLUMN {col} {decl}")
                self.conn.commit()
            except sqlite3.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise

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

    def knn(self, *, product_type: str | None, query_vec: list[float], k: int = 5) -> list[dict]:
        if product_type is not None:
            rows = self.conn.execute(
                "SELECT handle, title, text, embedding FROM corpus WHERE product_type=?",
                (product_type,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT handle, title, text, embedding FROM corpus",
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

    # ---- hitl_queue ----
    def _row_to_hitl(self, row: sqlite3.Row) -> HITLEntry:
        return HITLEntry(
            id=row["id"],
            product_handle=row["product_handle"],
            original_description=row["original_description"],
            drafted_description=row["drafted_description"],
            gap_summary=row["gap_summary"],
            status=row["status"],
            created_at=datetime.fromtimestamp(row["created_at"], tz=timezone.utc) if row["created_at"] is not None else None,
            reviewer_note=row["reviewer_note"],
            reviewed_at=datetime.fromtimestamp(row["reviewed_at"], tz=timezone.utc) if row["reviewed_at"] is not None else None,
        )

    def list_hitl(self, status: str | None = None) -> list[HITLEntry]:
        if status is not None:
            rows = self.conn.execute(
                "SELECT * FROM hitl_queue WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM hitl_queue ORDER BY created_at DESC",
            ).fetchall()
        return [self._row_to_hitl(r) for r in rows]

    def get_hitl(self, hitl_id: int) -> HITLEntry | None:
        row = self.conn.execute(
            "SELECT * FROM hitl_queue WHERE id = ?", (hitl_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_hitl(row)

    def update_hitl(
        self,
        hitl_id: int,
        *,
        status: str,
        drafted_description: str | None = None,
        reviewer_note: str | None = None,
    ) -> None:
        sets = ["status = ?", "reviewed_at = ?"]
        params: list = [status, time.time()]
        if drafted_description is not None:
            sets.append("drafted_description = ?")
            params.append(drafted_description)
        if reviewer_note is not None:
            sets.append("reviewer_note = ?")
            params.append(reviewer_note)
        params.append(hitl_id)
        cursor = self.conn.execute(
            f"UPDATE hitl_queue SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        self.conn.commit()
        if cursor.rowcount == 0:
            raise KeyError(f"No HITL entry with id={hitl_id}")

    # ---- chat sessions ----

    def create_chat_session(self, title: str, product_handle: str | None = None) -> int:
        now = time.time()
        cursor = self.conn.execute(
            "INSERT INTO chat_sessions(title, product_handle, created_at, updated_at) VALUES(?,?,?,?)",
            (title, product_handle, now, now),
        )
        self.conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]

    def list_recent_sessions(self, limit: int = 5) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT s.id, s.title, s.product_handle, s.updated_at,
                   COUNT(m.id) AS message_count
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_session_messages(self, session_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT role, text, trace_json, debug_json, created_at "
            "FROM chat_messages WHERE session_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        result = []
        for r in rows:
            entry: dict = {"role": r["role"], "text": r["text"]}
            if r["trace_json"]:
                entry["trace"] = json.loads(r["trace_json"])
            if r["debug_json"]:
                entry["debug"] = json.loads(r["debug_json"])
            result.append(entry)
        return result

    def append_chat_message(
        self,
        session_id: int,
        role: str,
        text: str,
        trace: dict | None = None,
        debug: dict | None = None,
    ) -> None:
        now = time.time()
        self.conn.execute(
            "INSERT INTO chat_messages(session_id, role, text, trace_json, debug_json, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                session_id,
                role,
                text,
                json.dumps(trace) if trace is not None else None,
                json.dumps(debug) if debug is not None else None,
                now,
            ),
        )
        self.conn.execute(
            "UPDATE chat_sessions SET updated_at=? WHERE id=?",
            (now, session_id),
        )
        self.conn.commit()

    def update_session_title(self, session_id: int, title: str) -> None:
        self.conn.execute(
            "UPDATE chat_sessions SET title=? WHERE id=?",
            (title, session_id),
        )
        self.conn.commit()

    def update_session_product(self, session_id: int, product_handle: str | None) -> None:
        self.conn.execute(
            "UPDATE chat_sessions SET product_handle=? WHERE id=?",
            (product_handle, session_id),
        )
        self.conn.commit()
