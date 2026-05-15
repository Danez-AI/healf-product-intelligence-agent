"""Yotpo reviews fetcher."""
from __future__ import annotations

import os
from datetime import datetime

import httpx

from healf_agent.models import Review

YOTPO_BASE = "https://api.yotpo.com/v1/widget"


def _product_id_from_gid(gid: str) -> str:
    return gid.rsplit("/", 1)[-1]


def _to_review(raw: dict, product_gid: str) -> Review:
    score = int(raw.get("score") or raw.get("rating") or 0) or 1
    created_raw = raw.get("created_at")
    created: datetime | None = None
    if created_raw:
        try:
            created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except ValueError:
            created = None
    user = raw.get("user") or {}
    return Review(
        review_id=str(raw.get("id") or raw.get("review_id") or ""),
        product_gid=product_gid,
        author=(user.get("display_name") if isinstance(user, dict) else None),
        rating=max(1, min(5, score)),
        title=raw.get("title"),
        body=raw.get("content") or raw.get("body") or "",
        created_at=created,
        verified=bool(raw.get("verified_buyer", False)),
    )


def fetch_reviews_full(
    *,
    product_gid: str,
    app_key: str | None = None,
    per_page: int = 50,
    max_pages: int = 50,
    timeout: float = 30.0,
) -> list[Review]:
    """Paginate the Yotpo widget API for a product. Returns all reviews."""
    app_key = app_key or os.environ.get("YOTPO_APP_KEY")
    if not app_key:
        raise RuntimeError("YOTPO_APP_KEY missing")
    product_id = _product_id_from_gid(product_gid)
    url = f"{YOTPO_BASE}/{app_key}/products/{product_id}/reviews.json"
    out: list[Review] = []
    seen_ids: set[str] = set()
    with httpx.Client(timeout=timeout) as client:
        for page in range(1, max_pages + 1):
            r = client.get(url, params={"page": page, "per_page": per_page})
            if r.status_code != 200:
                break
            data = r.json().get("response", {})
            chunk = data.get("reviews") or []
            if not chunk:
                break
            for raw in chunk:
                rv = _to_review(raw, product_gid)
                if rv.review_id and rv.review_id not in seen_ids:
                    seen_ids.add(rv.review_id)
                    out.append(rv)
            total = (data.get("pagination") or {}).get("total")
            if total and len(out) >= total:
                break
    return out
