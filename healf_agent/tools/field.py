"""check_field: exact factual lookups grounded in the Product."""
from __future__ import annotations

from healf_agent.models import Product


def check_field(product: Product, *, field: str, value: str = "") -> dict:
    """Check whether a named field is populated on the product.

    present: True  — field contains the value (or is non-empty when no value given)
    present: False — field is empty and extraction is confirmed to have run
    present: None  — extraction did not run; absence cannot be asserted
    """
    if field == "rating":
        return {"value": product.rating_value, "count": product.rating_count}

    if field == "brand":
        needle = value.lower()
        if needle:
            return {"present": needle in product.brand.lower(), "evidence": product.brand}
        return {"present": bool(product.brand), "evidence": product.brand}

    if field == "ingredient":
        if product.ingredients:
            needle = value.lower()
            present = any(needle in i.lower() for i in product.ingredients) if needle else True
            return {"present": present, "evidence": product.ingredients, "extraction_status": "ok"}
        if product.raw_metafields is not None:
            return {"present": False, "evidence": [], "extraction_status": "ok"}
        return {"field": field, "present": None, "value": None, "extraction_status": "no_metafields"}

    if field == "claim":
        if product.claims:
            needle = value.lower()
            present = any(needle in c.lower() for c in product.claims) if needle else True
            return {"present": present, "evidence": product.claims, "extraction_status": "ok"}
        if product.raw_metafields is not None:
            return {"present": False, "evidence": [], "extraction_status": "ok"}
        return {"field": field, "present": None, "value": None, "extraction_status": "no_metafields"}

    return {"field": field, "present": None, "value": None, "extraction_status": "unknown_field"}
