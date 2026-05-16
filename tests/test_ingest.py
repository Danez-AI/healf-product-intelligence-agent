from pathlib import Path

from healf_agent.tools.ingest import (
    extract_json_ld,
    extract_metafields,
    load_full_product,
    parse_product,
    _clean_metafield_text,
    _split_ingredient_blob,
)


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


def test_extract_metafields_returns_ingredients_from_lmnt_fixture() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    meta = extract_metafields(html)
    assert isinstance(meta, dict), "extract_metafields must return a dict"
    assert "ingredients" in meta, f"'ingredients' key missing from metafields; got keys: {list(meta.keys())}"
    assert "Salt (Sodium Chloride)" in meta["ingredients"], (
        f"Expected 'Salt (Sodium Chloride)' in ingredients metafield; got: {meta['ingredients'][:200]}"
    )


def test_extract_metafields_returns_multiple_keys() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    meta = extract_metafields(html)
    assert len(meta) >= 3, f"Expected at least 3 metafields; got {len(meta)}: {list(meta.keys())}"


def test_clean_metafield_text_converts_br_and_entities() -> None:
    assert _clean_metafield_text("A<br>B&amp;C") == "A\nB&C"
    assert _clean_metafield_text("Hello<br/>World") == "Hello\nWorld"
    assert _clean_metafield_text("") == ""


def test_load_full_product_populates_ingredients_and_metafields(monkeypatch) -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    # Patch on the source module — load_full_product uses a local import from navigate
    import healf_agent.tools.navigate as _nav
    monkeypatch.setattr(_nav, "fetch_product_page", lambda url: html)
    product = load_full_product("https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack")
    assert isinstance(product.raw_metafields, dict), "raw_metafields must be a dict"
    assert len(product.raw_metafields) >= 3, f"expected >=3 metafields; got {list(product.raw_metafields.keys())}"
    assert product.ingredients, "ingredients must be non-empty"
    assert any("sodium chloride" in i.lower() for i in product.ingredients), (
        f"Salt (Sodium Chloride) not found in ingredients: {product.ingredients[:5]}"
    )


def test_split_ingredient_blob_flat_and_deduplicated() -> None:
    blob = (
        "Citrus:\n"
        "Salt (Sodium Chloride), Citric Acid, Magnesium Malate, Potassium Chloride\n"
        "Mango Chili:\n"
        "Salt (Sodium Chloride), Citric Acid, Magnesium Malate, Potassium Chloride\n"
    )
    items = _split_ingredient_blob(blob)
    assert "Salt (Sodium Chloride)" in items
    assert items[0] == "Salt (Sodium Chloride)"
    # Duplicates across flavours must be collapsed
    assert items.count("Salt (Sodium Chloride)") == 1
    # Flavour headers must not appear as ingredients
    assert not any(":" in i and len(i) < 30 and i.endswith(":") for i in items)
