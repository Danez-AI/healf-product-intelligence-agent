"""find_similar_products: discovery tool returning candidate URLs for compare_products."""
from __future__ import annotations

from typing import Any

from healf_agent.corpus import build_corpus_text
from healf_agent.models import Product
from healf_agent.storage import Storage


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

    collection_filter = set(product.collections) if product.collections else None
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
