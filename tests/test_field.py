"""Tests for check_field tri-state logic."""
from healf_agent.tools.field import check_field
from healf_agent.models import Product


def _p(**overrides) -> Product:
    base = dict(
        url="https://healf.com/en-uk/products/x",
        handle="x",
        title="X",
        brand="Healf",
        product_type="Electrolytes",
        description="Test product.",
        price_gbp=9.99,
        currency="GBP",
        sku="x",
        gid="gid://shopify/Product/1",
        images=[],
        ingredients=[],
        claims=[],
        rating_value=4.0,
        rating_count=10,
    )
    base.update(overrides)
    return Product(**base)


def test_check_field_ingredient_present_true() -> None:
    p = _p(ingredients=["Salt (Sodium Chloride)", "Citric Acid"], raw_metafields={"ingredients": "..."})
    out = check_field(p, field="ingredient", value="sodium")
    assert out["present"] is True
    assert out["extraction_status"] == "ok"


def test_check_field_ingredient_present_false_when_extraction_succeeded() -> None:
    # raw_metafields set (extraction ran) but ingredient list is empty → confidently False
    p = _p(ingredients=[], raw_metafields={})
    out = check_field(p, field="ingredient", value="vitamin d")
    assert out["present"] is False
    assert out["extraction_status"] == "ok"


def test_check_field_ingredient_present_none_when_no_metafields() -> None:
    # raw_metafields is None (extraction never ran) and no ingredients → cannot assert absence
    p = _p(ingredients=[], raw_metafields=None)
    out = check_field(p, field="ingredient", value="sodium")
    assert out["present"] is None
    assert out["extraction_status"] == "no_metafields"


def test_check_field_unknown_field_returns_none() -> None:
    p = _p()
    out = check_field(p, field="nonexistent_field", value="")
    assert out["present"] is None
    assert out["extraction_status"] == "unknown_field"


def test_check_field_brand_match() -> None:
    p = _p(brand="LMNT")
    out = check_field(p, field="brand", value="lmnt")
    assert out["present"] is True


def test_check_field_rating_returns_values() -> None:
    p = _p(rating_value=4.9, rating_count=445)
    out = check_field(p, field="rating", value="")
    assert out["value"] == 4.9
    assert out["count"] == 445


def test_check_field_claim_present_none_when_no_metafields() -> None:
    p = _p(claims=[], raw_metafields=None)
    out = check_field(p, field="claim", value="zero sugar")
    assert out["present"] is None
    assert out["extraction_status"] == "no_metafields"


def test_check_field_ingredient_per_flavour_for_malic_acid() -> None:
    by_flav = {"Citrus": ["Citric Acid", "Salt (Sodium Chloride)"], "Watermelon": ["Malic Acid", "Salt (Sodium Chloride)"]}
    flat = ["Citric Acid", "Malic Acid", "Salt (Sodium Chloride)"]
    p = _p(ingredients=flat, raw_metafields={"ingredients": "..."}, ingredients_by_flavour=by_flav)
    out = check_field(p, field="ingredient", value="malic acid")
    assert out["present"] is True
    assert out["per_flavour"] == ["Watermelon"]
    assert set(out["all_flavours"]) == {"Citrus", "Watermelon"}


def test_check_field_ingredient_per_flavour_for_citric_acid() -> None:
    by_flav = {"Citrus": ["Citric Acid", "Salt (Sodium Chloride)"], "Watermelon": ["Malic Acid", "Salt (Sodium Chloride)"]}
    flat = ["Citric Acid", "Malic Acid", "Salt (Sodium Chloride)"]
    p = _p(ingredients=flat, raw_metafields={"ingredients": "..."}, ingredients_by_flavour=by_flav)
    out = check_field(p, field="ingredient", value="citric acid")
    assert out["present"] is True
    assert out["per_flavour"] == ["Citrus"]
    assert set(out["all_flavours"]) == {"Citrus", "Watermelon"}
