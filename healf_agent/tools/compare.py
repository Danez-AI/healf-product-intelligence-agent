"""compare_products: side-by-side comparison of multiple Healf products."""
from __future__ import annotations

from healf_agent.models import Comparison, Product


def compare_products(products: list[Product]) -> Comparison:
    """Return a structured side-by-side comparison."""
    if len(products) < 2:
        raise ValueError("need at least 2 products to compare")

    axes = [
        ("price_gbp", lambda p: f"£{p.price_gbp:.2f}"),
        ("rating", lambda p: f"{p.rating_value}/5 ({p.rating_count} reviews)" if p.rating_value else "N/A"),
        ("ingredients_count", lambda p: str(len(p.ingredients))),
        ("claims_count", lambda p: str(len(p.claims))),
        ("image_count", lambda p: str(len(p.images))),
        ("description_length", lambda p: str(len(p.description))),
    ]

    rows = [
        {"axis": axis, **{p.handle: fn(p) for p in products}}
        for axis, fn in axes
    ]

    winner_price = min(products, key=lambda p: p.price_gbp).handle
    winner_rating = max(products, key=lambda p: p.rating_value or 0).handle
    summary = (
        f"Compared {len(products)} products. "
        f"Best price: {winner_price}. Best rating: {winner_rating}."
    )

    return Comparison(
        handles=[p.handle for p in products],
        rows=rows,
        summary=summary,
    )
