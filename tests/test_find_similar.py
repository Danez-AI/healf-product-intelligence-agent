"""Tests for find_similar_products tool and its dispatch registration."""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from healf_agent.models import Product
from healf_agent.storage import Storage
from healf_agent.tools import TOOL_SCHEMAS
from healf_agent.tools.find_similar import find_similar_products


@pytest.fixture()
def storage() -> Storage:
    tmp = Path(tempfile.mkdtemp()) / "corpus.sqlite"
    s = Storage(tmp)
    s.init_schema()
    return s


def _make_product(handle: str, collections: list[str], vec_seed: float) -> Product:
    return Product(
        url=f"https://healf.com/en-uk/products/{handle}",
        handle=handle,
        title=handle.replace("-", " ").title(),
        brand="TestBrand",
        product_type="Vitamins & Supplements",
        description="A test supplement.",
        price_gbp=15.0,
        currency="GBP",
        sku=handle,
        gid=f"gid://shopify/Product/{hash(handle) % 100000}",
        collections=collections,
    )


def _seed_corpus(storage: Storage) -> None:
    entries = [
        ("thorne-vitamin-b12", ["vitamin-b12"], [0.9, 0.1] + [0.0] * 1534),
        ("vimergy-liquid-b12", ["vitamin-b12", "liquids"], [0.85, 0.15] + [0.0] * 1534),
        ("magnesium-glycinate", ["magnesium", "sleep"], [0.3, 0.7] + [0.0] * 1534),
    ]
    for handle, colls, vec in entries:
        storage.upsert_corpus_entry(
            handle=handle,
            product_type="Vitamins & Supplements",
            title=handle.replace("-", " ").title(),
            text=f"Test text for {handle}",
            embedding=vec,
            collections=colls,
        )


def _mock_openai(vec: list[float]):
    client = MagicMock()
    embedding = MagicMock()
    embedding.embedding = vec
    client.embeddings.create.return_value = MagicMock(data=[embedding])
    return client


def test_find_similar_returns_candidate_urls(storage: Storage) -> None:
    _seed_corpus(storage)
    product = _make_product("biocare-vitamin-b12", ["vitamin-b12"], 0.9)
    openai_client = _mock_openai([1.0, 0.0] + [0.0] * 1534)

    result = find_similar_products(
        product=product,
        storage=storage,
        openai_client=openai_client,
        k=3,
    )

    assert result["product_handle"] == "biocare-vitamin-b12"
    candidates = result["candidates"]
    assert len(candidates) >= 1
    for c in candidates:
        assert "handle" in c
        assert "title" in c
        assert c["product_url"].startswith("https://healf.com/en-uk/products/")
        assert "shared_collections" in c
        assert "score" in c
        # Current product must not appear in its own candidates
        assert c["handle"] != "biocare-vitamin-b12"


def test_find_similar_collection_overlap_products_appear(storage: Storage) -> None:
    _seed_corpus(storage)
    product = _make_product("biocare-vitamin-b12", ["vitamin-b12"], 0.9)
    openai_client = _mock_openai([1.0, 0.0] + [0.0] * 1534)

    result = find_similar_products(product=product, storage=storage, openai_client=openai_client, k=6)
    handles = [c["handle"] for c in result["candidates"]]

    # Both vitamin-b12 peers should surface before magnesium
    assert "thorne-vitamin-b12" in handles
    assert "vimergy-liquid-b12" in handles


def test_find_similar_shared_collections_populated(storage: Storage) -> None:
    _seed_corpus(storage)
    product = _make_product("biocare-vitamin-b12", ["vitamin-b12"], 0.9)
    openai_client = _mock_openai([1.0, 0.0] + [0.0] * 1534)

    result = find_similar_products(product=product, storage=storage, openai_client=openai_client, k=3)
    thorne = next((c for c in result["candidates"] if c["handle"] == "thorne-vitamin-b12"), None)
    assert thorne is not None
    assert "vitamin-b12" in thorne["shared_collections"]


