"""benchmark_against_category: kNN corpus retrieval for comparative context."""
from __future__ import annotations

from typing import Any

from healf_agent.corpus import build_corpus_text
from healf_agent.models import Product
from healf_agent.storage import Storage


def benchmark_against_category(
    *,
    product: Product,
    storage: Storage,
    openai_client,
    k: int = 5,
    embed_model: str = "text-embedding-3-small",
) -> dict[str, Any]:
    """Return k nearest corpus neighbours to the given product."""
    query_text = build_corpus_text(
        title=product.title,
        description=product.description,
        claims=product.claims,
    )
    resp = openai_client.embeddings.create(model=embed_model, input=[query_text])
    query_vec = resp.data[0].embedding

    # Try type-filtered first; fall back to full corpus if empty (Gotcha G-04)
    neighbours = storage.knn(product_type=product.product_type, query_vec=query_vec, k=k)
    if not neighbours:
        neighbours = storage.knn(product_type=None, query_vec=query_vec, k=k)

    return {
        "product_handle": product.handle,
        "neighbours": [
            {"handle": n["handle"], "title": n["title"], "excerpt": n["text"][:300]}
            for n in neighbours
            if n["handle"] != product.handle
        ][:k],
    }
