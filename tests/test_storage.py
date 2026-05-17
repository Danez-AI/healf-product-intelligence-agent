import json
import tempfile
import time
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


def test_corpus_upsert_with_collections(storage: Storage) -> None:
    storage.upsert_corpus_entry(
        handle="biocare-vitamin-b12",
        product_type="Vitamins & Supplements",
        title="BioCare Vitamin B12",
        text="Methylcobalamin B12 supplement.",
        embedding=[0.5] * 1536,
        collections=["vitamin-b12", "eat"],
    )
    import json
    row = storage.conn.execute(
        "SELECT collections FROM corpus WHERE handle='biocare-vitamin-b12'"
    ).fetchone()
    assert row is not None
    assert json.loads(row["collections"]) == ["vitamin-b12", "eat"]


def test_knn_collection_filter_ranks_overlap_first(storage: Storage) -> None:
    # Three products with different collection memberships
    # biocare-b12: shares "vitamin-b12" with query
    storage.upsert_corpus_entry(
        handle="biocare-b12",
        product_type="Vitamins & Supplements",
        title="BioCare B12",
        text="B12 supplement",
        embedding=[1.0, 0.0] + [0.0] * 1534,
        collections=["vitamin-b12", "eat"],
    )
    # thorne-b12: also in vitamin-b12 collection
    storage.upsert_corpus_entry(
        handle="thorne-b12",
        product_type="Vitamins & Supplements",
        title="Thorne B12",
        text="Thorne methylcobalamin",
        embedding=[0.9, 0.1] + [0.0] * 1534,
        collections=["vitamin-b12"],
    )
    # magnesium: same product_type but no collection overlap
    storage.upsert_corpus_entry(
        handle="magnesium-glycinate",
        product_type="Vitamins & Supplements",
        title="Magnesium Glycinate",
        text="Magnesium supplement for sleep",
        embedding=[0.8, 0.2] + [0.0] * 1534,
        collections=["magnesium", "sleep"],
    )

    # Query with collection_filter={"vitamin-b12"}
    results = storage.knn(
        product_type="Vitamins & Supplements",
        query_vec=[1.0, 0.0] + [0.0] * 1534,
        k=3,
        collection_filter={"vitamin-b12"},
    )
    result_handles = [r["handle"] for r in results]
    # Collection-overlap products must appear before magnesium (no overlap)
    assert "biocare-b12" in result_handles
    assert "thorne-b12" in result_handles
    # magnesium appears only as fallback top-up (after the 2 collection hits)
    overlap_idx = [result_handles.index(h) for h in ("biocare-b12", "thorne-b12") if h in result_handles]
    if "magnesium-glycinate" in result_handles:
        magnesium_idx = result_handles.index("magnesium-glycinate")
        assert all(magnesium_idx > i for i in overlap_idx)


def test_knn_collection_filter_empty_falls_back_to_type(storage: Storage) -> None:
    storage.upsert_corpus_entry(
        handle="whey-protein",
        product_type="Protein",
        title="Whey Protein",
        text="High quality whey",
        embedding=[0.3] * 1536,
        collections=["protein"],
    )
    # Filter with non-overlapping collection — should fall through to product_type
    results = storage.knn(
        product_type="Protein",
        query_vec=[0.3] * 1536,
        k=1,
        collection_filter={"vitamin-b12"},
    )
    assert results[0]["handle"] == "whey-protein"


def test_init_schema_is_idempotent(storage: Storage) -> None:
    storage.init_schema()
    storage.init_schema()  # should not raise


# ---- HITL CRUD tests ----

def _insert_hitl(storage: Storage, product_handle: str = "lmnt", created_at: float | None = None) -> int:
    """Insert a HITL row directly and return its id."""
    ts = created_at if created_at is not None else time.time()
    cursor = storage.conn.execute(
        "INSERT INTO hitl_queue(product_handle, original_description, drafted_description, gap_summary, status, created_at) "
        "VALUES(?,?,?,?,?,?)",
        (product_handle, "Original description.", "Drafted description.", "Missing sodium.", "pending", ts),
    )
    storage.conn.commit()
    return cursor.lastrowid


def test_list_hitl_returns_newest_first(storage: Storage) -> None:
    now = time.time()
    _insert_hitl(storage, product_handle="prod-a", created_at=now - 10)
    _insert_hitl(storage, product_handle="prod-b", created_at=now)
    entries = storage.list_hitl(status="pending")
    assert len(entries) == 2
    # Newest (higher created_at) comes first
    assert entries[0].created_at > entries[1].created_at


def test_update_hitl_sets_reviewed_at(storage: Storage) -> None:
    entry_id = _insert_hitl(storage)
    storage.update_hitl(entry_id, status="approved", reviewer_note="LGTM")
    entry = storage.get_hitl(entry_id)
    assert entry is not None
    assert entry.status == "approved"
    assert entry.reviewer_note == "LGTM"
    assert entry.reviewed_at is not None


def test_update_hitl_edit_overwrites_drafted_description(storage: Storage) -> None:
    entry_id = _insert_hitl(storage)
    storage.update_hitl(entry_id, status="edited", drafted_description="Revised copy")
    entry = storage.get_hitl(entry_id)
    assert entry is not None
    assert entry.drafted_description == "Revised copy"
    assert entry.status == "edited"
    assert entry.reviewed_at is not None


# ---- chat session CRUD tests ----

def test_create_and_list_chat_sessions(storage: Storage) -> None:
    id1 = storage.create_chat_session("Session one", product_handle="lmnt")
    id2 = storage.create_chat_session("Session two")
    sessions = storage.list_recent_sessions(5)
    assert len(sessions) == 2
    # Most recent (id2) should be first
    assert sessions[0]["id"] == id2
    assert sessions[1]["id"] == id1
    assert sessions[1]["product_handle"] == "lmnt"


def test_append_chat_message_persists_and_bumps_updated_at(storage: Storage) -> None:
    sid = storage.create_chat_session("Test chat")
    # Grab the initial updated_at
    initial_updated = storage.conn.execute(
        "SELECT updated_at FROM chat_sessions WHERE id=?", (sid,)
    ).fetchone()["updated_at"]

    import time; time.sleep(0.01)
    storage.append_chat_message(sid, "user", "Hello agent")
    storage.append_chat_message(sid, "assistant", "Hello!", trace={"tool": "none"}, debug={"system": "sys"})

    msgs = storage.get_session_messages(sid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["text"] == "Hello agent"
    assert msgs[1]["trace"] == {"tool": "none"}
    assert msgs[1]["debug"] == {"system": "sys"}

    new_updated = storage.conn.execute(
        "SELECT updated_at FROM chat_sessions WHERE id=?", (sid,)
    ).fetchone()["updated_at"]
    assert new_updated > initial_updated


def test_update_session_title(storage: Storage) -> None:
    sid = storage.create_chat_session("New conversation")
    storage.update_session_title(sid, "LMNT claims audit")
    sessions = storage.list_recent_sessions(1)
    assert sessions[0]["title"] == "LMNT claims audit"