def test_find_similar_ignores_generic_collections(storage: Storage) -> None:
    """Generic site-wide collections must not dominate the candidate pool."""
    # Seed: 3 B12 peers + 2 unrelated products all sharing a bloated collection.
    bloated = ["all-products"] * 1  # one collection shared by many
    b12_cols = ["vitamin-b12"]
    entries = [
        ("thorne-b12", b12_cols, [0.9, 0.1] + [0.0] * 1534),
        ("vimergy-b12", b12_cols, [0.85, 0.15] + [0.0] * 1534),
        ("random-protein", bloated, [0.1, 0.9] + [0.0] * 1534),
        ("random-sleep", bloated, [0.05, 0.95] + [0.0] * 1534),
    ]
    for h, c, v in entries:
        storage.upsert_corpus_entry(handle=h, product_type="T", title=h, text=h, embedding=v, collections=c)
    # Also add "all-products" to the 2 b12 peers so the generic collection is shared
    # but vitamin-b12 remains the specific one (2 members vs 4 for all-products).
    # With _MAX_COLLECTION_SIZE=200, all collections in this tiny DB are specific.
    # The key assertion: b12 peers surface over random products.
    product = _make_product("biocare-b12", ["vitamin-b12", "all-products"], 0.9)
    openai_client = _mock_openai([1.0, 0.0] + [0.0] * 1534)
    result = find_similar_products(product=product, storage=storage, openai_client=openai_client, k=4)
    handles = [c["handle"] for c in result["candidates"]]
    assert "thorne-b12" in handles
    assert "vimergy-b12" in handles


def test_find_similar_excludes_same_brand_saturation(storage: Storage) -> None:
    """Per-brand cap must surface cross-brand peers even when many same-brand SKUs
    have higher cosine similarity than cross-brand alternatives."""
    biocare_cols = ["biocare", "vitamin-b12", "b-vitamins"]
    for i in range(10):
        storage.upsert_corpus_entry(
            handle=f"biocare-b-vitamin-sku-{i}",
            product_type="Vitamins & Supplements",
            title=f"BioCare B Vitamin {i}",
            text=f"BioCare supplement {i}",
            embedding=[0.95, 0.31] + [0.0] * 1534,
            collections=biocare_cols,
        )
    for handle, vec in [
        ("thorne-vitamin-b12", [0.7, 0.714] + [0.0] * 1534),
        ("vimergy-liquid-b12", [0.65, 0.76] + [0.0] * 1534),
    ]:
        storage.upsert_corpus_entry(
            handle=handle,
            product_type="Vitamins & Supplements",
            title=handle.replace("-", " ").title(),
            text=f"Test text for {handle}",
            embedding=vec,
            collections=["vitamin-b12", "b-vitamins"],
        )

    product = Product(
        url="https://healf.com/en-uk/products/biocare-vitamin-b12",
        handle="biocare-vitamin-b12",
        title="BioCare Vitamin B12",
        brand="BioCare",
        product_type="Vitamins & Supplements",
        description="BioCare Vitamin B12 capsule.",
        price_gbp=14.89,
        currency="GBP",
        sku="biocare-vitamin-b12",
        gid="gid://shopify/Product/12345",
        collections=["biocare", "vitamin-b12", "b-vitamins"],
    )
    openai_client = _mock_openai([1.0, 0.0] + [0.0] * 1534)

    result = find_similar_products(product=product, storage=storage, openai_client=openai_client, k=6)
    handles = [c["handle"] for c in result["candidates"]]

    biocare_count = sum(1 for h in handles if h.startswith("biocare-"))
    assert biocare_count <= 2, f"Too many BioCare SKUs in candidates: {handles}"
    assert any(h in handles for h in ("thorne-vitamin-b12", "vimergy-liquid-b12")), (
        f"No cross-brand peer surfaced: {handles}"
    )


def test_find_similar_products_registered_in_tool_schemas() -> None:
    names = [t["name"] for t in TOOL_SCHEMAS]
    assert "find_similar_products" in names
    schema = next(t for t in TOOL_SCHEMAS if t["name"] == "find_similar_products")
    assert "k" in schema["input_schema"]["properties"]
