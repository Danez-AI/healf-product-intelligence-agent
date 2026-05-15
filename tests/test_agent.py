from healf_agent.tools.field import check_field
from healf_agent.models import Product


def _p(**overrides) -> Product:
    base = dict(
        url="https://healf.com/en-uk/products/x",
        handle="x",
        title="X",
        brand="X",
        product_type="Electrolytes",
        description="Tasty electrolytes.",
        price_gbp=1.0,
        currency="GBP",
        sku="x",
        gid="gid://shopify/Product/1",
        images=[],
        ingredients=["sodium", "potassium"],
        claims=["zero sugar"],
        rating_value=4.5,
        rating_count=10,
    )
    base.update(overrides)
    return Product(**base)


def test_check_field_finds_ingredient_when_present() -> None:
    p = _p()
    out = check_field(p, field="ingredient", value="sodium")
    assert out["present"] is True


def test_check_field_misses_ingredient_when_absent() -> None:
    p = _p()
    out = check_field(p, field="ingredient", value="vitamin d")
    assert out["present"] is False


def test_tool_schemas_advertise_check_field() -> None:
    from healf_agent.tools import TOOL_SCHEMAS

    names = {t["name"] for t in TOOL_SCHEMAS}
    assert "check_field" in names


def test_dispatch_check_field_returns_dict(monkeypatch) -> None:
    from healf_agent.tools import dispatch_tool

    p = _p()  # reuses helper defined at top of this file
    out = dispatch_tool(
        name="check_field",
        arguments={"field": "ingredient", "value": "sodium"},
        product=p,
    )
    assert out["present"] is True
