"""Tests for the FastAPI /audit webhook."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_health_returns_ok() -> None:
    import webhook
    client = TestClient(webhook.app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_audit_runs_full_chain(monkeypatch) -> None:
    import webhook
    from healf_agent.models import Product

    fake_product = Product(
        url="https://healf.com/en-uk/products/x",
        handle="x", title="X", brand="X", product_type="Electrolytes",
        description="d", price_gbp=1.0, currency="GBP", sku="x",
        gid="gid://shopify/Product/1",
    )

    def fake_dispatch(*, name, arguments, product):
        if name == "fetch_product":
            return fake_product.model_dump(mode="json")
        if name == "evaluate_listing_quality":
            return {
                "product_handle": "x",
                "scores": [{"axis": "ingredients", "score": 2, "rationale": "thin"}],
                "gaps": ["ingredient transparency"],
                "corpus_references": [],
            }
        if name == "draft_rewrite":
            return {"drafted_description": "Better copy.", "product_handle": "x"}
        if name == "enqueue_hitl":
            return {"entry_id": 42, "status": "pending", "product_handle": "x"}
        raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(webhook, "_dispatch", fake_dispatch)
    client = TestClient(webhook.app)
    r = client.post("/audit", json={
        "url": "https://healf.com/en-uk/products/x",
        "draft": True,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["product_handle"] == "x"
    assert body["score"] == 2.0
    assert body["hitl_id"] == 42
    assert "Better" in body["draft"]


def test_audit_rejects_non_healf_url() -> None:
    import webhook
    client = TestClient(webhook.app)
    r = client.post("/audit", json={"url": "https://example.com/foo"})
    assert r.status_code == 400
    assert "healf" in r.json().get("detail", "").lower()
