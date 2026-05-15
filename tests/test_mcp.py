"""Tests for the FastMCP server wrapper."""
from __future__ import annotations

import pytest


def test_mcp_server_exposes_expected_tools() -> None:
    """The MCP server must register one tool per Healf tool plus set_current_product."""
    import mcp_server

    names = mcp_server.tool_names()
    expected = {
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
    }
    assert expected.issubset(set(names)), f"missing: {expected - set(names)}"


def test_set_current_product_caches_product(monkeypatch) -> None:
    """set_current_product should call fetch_product and store the Product on the module."""
    import mcp_server
    from healf_agent.models import Product

    fake = Product(
        url="https://healf.com/en-uk/products/x",
        handle="x", title="X", brand="X", product_type="Electrolytes",
        description="d", price_gbp=1.0, currency="GBP", sku="x",
        gid="gid://shopify/Product/1",
    )

    def fake_dispatch(*, name, arguments, product):
        assert name == "fetch_product"
        return fake.model_dump(mode="json")

    monkeypatch.setattr(mcp_server, "_dispatch", fake_dispatch)
    out = mcp_server.set_current_product(url="https://healf.com/en-uk/products/x")
    assert out["handle"] == "x"
    assert mcp_server._current_product is not None
    assert mcp_server._current_product.handle == "x"


def test_check_field_uses_cached_product(monkeypatch) -> None:
    """check_field MCP tool should pass the cached _current_product to dispatch_tool."""
    import mcp_server
    from healf_agent.models import Product

    p = Product(
        url="https://healf.com/en-uk/products/x",
        handle="x", title="X", brand="X", product_type="Electrolytes",
        description="d", price_gbp=1.0, currency="GBP", sku="x",
        gid="gid://shopify/Product/1",
        ingredients=["sodium"],
    )
    mcp_server._current_product = p

    captured = {}
    def fake_dispatch(*, name, arguments, product):
        captured["name"] = name
        captured["product"] = product
        return {"present": True}

    monkeypatch.setattr(mcp_server, "_dispatch", fake_dispatch)
    result = mcp_server.check_field(field="ingredient", value="sodium")
    assert result == {"present": True}
    assert captured["product"] is p
    assert captured["name"] == "check_field"
