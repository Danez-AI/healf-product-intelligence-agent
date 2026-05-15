from pathlib import Path

from healf_agent.tools.ingest import extract_json_ld, extract_metafields, parse_product


FIXTURE = Path("tests/fixtures/lmnt-recharge-electrolytes-variety-pack.html")


def test_extract_jsonld_finds_product_schema() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    blocks = extract_json_ld(html)
    products = [b for b in blocks if b.get("@type") == "Product"]
    assert products, "expected at least one Product JSON-LD block"
    # The product name is "Recharge Electrolytes - Variety Pack"; brand is "LMNT"
    brand = products[0].get("brand") or {}
    brand_name = brand.get("name") if isinstance(brand, dict) else str(brand)
    assert brand_name and brand_name.lower() == "lmnt"


def test_parse_product_lmnt_fixture() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    p = parse_product(
        html,
        url="https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack",
    )
    assert p.handle == "lmnt-recharge-electrolytes-variety-pack"
    assert p.brand.lower() == "lmnt"
    assert p.gid.startswith("gid://shopify/Product/")
    assert p.rating_value and p.rating_value > 4.5
    assert p.rating_count and p.rating_count >= 100
    assert len(p.images) >= 1


def test_extract_metafields_pulls_ingredients_when_present() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    meta = extract_metafields(html)
    # We don't assert exact shape (LMNT may or may not have ingredient metafield),
    # but the function must return a dict and not raise.
    assert isinstance(meta, dict)
