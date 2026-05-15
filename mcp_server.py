"""FastMCP server exposing all Healf agent tools.

Run:
    python -m uv run python mcp_server.py

The server maintains a module-level `_current_product` so MCP clients can:
    1. Call set_current_product(url) once.
    2. Then call any product-scoped tool (check_field, evaluate_listing_quality, ...)
       without re-sending the product context.
"""
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from healf_agent.models import Product
from healf_agent.tools import dispatch_tool as _dispatch

mcp = FastMCP("healf-product-intelligence")

_current_product: Product | None = None


def tool_names() -> list[str]:
    """Return the registered tool names (used by tests)."""
    tools_attr = getattr(mcp, "_tools", None)
    if isinstance(tools_attr, dict):
        return list(tools_attr.keys())
    return [
        "set_current_product",
        "fetch_product",
        "check_field",
        "cluster_review_themes",
        "benchmark_against_category",
        "evaluate_listing_quality",
        "score_images",
        "check_consistency",
        "compare_products",
        "draft_rewrite",
        "enqueue_hitl",
    ]


@mcp.tool()
def set_current_product(url: str) -> dict[str, Any]:
    """Load a Healf product by URL and cache it for subsequent tool calls."""
    global _current_product
    data = _dispatch(name="fetch_product", arguments={"url": url}, product=None)
    _current_product = Product.model_validate(data)
    return data


@mcp.tool()
def fetch_product(url: str) -> dict[str, Any]:
    """Fetch a Healf product page. Does NOT update the cached current product."""
    return _dispatch(name="fetch_product", arguments={"url": url}, product=None)


@mcp.tool()
def check_field(field: str, value: str = "") -> dict[str, Any]:
    """Look up an exact factual field on the cached current product."""
    return _dispatch(name="check_field", arguments={"field": field, "value": value}, product=_current_product)


@mcp.tool()
def cluster_review_themes(polarity_filter: str = "all") -> dict[str, Any]:
    """Cluster reviews for the cached current product into themes."""
    return _dispatch(
        name="cluster_review_themes",
        arguments={"polarity_filter": polarity_filter},
        product=_current_product,
    )


@mcp.tool()
def benchmark_against_category(k: int = 5) -> dict[str, Any]:
    """Find similar products in the Healf corpus."""
    return _dispatch(name="benchmark_against_category", arguments={"k": k}, product=_current_product)


@mcp.tool()
def evaluate_listing_quality() -> dict[str, Any]:
    """Score the cached current product on 5 quality axes."""
    return _dispatch(name="evaluate_listing_quality", arguments={}, product=_current_product)


@mcp.tool()
def score_images() -> dict[str, Any]:
    """Score the product images using Gemini Vision."""
    return _dispatch(name="score_images", arguments={}, product=_current_product)


@mcp.tool()
def check_consistency() -> dict[str, Any]:
    """Cross-validate ingredients, claims, description, and review themes."""
    return _dispatch(name="check_consistency", arguments={}, product=_current_product)


@mcp.tool()
def compare_products(urls: list[str]) -> dict[str, Any]:
    """Compare 2-4 Healf product URLs side-by-side."""
    return _dispatch(name="compare_products", arguments={"urls": urls}, product=None)


@mcp.tool()
def draft_rewrite(gaps: list[str]) -> dict[str, Any]:
    """Draft an improved description in Healf voice, addressing identified gaps."""
    return _dispatch(name="draft_rewrite", arguments={"gaps": gaps}, product=_current_product)


@mcp.tool()
def enqueue_hitl(drafted_description: str, gap_summary: str) -> dict[str, Any]:
    """Send a drafted rewrite to the HITL approval queue."""
    return _dispatch(
        name="enqueue_hitl",
        arguments={"drafted_description": drafted_description, "gap_summary": gap_summary},
        product=_current_product,
    )


if __name__ == "__main__":
    mcp.run()
