"""act.py: draft_rewrite and enqueue_hitl action tools."""
from __future__ import annotations

import time

from healf_agent.models import Product
from healf_agent.storage import Storage
from healf_agent.voice import REWRITE_SYSTEM, build_rewrite_prompt


def draft_rewrite(
    *,
    product: Product,
    gaps: list[str],
    anthropic_client,
    model: str = "claude-sonnet-4-6",
) -> str:
    gap_summary = "\n".join(f"- {g}" for g in gaps)
    prompt = build_rewrite_prompt(product, gap_summary)
    resp = anthropic_client.messages.create(
        model=model,
        max_tokens=512,
        system=REWRITE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip() if resp.content else ""


def enqueue_hitl(
    *,
    product: Product,
    drafted_description: str,
    gap_summary: str,
    storage: Storage,
) -> int:
    """Persist a drafted rewrite to the HITL queue. Returns the new row id."""
    cursor = storage.conn.execute(
        "INSERT INTO hitl_queue(product_handle, original_description, drafted_description, gap_summary, status, created_at) "
        "VALUES(?,?,?,?,?,?)",
        (product.handle, product.description, drafted_description, gap_summary, "pending", time.time()),
    )
    storage.conn.commit()
    row_id = cursor.lastrowid
    if row_id is None:
        raise RuntimeError("INSERT into hitl_queue returned no row id")
    return row_id
