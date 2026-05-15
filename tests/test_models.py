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
