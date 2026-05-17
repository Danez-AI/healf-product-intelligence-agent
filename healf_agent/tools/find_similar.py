"""find_similar_products: discovery tool returning candidate URLs for compare_products."""
from __future__ import annotations

import json
from typing import Any

from healf_agent.corpus import build_corpus_text
from healf_agent.models import Product
from healf_agent.storage import Storage

# Collections with more members than this threshold are site-wide merchandising
# tags (e.g. "all-products-1": 6077, "best-sellers": 6077) that match almost
# every product and add no discriminating signal. Only small, specific collections
# (e.g. "vitamin-b12": 32, "biocare": 118) should drive candidate retrieval.
_MAX_COLLECTION_SIZE = 200


def _specific_collections(collections: list[str], storage: Storage) -> set[str]:
    """Return only collections whose corpus membership is <= _MAX_COLLECTION_SIZE."""
    if not collections:
        return set()
    rows = storage.conn.execute("SELECT collections FROM corpus").fetchall()
    freq: dict[str, int] = {}
    for row in rows:
        for c in json.loads(row[0] or "[]"):
            freq[c] = freq.get(c, 0) + 1
    specific = {c for c in collections if freq.get(c, 0) <= _MAX_COLLECTION_SIZE}
    if not specific:
        # All collections are generic — fall back to the 3 most specific ones.
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

    collection_filter = _specific_collections(product.collections, storage) if product.collections else None
    neighbours = storage.knn(
        product_type=product.product_type,
        query_vec=query_vec,
        k=k,
        collection_filter=collection_filter,
    )
    if not neighbours:
        neighbours = storage.knn(product_type=None, query_vec=query_vec, k=k)

    candidates = [
        {
            "handle": n["handle"],
            "title": n["title"],
            "product_url": f"https://healf.com/en-uk/products/{n['handle']}",
            "shared_collections": list(set(n.get("collections", [])) & (collection_filter or set())),
            "score": round(n["score"], 4),
        }
        for n in neighbours
        if n["handle"] != product.handle
    ][:k]

    return {
        "product_handle": product.handle,
        "candidates": candidates,
    }
