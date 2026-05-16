"""Tests for score_images tool — using monkeypatched Gemini client."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from healf_agent.models import Image, Product
from healf_agent.tools.vision import score_images


def _make_product(image_urls: list[str]) -> Product:
    return Product(
        url="https://healf.com/en-uk/products/test",
        handle="test",
        title="Test Product",
        brand="Brand",
        product_type="Unknown",
        description="",
        price_gbp=9.99,
        currency="GBP",
        sku="test",
        gid="gid://shopify/Product/1",
        images=[Image(url=u) for u in image_urls],
        ingredients=[],
        claims=[],
    )


def _make_gemini_client(response_text: str) -> MagicMock:
    """Return a MagicMock mimicking google.genai.Client.models.generate_content."""
    mock_resp = MagicMock()
    mock_resp.text = response_text
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp
    return mock_client


def test_score_images_empty_product():
    """No images → returns note, no Gemini call."""
    product = _make_product([])
    client = _make_gemini_client("[]")
    result = score_images(product=product, gemini_client=client)
    assert result.get("note") == "no images found"
    client.models.generate_content.assert_not_called()


def test_score_images_returns_aggregated_on_pack_text(monkeypatch):
    """on_pack_text values from multiple images are joined into aggregated_on_pack_text."""
    scores = [
        {
            "url": "https://example.com/img1.jpg",
            "clarity": 5,
            "lifestyle": False,
            "label_legible": True,
            "overall": 5,
            "notes": "Clear studio shot",
            "on_pack_text": "Sodium 1000mg per sachet",
            "contains_nutrition_panel": True,
        },
        {
            "url": "https://example.com/img2.jpg",
            "clarity": 4,
            "lifestyle": True,
            "label_legible": False,
            "overall": 4,
            "notes": "Lifestyle shot",
            "on_pack_text": "",
            "contains_nutrition_panel": False,
        },
    ]
    product = _make_product(
        ["https://example.com/img1.jpg", "https://example.com/img2.jpg"]
    )
    client = _make_gemini_client(json.dumps(scores))

    # Monkeypatch _fetch_image_bytes to avoid real HTTP
    import healf_agent.tools.vision as _vision
    monkeypatch.setattr(_vision, "_fetch_image_bytes", lambda url, **kw: b"\xff\xd8\xff" + b"\x00" * 10)

    result = score_images(product=product, gemini_client=client)

    assert result["aggregated_on_pack_text"] == "Sodium 1000mg per sachet"
    assert result["any_nutrition_panel"] is True
    assert result["image_count"] == 2


def test_score_images_any_nutrition_panel_false_when_none(monkeypatch):
    """any_nutrition_panel is False when no image has contains_nutrition_panel=True."""
    scores = [
        {
            "url": "https://example.com/img1.jpg",
            "clarity": 3,
            "lifestyle": False,
            "label_legible": False,
            "overall": 3,
            "notes": "Blurry",
            "on_pack_text": "",
            "contains_nutrition_panel": False,
        }
    ]
    product = _make_product(["https://example.com/img1.jpg"])
    client = _make_gemini_client(json.dumps(scores))

    import healf_agent.tools.vision as _vision
    monkeypatch.setattr(_vision, "_fetch_image_bytes", lambda url, **kw: b"\xff\xd8\xff" + b"\x00" * 10)

    result = score_images(product=product, gemini_client=client)
    assert result["any_nutrition_panel"] is False
    assert result["aggregated_on_pack_text"] == ""
