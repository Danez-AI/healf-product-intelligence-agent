from unittest.mock import MagicMock, patch
from datetime import datetime

from healf_agent.models import Review, ReviewTheme
from healf_agent.tools.review_themes import cluster_review_themes


def _make_reviews(n: int, rating: int = 5) -> list[Review]:
    return [
        Review(
            review_id=f"r{i}",
            product_gid="gid://shopify/Product/1",
            author=f"User{i}",
            rating=rating,
            body=f"This product is great sample review number {i}",
            verified=True,
        )
        for i in range(n)
    ]


def test_cluster_review_themes_returns_themes_list(monkeypatch) -> None:
    reviews = _make_reviews(10, rating=5)

    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1] * 128) for _ in range(10)]
    )

    fake_anthropic = MagicMock()
    fake_anthropic.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text='[{"label": "Great taste", "summary": "Users love the taste", "polarity": "positive"}]')]
    )

    themes = cluster_review_themes(
        reviews=reviews,
        product_gid="gid://shopify/Product/1",
        openai_client=fake_openai,
        anthropic_client=fake_anthropic,
        min_cluster_size=2,
    )
    assert isinstance(themes, list)
    assert len(themes) >= 1
    assert all(isinstance(t, ReviewTheme) for t in themes)


def test_cluster_review_themes_returns_empty_for_few_reviews() -> None:
    reviews = _make_reviews(2)
    fake_openai = MagicMock()
    fake_anthropic = MagicMock()
    themes = cluster_review_themes(
        reviews=reviews,
        product_gid="gid://shopify/Product/1",
        openai_client=fake_openai,
        anthropic_client=fake_anthropic,
        min_reviews=5,
    )
    assert themes == []
