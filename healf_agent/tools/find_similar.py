"""find_similar_products: discovery tool returning candidate URLs for compare_products."""
from __future__ import annotations

import json
import re
from typing import Any

from healf_agent.corpus import build_corpus_text
from healf_agent.models import Product
from healf_agent.storage import Storage

# Collections with more members than this threshold are site-wide merchandising
# tags (e.g. "all-products-1": 6077, "best-sellers": 6077) that match almost
# every product and add no discriminating signal.
_MAX_COLLECTION_SIZE = 200

# At most this many candidates from any single brand prefix in the returned list.
# Prevents same-brand cosine saturation when a brand has many near-duplicate SKUs.
_MAX_BRAND_CANDIDATES = 2


def _brand_slug(brand: str | None) -> str | None:
    """Normalise a brand name to its likely collection-slug form."""
    if not brand:
        return None
    return re.sub(r"[^a-z0-9-]", "", brand.lower().replace(" ", "-").strip())


def _handle_brand_prefix(handle: str) -> str:
    """Infer a rough brand group from the first hyphen-delimited segment of a product handle."""
    return handle.split("-")[0] if "-" in handle else handle


def _specific_collections(
    collections: list[str], storage: Storage, brand: str | None = None
) -> set[str]:
    """Return only collections whose corpus membership is <= _MAX_COLLECTION_SIZE.

    Also excludes the current product's own brand collection (e.g. "biocare") so
    same-brand SKUs don't flood the knn candidate pool before cross-brand peers.
    """
    if not collections:
        return set()
    rows = storage.conn.execute("SELECT collections FROM corpus").fetchall()
    freq: dict[str, int] = {}
    for row in rows:
        for c in json.loads(row[0] or "[]"):
            freq[c] = freq.get(c, 0) + 1
    slug = _brand_slug(brand)
    specific = {
        c
        for c in collections
        if freq.get(c, 0) <= _MAX_COLLECTION_SIZE and (slug is None or c != slug)
    }
    if not specific:
        # All collections are generic / brand-only — fall back to the 3 most specific
        # (may include the brand collection as a last resort).
        specific = set(sorted(collections, key=lambda c: freq.get(c, 0))[:3])
    return specific


def find_similar_products(
    *,
    product: Product,
    storage: Storage,
    openai_client,
    k: int = 6,
    embed_model: str = "text-embedding-3-small",
) -> dict[str, Any]:
    """Return k similar products as candidate URLs ready for compare_products."""
    query_text = build_corpus_text(
        title=product.title,
        description=product.description,
        claims=product.claims,
    )
    resp = openai_client.embeddings.create(model=embed_model, input=[query_text])
    query_vec = resp.data[0].embedding

    collection_filter = (
        _specific_collections(product.collections, storage, brand=product.brand)
        if product.collections
        else None
    )

    # Fetch a larger pool so the per-brand cap can refill from diverse candidates.
    fetch_k = max(k * 4, 20)
    neighbours = storage.knn(
        product_type=product.product_type,
        query_vec=query_vec,
        k=fetch_k,
        collection_filter=collection_filter,
    )
    if not neighbours:
        neighbours = storage.knn(product_type=None, query_vec=query_vec, k=fetch_k)

    # Apply per-brand diversity cap: max _MAX_BRAND_CANDIDATES per brand prefix.
    brand_counts: dict[str, int] = {}
    capped: list[dict] = []
    for n in neighbours:
        if n["handle"] == product.handle:
            continue
        prefix = _handle_brand_prefix(n["handle"])
        if brand_counts.get(prefix, 0) >= _MAX_BRAND_CANDIDATES:
            continue
        brand_counts[prefix] = brand_counts.get(prefix, 0) + 1
        capped.append(n)
        if len(capped) >= k:
            break

    candidates = [
        {
            "handle": n["handle"],
            "title": n["title"],
            "product_url": f"https://healf.com/en-uk/products/{n['handle']}",
            "shared_collections": list(
                set(n.get("collections", [])) & (collection_filter or set())
            ),
            "score": round(n["score"], 4),
        }
        for n in capped
    ]

    return {
        "product_handle": product.handle,
        "candidates": candidates,
    }
