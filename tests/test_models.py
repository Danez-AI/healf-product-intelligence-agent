from datetime import datetime
from healf_agent.models import (
    Product, Image, Review, ReviewTheme, EvalReport, RubricScore,
    ConsistencyFinding, ConsistencyReport, HITLEntry, Comparison,
)


def test_product_minimal_construction():
    p = Product(
        url="https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack",
        handle="lmnt-recharge-electrolytes-variety-pack",
        title="LMNT Recharge Electrolytes Variety Pack",
        brand="LMNT",
        product_type="Electrolytes",
        description="Tasty electrolytes...",
        price_gbp=45.0,
        currency="GBP",
        sku="LMNT-VARIETY-30",
        gid="gid://shopify/Product/7620180541679",
        images=[],
        ingredients=[],
        claims=[],
        rating_value=4.9,
        rating_count=445,
    )
    assert p.handle == "lmnt-recharge-electrolytes-variety-pack"
    assert p.rating_count == 445


def test_product_rejects_unknown_currency():
    import pydantic
    try:
        Product(
            url="https://healf.com/x",
            handle="x",
            title="x",
            brand="x",
            product_type="x",
            description="x",
            price_gbp=1.0,
            currency="XYZ",
            sku="x",
            gid="gid://shopify/Product/1",
            images=[],
            ingredients=[],
            claims=[],
            rating_value=None,
            rating_count=None,
        )
    except pydantic.ValidationError:
        return
    raise AssertionError("expected ValidationError for unknown currency")


def test_review_construction_and_polarity():
    r = Review(
        review_id="abc",
        product_gid="gid://shopify/Product/1",
        author="Alex",
        rating=2,
        title="Tart",
        body="Too sour for me",
        created_at=datetime(2025, 1, 1),
        verified=True,
    )
    assert r.polarity() == "negative"


def test_eval_report_average_score():
    rep = EvalReport(
        product_handle="x",
        scores=[
            RubricScore(axis="clarity", score=4, rationale="ok"),
            RubricScore(axis="depth", score=2, rationale="thin"),
        ],
        gaps=["missing serving size"],
        corpus_references=[],
    )
    assert rep.average() == 3.0


def test_product_collections_and_tags_round_trip():
    p = Product(
        url="https://healf.com/en-uk/products/biocare-vitamin-b12",
        handle="biocare-vitamin-b12",
        title="BioCare Vitamin B12",
        brand="BioCare",
        product_type="Vitamins & Supplements",
        description="Methylcobalamin B12.",
        price_gbp=14.89,
        currency="GBP",
        sku="BC-B12",
        gid="gid://shopify/Product/123",
        collections=["vitamin-b12", "vitamins-and-supplements", "eat"],
        tags=["B12", "energy", "vegan"],
    )
    assert p.collections == ["vitamin-b12", "vitamins-and-supplements", "eat"]
    assert p.tags == ["B12", "energy", "vegan"]
    dumped = p.model_dump(mode="json")
    restored = Product.model_validate(dumped)
    assert restored.collections == p.collections
    assert restored.tags == p.tags


def test_product_collections_defaults_to_empty():
    p = Product(
        url="https://healf.com/en-uk/products/some-product",
        handle="some-product",
        title="Some Product",
        brand="Brand",
        product_type="Unknown",
        description="",
        price_gbp=10.0,
        currency="GBP",
        sku="SP-1",
        gid="gid://shopify/Product/999",
    )
    assert p.collections == []
    assert p.tags == []
