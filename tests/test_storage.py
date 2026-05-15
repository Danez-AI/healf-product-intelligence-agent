import json
import tempfile
from pathlib import Path

import pytest

from healf_agent.models import Image, Product, Review
from healf_agent.storage import Storage


@pytest.fixture()
def storage() -> Storage:
    tmp = Path(tempfile.mkdtemp()) / "test.sqlite"
    s = Storage(tmp)
    s.init_schema()
    return s


def _make_product(handle: str = "lmnt-recharge-electrolytes-variety-pack") -> Product:
    return Product(
        url=f"https://healf.com/en-uk/products/{handle}",
        handle=handle,
        title="LMNT Recharge Electrolytes Variety Pack",
        brand="LMNT",
        product_type="Electrolytes",
        description="A pack of tasty electrolytes.",
        price_gbp=45.0,
        currency="GBP",
        sku="LMNT-VARIETY-30",
        gid="gid://shopify/Product/7620180541679",
        images=[Image(url="https://cdn.shopify.com/x.jpg", alt="LMNT")],
        ingredients=["sodium", "potassium", "magnesium"],
        claims=["zero sugar", "no artificial colors"],
        rating_value=4.9,
        rating_count=445,
    )


def test_product_round_trip(storage: Storage) -> None:
    p = _make_product()
    storage.upsert_product(p)
    fetched = storage.get_product(p.handle)
    assert fetched is not None
    assert fetched.gid == p.gid
    assert fetched.images[0].alt == "LMNT"
    assert fetched.ingredients == ["sodium", "potassium", "magnesium"]


def test_review_round_trip(storage: Storage) -> None:
    p = _make_product()
    storage.upsert_product(p)
    r = Review(
        review_id="rev-1",
        product_gid=p.gid,
        author="Alex",
        rating=4,
        title="Solid",
        body="Tastes good and works",
    )
    storage.upsert_reviews([r])
    fetched = storage.get_reviews(p.gid)
    assert len(fetched) == 1
    assert fetched[0].review_id == "rev-1"


def test_corpus_round_trip(storage: Storage) -> None:
    storage.upsert_corpus_entry(
        handle="creatine-monohydrate",
        product_type="Supplements",
        title="Creatine Monohydrate",
        text="Pure creatine monohydrate, micronised.",
        embedding=[0.1] * 1536,
    )
    near = storage.knn(product_type="Supplements", query_vec=[0.1] * 1536, k=1)
    assert near[0]["handle"] == "creatine-monohydrate"


def test_init_schema_is_idempotent(storage: Storage) -> None:
    storage.init_schema()
    storage.init_schema()  # should not raise
