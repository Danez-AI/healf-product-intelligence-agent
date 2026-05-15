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


from unittest.mock import MagicMock

from healf_agent.agent import run_agent_turn


def test_agent_loop_dispatches_tool_then_finalises() -> None:
    fake_client = MagicMock()

    # Turn 1: model asks to call check_field
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.id = "tu_1"
    tool_use_block.name = "check_field"
    tool_use_block.input = {"field": "ingredient", "value": "sodium"}
    fake_client.messages.create.side_effect = [
        MagicMock(stop_reason="tool_use", content=[tool_use_block]),
        MagicMock(
            stop_reason="end_turn",
            content=[MagicMock(type="text", text="Yes, sodium is listed.")],
        ),
    ]

    p = _p()
    answer, trace = run_agent_turn(
        client=fake_client,
        model="claude-sonnet-4-6",
        system="be useful",
        user_message="does this have sodium?",
        product=p,
    )
    assert "sodium" in answer.lower()
    assert any(step["tool"] == "check_field" for step in trace)


from healf_agent.tools.benchmark import benchmark_against_category


def test_benchmark_returns_neighbours(monkeypatch) -> None:
    from healf_agent.storage import Storage
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp()) / "c.sqlite"
    s = Storage(tmp)
    s.init_schema()
    for i in range(3):
        s.upsert_corpus_entry(
            handle=f"prod-{i}",
            product_type="Unknown",
            title=f"Product {i}",
            text=f"Description of product {i}",
            embedding=[0.1 + i * 0.01] * 8,
        )

    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1] * 8)]
    )

    result = benchmark_against_category(
        product=_p(),
        storage=s,
        openai_client=fake_openai,
        k=3,
    )
    assert "neighbours" in result
    assert len(result["neighbours"]) <= 3


from healf_agent.tools.evaluate import evaluate_listing_quality


def test_evaluate_listing_quality_returns_eval_report(monkeypatch) -> None:
    fake_anthropic = MagicMock()
    fake_anthropic.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text='''{
  "scores": [
    {"axis": "completeness", "score": 3, "rationale": "Missing serving size"},
    {"axis": "differentiation", "score": 4, "rationale": "Good brand story"}
  ],
  "gaps": ["Add serving size info", "Add ingredient amounts"]
}''')]
    )
    p = _p()
    report = evaluate_listing_quality(
        product=p,
        neighbours=[{"handle": "x", "title": "X", "excerpt": "Great product."}],
        themes=[],
        anthropic_client=fake_anthropic,
    )
    from healf_agent.models import EvalReport
    assert isinstance(report, EvalReport)
    assert report.average() > 0
    assert len(report.gaps) >= 1
