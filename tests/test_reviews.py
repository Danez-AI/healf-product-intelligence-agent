import httpx
import respx

from healf_agent.tools.reviews import fetch_reviews_full


YOTPO_BASE = "https://api.yotpo.com/v1/widget"


def _page(page: int, per_page: int, total: int) -> dict:
    start = (page - 1) * per_page
    items = [
        {
            "id": f"rev-{i}",
            "score": 5 if i % 2 == 0 else 3,
            "title": f"Title {i}",
            "content": f"Body {i}",
            "user": {"display_name": f"User {i}"},
            "created_at": "2025-01-01T00:00:00Z",
            "verified_buyer": True,
        }
        for i in range(start, min(start + per_page, total))
    ]
    return {
        "response": {
            "bottomline": {"total_review": total, "average_score": 4.5},
            "reviews": items,
            "pagination": {"page": page, "per_page": per_page, "total": total},
        }
    }


@respx.mock
def test_fetch_reviews_full_paginates() -> None:
    app_key = "TEST_KEY"
    product_id = "7620180541679"
    url = f"{YOTPO_BASE}/{app_key}/products/{product_id}/reviews.json"
    respx.get(url, params={"page": 1, "per_page": 50}).mock(
        return_value=httpx.Response(200, json=_page(1, 50, 75))
    )
    respx.get(url, params={"page": 2, "per_page": 50}).mock(
        return_value=httpx.Response(200, json=_page(2, 50, 75))
    )
    reviews = fetch_reviews_full(
        product_gid=f"gid://shopify/Product/{product_id}",
        app_key=app_key,
        per_page=50,
    )
    assert len(reviews) == 75
    assert reviews[0].review_id == "rev-0"
    assert reviews[-1].review_id == "rev-74"
