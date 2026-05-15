"""check_field: exact factual lookups grounded in the Product."""
from __future__ import annotations

from healf_agent.models import Product


def check_field(product: Product, *, field: str, value: str) -> dict:
    needle = value.lower()
    if field == "ingredient":
        present = any(needle in i.lower() for i in product.ingredients)
        return {"present": present, "evidence": product.ingredients}
    if field == "claim":
        present = any(needle in c.lower() for c in product.claims)
        return {"present": present, "evidence": product.claims}
    if field == "brand":
        return {"present": needle == product.brand.lower(), "evidence": product.brand}
    if field == "rating":
        return {"value": product.rating_value, "count": product.rating_count}
    return {"present": False, "evidence": None}
