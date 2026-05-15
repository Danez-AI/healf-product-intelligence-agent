"""Tests for healf_agent.voice — pure prompt-template assertions, no API calls."""
from healf_agent.voice import HEALF_VOICE, REWRITE_SYSTEM, build_rewrite_prompt
from healf_agent.models import Product, Image


def _make_product(**overrides) -> Product:
    base = dict(
        url="https://healf.com/en-uk/products/lmnt-recharge",
        handle="lmnt-recharge",
        title="LMNT Recharge Electrolytes",
        brand="LMNT",
        product_type="Electrolytes",
        description="A tasty electrolyte drink mix.",
        price_gbp=18.99,
        currency="GBP",
        sku="LMNT-001",
        gid="gid://shopify/Product/7620180541679",
        images=[],
        ingredients=["sodium", "potassium", "magnesium"],
        claims=["zero sugar"],
        rating_value=4.9,
        rating_count=445,
    )
    base.update(overrides)
    return Product(**base)


def test_healf_voice_contains_british_english_signal() -> None:
    assert "British English" in HEALF_VOICE


def test_rewrite_system_starts_with_role() -> None:
    assert REWRITE_SYSTEM.startswith("You are")


def test_build_rewrite_prompt_includes_product_title_and_gaps() -> None:
    p = _make_product()
    prompt = build_rewrite_prompt(p, "- Missing sodium amount")
    assert p.title in prompt
    assert "Missing sodium amount" in prompt
    assert "150" in prompt


def test_build_rewrite_prompt_truncates_long_description() -> None:
    long_desc = "x" * 700
    p = _make_product(description=long_desc)
    prompt = build_rewrite_prompt(p, "gap")
    # The full 700-char string should NOT appear — truncated to 600
    assert "x" * 601 not in prompt
