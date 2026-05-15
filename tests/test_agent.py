from healf_agent.tools.field import check_field
from healf_agent.models import Product
from healf_agent.tools.compare import compare_products
from healf_agent.tools.act import draft_rewrite, enqueue_hitl


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


from healf_agent.tools.vision import score_images


def test_score_images_returns_scores_no_images() -> None:
    """Empty images list triggers early return."""
    fake_gemini = MagicMock()
    p = _p()  # images=[]
    result = score_images(product=p, gemini_client=fake_gemini)
    assert "image_scores" in result
    assert result["image_scores"] == []
    fake_gemini.models.generate_content.assert_not_called()


def test_score_images_calls_gemini_with_image_parts(monkeypatch) -> None:
    """With images, fetches bytes and calls Gemini multimodally."""
    from healf_agent.models import Image

    fake_gemini = MagicMock()
    fake_gemini.models.generate_content.return_value = MagicMock(
        text='[{"url": "https://cdn.shopify.com/x.jpg", "clarity": 4, "lifestyle": false, "label_legible": true, "overall": 4, "notes": "Clean pack shot"}]'
    )

    # Patch httpx so no real network call is made
    import healf_agent.tools.vision as vision_module
    monkeypatch.setattr(
        vision_module,
        "_fetch_image_bytes",
        lambda url, timeout=10.0: b"fakeimagebytes",
    )

    p = _p(images=[Image(url="https://cdn.shopify.com/x.jpg", alt="test")])
    result = score_images(product=p, gemini_client=fake_gemini)

    assert "image_scores" in result
    assert result["image_count"] == 1
    fake_gemini.models.generate_content.assert_called_once()


from healf_agent.tools.consistency import check_consistency


def test_check_consistency_flags_unsupported_claim(monkeypatch) -> None:
    fake_anthropic = MagicMock()
    fake_anthropic.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text='[{"kind": "claim_unsupported", "detail": "zero sugar claim not in ingredients", "evidence": "sugar-free not listed"}]')]
    )
    p = _p(claims=["zero sugar", "keto friendly"])
    from healf_agent.models import ConsistencyReport
    report = check_consistency(product=p, themes=[], anthropic_client=fake_anthropic)
    assert isinstance(report, ConsistencyReport)


def test_compare_products_returns_rows(monkeypatch) -> None:
    p1 = _p(handle="a", title="Product A", price_gbp=10.0, rating_value=4.5, rating_count=50)
    p2 = _p(handle="b", title="Product B", price_gbp=15.0, rating_value=4.0, rating_count=20)
    result = compare_products(products=[p1, p2])
    from healf_agent.models import Comparison
    assert isinstance(result, Comparison)
    assert len(result.rows) >= 1
    assert len(result.handles) == 2


def test_draft_rewrite_returns_string(monkeypatch) -> None:
    fake_anthropic = MagicMock()
    fake_anthropic.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text="Improved product description here.")]
    )
    p = _p()
    result = draft_rewrite(
        product=p,
        gaps=["add serving size", "mention electrolyte amounts"],
        anthropic_client=fake_anthropic,
    )
    assert isinstance(result, str)
    assert len(result) > 0


def test_enqueue_hitl_persists_to_storage(monkeypatch) -> None:
    import tempfile
    from pathlib import Path
    from healf_agent.storage import Storage

    tmp = Path(tempfile.mkdtemp()) / "test.sqlite"
    s = Storage(tmp)
    s.init_schema()
    p = _p()
    entry_id = enqueue_hitl(
        product=p,
        drafted_description="Better description.",
        gap_summary="Missing serving size.",
        storage=s,
    )
    assert isinstance(entry_id, int)
    row = s.conn.execute("SELECT * FROM hitl_queue WHERE id=?", (entry_id,)).fetchone()
    assert row is not None
