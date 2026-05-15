# Healf Product Intelligence Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a natural-language agent for Healf (UK health & wellness Shopify marketplace) that, given a product URL and a plain-English question, returns a useful, grounded answer — backed by an ingestion layer, a site-wide corpus, multimodal evaluation, an HITL queue, an MCP surface, and an n8n catalog-audit companion workflow.

**Architecture:** Anthropic-SDK tool-using agent (Claude Sonnet 4.6) with 12 tools spanning Navigate / Ingest / Evaluate / Act, fronted by three surfaces (Streamlit chat, MCP server over stdio/SSE, FastAPI webhook), backed by SQLite for caching + corpus + HITL queue + eval runs. Tools are wired via Anthropic tool-use schemas; the model decides which to call per question. Tool traces are surfaced in the UI for debuggability.

**Tech Stack:** Python 3.11 · `uv` · Anthropic SDK (`claude-sonnet-4-6`) · Pydantic v2 · `httpx` · `selectolax` · `playwright` (fallback) · `openai` (embeddings) · `google-genai` (vision) · `numpy` (kNN) · `hdbscan` + `scikit-learn` (clustering) · `streamlit` · `fastmcp` · `fastapi` + `uvicorn` · `sqlite3` · `pytest` + `pytest-asyncio` · n8n (workflow JSON).

**Plan location:** This file lives at `C:\Users\Daran\.claude\plans\i-applied-to-a-delegated-finch.md` during plan-mode review. First execution step copies it to the project repo as `docs/superpowers/plans/2026-05-15-healf-product-intelligence-agent.md`.

**Plan series:** This is **Plan 1 of 4** — covers Tier 1 (foundation, waves 0–5) in TDD detail. Plans 2/3/4 (Tier 2 analytical depth, Tier 3 surfaces + companion, Tier 4 polish) will be authored at the start of each tier so they reflect what was actually built. Tier 2–4 outlines are at the bottom of this file as design anchors.

---

## Context

**The ask** (from `AI Automation - Assignment.pdf`): build a working MVP of a natural-language agent for Healf. Required capabilities: **Navigate / Ingest / Evaluate / Act**. At least one capability must use an LLM for reasoning. The role is on Healf's "AI Transformation Team" — they frame AI agents as "functional colleagues, each with their own capabilities, tools, and documentation." The implicit test signals: (a) discover Healf's structured data sources, (b) understand the broader site context, not just one page, (c) what you choose to include in the MVP vs. roadmap is itself part of the test.

**User constraint update:** the original 5-hour budget has been removed. The submission target is now "believable working colleague for the AI Transformation Team," not just a four-capability checkbox.

**Verified probes against the live site** (done before this plan was written):

| Probe | Finding | Implication |
|---|---|---|
| `/products/<handle>.json` | Returns HTML (404 wrapped) | Healf is **Next.js App Router** custom storefront — not vanilla Shopify. |
| PDP HTML | `<script type="application/ld+json">` with full `Product` schema (title, brand, description, image[], offers, aggregateRating, ~10 embedded `Review` objects) | **JSON-LD is the clean structured ingestion path.** |
| PDP HTML | Next.js RSC flight payload (`self.__next_f.push(...)`) with `handle`, `ingredient`, `metafield` fields | **Secondary ingestion path** for ingredient text + metafields. |
| Review widget | Yotpo signatures present | Public Yotpo widget API (`api.yotpo.com/v1/widget/<appKey>/products/<productId>/reviews.json`) for full review corpus + pagination. |
| `sitemap.xml` | Lists `sitemap-products.xml`, `sitemap-collections.xml`, `sitemap-articles.xml`, `sitemap-pages.xml` | **Corpus path** — stratified sample of products to build the "implicit standards" benchmark. |
| PDP HTML | Feature flag `ai-generated-reviews` (internal A/B test) | Healf is already experimenting with AI on this exact problem — submission must feel adjacent to their roadmap. |
| Reference product: `https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack` | 200 OK, JSON-LD parsed, aggregateRating: 4.9 / 445, 10 embedded reviews, Shopify GID `7620180541679` | Acts as our golden fixture for tests. |

---

## Architecture

```
                       ┌──────────────────────────────────────────────┐
                       │  Surfaces (3 ways to talk to the same agent) │
                       │  1. Streamlit chat UI                        │
                       │  2. MCP server (Claude Desktop, n8n MCP,     │
                       │     Claude Code)                             │
                       │  3. HTTP webhook (consumed by n8n            │
                       │     catalog-audit workflow)                  │
                       └──────────────────────┬───────────────────────┘
                                              │
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │  Agent core (Anthropic SDK tool-use loop)    │
                       │  Model: claude-sonnet-4-6                    │
                       │  Strategy: prompt-cached system prompt,      │
                       │  parallel tool calls where safe.             │
                       └──────────────────────┬───────────────────────┘
                                              │
                  ┌───────────────────────────┼───────────────────────────┐
                  │                           │                           │
        ┌─────────▼─────────┐    ┌────────────▼────────────┐    ┌─────────▼──────────┐
        │ Ingestion tools   │    │  Analysis tools         │    │  Action tools      │
        ├───────────────────┤    ├─────────────────────────┤    ├────────────────────┤
        │ fetch_product     │    │ benchmark_against_      │    │ draft_rewrite      │
        │ fetch_reviews_    │    │   category              │    │ enqueue_hitl       │
        │   full (Yotpo)    │    │ cluster_review_themes   │    │ compare_products   │
        │ extract_meta-     │    │ score_images (Gemini)   │    │                    │
        │   fields          │    │ check_consistency       │    │                    │
        │ check_field       │    │ evaluate_listing_       │    │                    │
        │                   │    │   quality               │    │                    │
        └─────────┬─────────┘    └────────────┬────────────┘    └─────────┬──────────┘
                  └───────────────────────────┼───────────────────────────┘
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │  SQLite (single file shipped in repo)        │
                       │  products · reviews · corpus(+embeddings) ·  │
                       │  hitl_queue · eval_runs · review_themes      │
                       └──────────────────────────────────────────────┘
```

**Why a tool-using agent (not a monolithic prompt):** Claude decides which tools to call per question. Factual lookups fire only `fetch_product` + `check_field`; "what can I improve?" triggers `benchmark_against_category` + `evaluate_listing_quality` + `score_images` + `check_consistency`. Tool traces are visible in the UI — reviewers can see, debug, and extend.

**Why three surfaces (Streamlit / MCP / HTTP):** Healf's brief frames agents as colleagues that plug into existing teams. A real colleague has multiple ways you can reach them. Three surfaces, one core — that's the architectural pitch.

---

## Four required capabilities (mapped to tools)

| Required capability | Implemented as | LLM in loop? |
|---|---|---|
| **Navigate** | `fetch_product_page(url)` — normalises URL, fetches HTML, extracts JSON-LD + RSC flight chunks, caches to SQLite. Playwright fallback if HTTPS fails. | No |
| **Ingest** | `parse_product(html)` → JSON-LD → Pydantic `Product`. `extract_metafields(rsc_flight)` → ingredients/claims. `fetch_reviews_full(product_id)` → Yotpo pagination. Covers all three of the assignment's text/reviews/images. | No |
| **Evaluate** | `benchmark_against_category(product)` — kNN over site corpus, 5 same-`product_type` exemplars + comparative stats. `cluster_review_themes(product_id)` — embed + cluster + Claude-label themes. `score_images(image_urls)` — Gemini Vision rubric. `check_consistency(product)` — cross-validates ingredients/description/labels/reviews. `evaluate_listing_quality(product)` — Claude rubric grounded in retrievals. | **Yes** (Claude + Gemini Vision + embeddings) |
| **Act** | `draft_rewrite(product, gaps)` — Claude drafts improved copy in Healf voice. `enqueue_hitl(rewrite)` — pushes to HITL queue. `compare_products(urls)` — cross-product side-by-side. | **Yes** (Claude) |

**LLM-reasoning requirement satisfied:** Claude does evaluation, theme labelling, copy improvement, and tool orchestration; Gemini does vision.

---

## File structure (target end state of all four plans)

```
healf-product-intelligence-agent/
├── README.md
├── CLAUDE.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── corpus.sqlite                    ← pre-built shipping artifact
├── app.py                           ← Streamlit entry
├── mcp_server.py                    ← MCP server (FastMCP)
├── webhook.py                       ← FastAPI endpoint consumed by n8n
├── pages/
│   └── hitl.py                      ← Streamlit HITL approval queue
├── healf_agent/
│   ├── __init__.py
│   ├── agent.py                     ← Anthropic tool-use loop + system prompt
│   ├── models.py                    ← Pydantic types
│   ├── storage.py                   ← SQLite schema + CRUD
│   ├── corpus.py                    ← Sitemap → stratified sample → embed → retrieve
│   ├── voice.py                     ← Healf-voice prompts
│   └── tools/
│       ├── __init__.py              ← TOOL_SCHEMAS + dispatcher
│       ├── navigate.py
│       ├── ingest.py
│       ├── reviews.py
│       ├── review_themes.py
│       ├── benchmark.py
│       ├── vision.py
│       ├── consistency.py
│       ├── evaluate.py
│       ├── act.py
│       ├── compare.py
│       └── field.py
├── evals/
│   ├── golden.jsonl
│   ├── runner.py
│   └── results/
├── n8n/
│   ├── healf-catalog-audit.json
│   └── README.md
├── examples/                        ← 7 captured demo runs
├── tests/
│   ├── fixtures/                    ← real PDP HTMLs (LMNT + 5 categories)
│   └── test_*.py
└── docs/
    └── superpowers/plans/           ← these plans live here
```

This **Plan 1** delivers the files marked Tier 1 in the wave table below. Plans 2/3/4 add the rest.

---

## Tier overview (build order)

| Tier | Waves | Scope | Plan |
|---|---|---|---|
| **1 — Foundation** | 0–5 | Scaffold, models+storage, ingestion, reviews, corpus, agent core | **This plan** |
| **2 — Analytical depth** | 6–9 | Review-theme clustering, benchmark+evaluate, vision+consistency, compare+act | Plan 2 (drafted after Tier 1 lands) |
| **3 — AI-as-colleague proof** | 10–13 | Streamlit polish + HITL, eval harness, MCP server, n8n companion | Plan 3 |
| **4 — Polish** | 14 | Examples, README, decisions log, Loom | Plan 4 |

**Wave gating:** don't start tier N+1 until tier N's tests pass green on `pytest`.

---

# Tier 1 — Foundation (this plan)

## Wave 0 — Scaffold

**Files:**
- Create: `docs/superpowers/plans/2026-05-15-healf-product-intelligence-agent.md` (copy of this plan)
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `README.md` (skeleton)
- Create: `healf_agent/__init__.py`
- Create: `healf_agent/tools/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/.gitkeep`

### Task 0.1: Move plan into repo

- [ ] **Step 1: Copy plan from Claude Code plans dir into the repo**

```powershell
New-Item -ItemType Directory -Force "docs\superpowers\plans" | Out-Null
Copy-Item "$env:USERPROFILE\.claude\plans\i-applied-to-a-delegated-finch.md" "docs\superpowers\plans\2026-05-15-healf-product-intelligence-agent.md"
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-05-15-healf-product-intelligence-agent.md
git commit -m "docs: import Tier 1 superpowers plan into repo"
```

### Task 0.2: Initialise uv project + dependencies

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "healf-agent"
version = "0.1.0"
description = "Healf Product Intelligence Agent"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.39.0",
    "openai>=1.40.0",
    "google-genai>=0.3.0",
    "httpx>=0.27.0",
    "selectolax>=0.3.21",
    "playwright>=1.45.0",
    "pydantic>=2.7.0",
    "python-dotenv>=1.0.1",
    "numpy>=1.26.0",
    "scikit-learn>=1.4.0",
    "hdbscan>=0.8.36",
    "streamlit>=1.36.0",
    "fastapi>=0.110.0",
    "uvicorn>=0.30.0",
    "fastmcp>=0.2.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "respx>=0.21.0",
    "ruff>=0.5.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Install with uv**

Run: `uv sync`
Expected: lockfile created, virtualenv populated.

- [ ] **Step 3: Install Playwright browser binary**

Run: `uv run playwright install chromium`
Expected: Chromium downloaded.

- [ ] **Step 4: Verify Python import sanity**

Run: `uv run python -c "import anthropic, openai, pydantic, httpx, selectolax, streamlit; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: initialise uv project with full dependency set"
```

### Task 0.3: Environment + gitignore

- [ ] **Step 1: Write `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
YOTPO_APP_KEY=...
HEALF_USER_AGENT=HealfProductIntelligenceAgent/0.1 (https://github.com/Danez-AI/healf-product-intelligence-agent)
```

- [ ] **Step 2: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.env
*.sqlite-journal
healf.sqlite
tests/fixtures/*.html
!tests/fixtures/.gitkeep
.streamlit/secrets.toml
evals/results/*.jsonl
!evals/results/.gitkeep
```

- [ ] **Step 3: Commit**

```bash
git add .env.example .gitignore
git commit -m "build: env template and gitignore"
```

### Task 0.4: Skeleton package + README

- [ ] **Step 1: Create empty `__init__.py` files**

`healf_agent/__init__.py`:
```python
"""Healf Product Intelligence Agent."""
__version__ = "0.1.0"
```

`healf_agent/tools/__init__.py`:
```python
"""Tool implementations for the Healf agent."""
```

`tests/__init__.py`: empty file.

`tests/fixtures/.gitkeep`: empty file.

- [ ] **Step 2: Write README skeleton**

```markdown
# Healf Product Intelligence Agent

A natural-language agent for Healf product pages — answers questions, evaluates listings against the site corpus, drafts copy improvements, and surfaces them through a Streamlit chat, an MCP server, and an n8n catalog-audit workflow.

## Status

Under construction. See `docs/superpowers/plans/` for the live build plans.

## Quickstart

```bash
uv sync
uv run playwright install chromium
cp .env.example .env  # fill in keys
uv run streamlit run app.py
```

## Architecture

See `docs/superpowers/plans/2026-05-15-healf-product-intelligence-agent.md`.
```

- [ ] **Step 3: Commit**

```bash
git add healf_agent/ tests/ README.md
git commit -m "build: package skeleton and README"
```

### Task 0.5: Generate CLAUDE.md

- [ ] **Step 1: Run `/init` slash command**

This is a manual user action in Claude Code. Skip if already present.

- [ ] **Step 2: Verify `CLAUDE.md` exists at repo root and references the plan**

If missing, ask the human to invoke `/init`. The init skill emits a fresh CLAUDE.md tuned to this repo.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md for future Claude Code sessions"
```

---

## Wave 1 — Models + Storage

**Files:**
- Create: `healf_agent/models.py`
- Create: `healf_agent/storage.py`
- Create: `tests/test_models.py`
- Create: `tests/test_storage.py`

### Task 1.1: Pydantic models

- [ ] **Step 1: Write `tests/test_models.py`**

```python
from datetime import datetime
from healf_agent.models import (
    Product, Image, Review, ReviewTheme, EvalReport, RubricScore,
    ConsistencyFinding, ConsistencyReport, HITLEntry, Comparison,
)


def test_product_minimal_construction():
    p = Product(
        url="https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack",
        handle="lmnt-recharge-electrolytes-variety-pack",
        title="LMNT Recharge Electrolytes Variety Pack",
        brand="LMNT",
        product_type="Electrolytes",
        description="Tasty electrolytes...",
        price_gbp=45.0,
        currency="GBP",
        sku="LMNT-VARIETY-30",
        gid="gid://shopify/Product/7620180541679",
        images=[],
        ingredients=[],
        claims=[],
        rating_value=4.9,
        rating_count=445,
    )
    assert p.handle == "lmnt-recharge-electrolytes-variety-pack"
    assert p.rating_count == 445


def test_product_rejects_unknown_currency():
    import pydantic
    try:
        Product(
            url="https://healf.com/x",
            handle="x",
            title="x",
            brand="x",
            product_type="x",
            description="x",
            price_gbp=1.0,
            currency="XYZ",
            sku="x",
            gid="gid://shopify/Product/1",
            images=[],
            ingredients=[],
            claims=[],
            rating_value=None,
            rating_count=None,
        )
    except pydantic.ValidationError:
        return
    raise AssertionError("expected ValidationError for unknown currency")


def test_review_construction_and_polarity():
    r = Review(
        review_id="abc",
        product_gid="gid://shopify/Product/1",
        author="Alex",
        rating=2,
        title="Tart",
        body="Too sour for me",
        created_at=datetime(2025, 1, 1),
        verified=True,
    )
    assert r.polarity() == "negative"


def test_eval_report_average_score():
    rep = EvalReport(
        product_handle="x",
        scores=[
            RubricScore(axis="clarity", score=4, rationale="ok"),
            RubricScore(axis="depth", score=2, rationale="thin"),
        ],
        gaps=["missing serving size"],
        corpus_references=[],
    )
    assert rep.average() == 3.0
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `uv run pytest tests/test_models.py -v`
Expected: ImportError (`healf_agent.models` has nothing).

- [ ] **Step 3: Implement `healf_agent/models.py`**

```python
"""Pydantic models for the Healf agent."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


Currency = Literal["GBP", "USD", "EUR"]


class Image(BaseModel):
    url: HttpUrl
    alt: str | None = None
    width: int | None = None
    height: int | None = None


class Review(BaseModel):
    review_id: str
    product_gid: str
    author: str | None = None
    rating: int = Field(ge=1, le=5)
    title: str | None = None
    body: str
    created_at: datetime | None = None
    verified: bool = False

    def polarity(self) -> Literal["positive", "neutral", "negative"]:
        if self.rating >= 4:
            return "positive"
        if self.rating == 3:
            return "neutral"
        return "negative"


class Product(BaseModel):
    url: HttpUrl
    handle: str
    title: str
    brand: str
    product_type: str
    description: str
    price_gbp: float
    currency: Currency
    sku: str
    gid: str
    images: list[Image] = Field(default_factory=list)
    ingredients: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    rating_value: float | None = None
    rating_count: int | None = None
    raw_jsonld: dict | None = None
    raw_metafields: dict | None = None

    @field_validator("handle")
    @classmethod
    def _handle_is_slug(cls, v: str) -> str:
        if not v or "/" in v or " " in v:
            raise ValueError("handle must be a URL slug")
        return v


class ReviewTheme(BaseModel):
    product_gid: str
    polarity: Literal["positive", "negative", "neutral"]
    label: str
    summary: str
    review_ids: list[str]
    weight: float


class RubricScore(BaseModel):
    axis: str
    score: int = Field(ge=1, le=5)
    rationale: str


class CorpusReference(BaseModel):
    handle: str
    title: str
    why: str


class EvalReport(BaseModel):
    product_handle: str
    scores: list[RubricScore]
    gaps: list[str]
    corpus_references: list[CorpusReference]

    def average(self) -> float:
        if not self.scores:
            return 0.0
        return sum(s.score for s in self.scores) / len(self.scores)


class ConsistencyFinding(BaseModel):
    kind: Literal["ingredient_mismatch", "claim_unsupported", "image_underrepresented", "label_ocr_conflict"]
    detail: str
    evidence: str


class ConsistencyReport(BaseModel):
    product_handle: str
    findings: list[ConsistencyFinding]


class HITLEntry(BaseModel):
    id: int | None = None
    product_handle: str
    original_description: str
    drafted_description: str
    gap_summary: str
    status: Literal["pending", "approved", "rejected", "edited"] = "pending"
    created_at: datetime | None = None


class Comparison(BaseModel):
    handles: list[str]
    rows: list[dict]
    summary: str
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `uv run pytest tests/test_models.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add healf_agent/models.py tests/test_models.py
git commit -m "feat(models): Pydantic v2 schema for product, review, eval, consistency, HITL"
```

### Task 1.2: SQLite storage layer

- [ ] **Step 1: Write `tests/test_storage.py`**

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `uv run pytest tests/test_storage.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `healf_agent/storage.py`**

```python
"""SQLite storage for the Healf agent."""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Iterable

from healf_agent.models import Image, Product, Review

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    handle TEXT PRIMARY KEY,
    gid TEXT UNIQUE NOT NULL,
    json TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    product_gid TEXT NOT NULL,
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reviews_gid ON reviews(product_gid);
CREATE TABLE IF NOT EXISTS corpus (
    handle TEXT PRIMARY KEY,
    product_type TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_corpus_type ON corpus(product_type);
CREATE TABLE IF NOT EXISTS review_themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_gid TEXT NOT NULL,
    polarity TEXT NOT NULL,
    label TEXT NOT NULL,
    summary TEXT NOT NULL,
    review_ids TEXT NOT NULL,
    weight REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS hitl_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_handle TEXT NOT NULL,
    original_description TEXT NOT NULL,
    drafted_description TEXT NOT NULL,
    gap_summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS eval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    score REAL NOT NULL,
    detail TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


def _vec_to_blob(vec: list[float]) -> bytes:
    import array
    return array.array("f", vec).tobytes()


def _blob_to_vec(blob: bytes) -> list[float]:
    import array
    a = array.array("f")
    a.frombytes(blob)
    return list(a)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


class Storage:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- products ----
    def upsert_product(self, p: Product) -> None:
        import time
        payload = p.model_dump(mode="json")
        self.conn.execute(
            "INSERT INTO products(handle, gid, json, fetched_at) VALUES(?,?,?,?) "
            "ON CONFLICT(handle) DO UPDATE SET gid=excluded.gid, json=excluded.json, fetched_at=excluded.fetched_at",
            (p.handle, p.gid, json.dumps(payload), time.time()),
        )
        self.conn.commit()

    def get_product(self, handle: str) -> Product | None:
        row = self.conn.execute("SELECT json FROM products WHERE handle=?", (handle,)).fetchone()
        if not row:
            return None
        return Product.model_validate(json.loads(row["json"]))

    # ---- reviews ----
    def upsert_reviews(self, reviews: Iterable[Review]) -> None:
        rows = [
            (r.review_id, r.product_gid, json.dumps(r.model_dump(mode="json")))
            for r in reviews
        ]
        self.conn.executemany(
            "INSERT INTO reviews(review_id, product_gid, json) VALUES(?,?,?) "
            "ON CONFLICT(review_id) DO UPDATE SET json=excluded.json",
            rows,
        )
        self.conn.commit()

    def get_reviews(self, product_gid: str) -> list[Review]:
        rows = self.conn.execute(
            "SELECT json FROM reviews WHERE product_gid=?", (product_gid,)
        ).fetchall()
        return [Review.model_validate(json.loads(r["json"])) for r in rows]

    # ---- corpus ----
    def upsert_corpus_entry(
        self,
        handle: str,
        product_type: str,
        title: str,
        text: str,
        embedding: list[float],
    ) -> None:
        self.conn.execute(
            "INSERT INTO corpus(handle, product_type, title, text, embedding) VALUES(?,?,?,?,?) "
            "ON CONFLICT(handle) DO UPDATE SET product_type=excluded.product_type, title=excluded.title, text=excluded.text, embedding=excluded.embedding",
            (handle, product_type, title, text, _vec_to_blob(embedding)),
        )
        self.conn.commit()

    def knn(self, *, product_type: str, query_vec: list[float], k: int = 5) -> list[dict]:
        rows = self.conn.execute(
            "SELECT handle, title, text, embedding FROM corpus WHERE product_type=?",
            (product_type,),
        ).fetchall()
        scored = [
            {
                "handle": r["handle"],
                "title": r["title"],
                "text": r["text"],
                "score": _cosine(query_vec, _blob_to_vec(r["embedding"])),
            }
            for r in rows
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `uv run pytest tests/test_storage.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add healf_agent/storage.py tests/test_storage.py
git commit -m "feat(storage): SQLite schema and CRUD for products, reviews, corpus, HITL"
```

---

## Wave 2 — Ingestion (Navigate + Parse)

**Files:**
- Create: `healf_agent/tools/navigate.py`
- Create: `healf_agent/tools/ingest.py`
- Create: `tests/fixtures/lmnt-recharge-electrolytes-variety-pack.html` (real PDP HTML captured offline — see Task 2.1)
- Create: `tests/test_navigate.py`
- Create: `tests/test_ingest.py`

### Task 2.1: Capture a real PDP fixture

- [ ] **Step 1: Fetch LMNT PDP HTML and save as a test fixture**

```bash
uv run python -c "import httpx; r=httpx.get('https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack', timeout=30, headers={'User-Agent': 'HealfProductIntelligenceAgent/0.1'}); open('tests/fixtures/lmnt-recharge-electrolytes-variety-pack.html','w',encoding='utf-8').write(r.text); print(r.status_code, len(r.text))"
```

Expected: `200 <large number>`.

- [ ] **Step 2: Verify the fixture has both JSON-LD and an RSC flight block**

```bash
uv run python -c "h=open('tests/fixtures/lmnt-recharge-electrolytes-variety-pack.html',encoding='utf-8').read(); print('jsonld:', 'application/ld+json' in h); print('rsc:', '__next_f.push' in h)"
```

Expected: `jsonld: True` and `rsc: True`.

- [ ] **Step 3: Add the fixture to git despite gitignore**

Override the gitignore exclusion for this single file so tests are reproducible without re-fetching:

```bash
git add -f tests/fixtures/lmnt-recharge-electrolytes-variety-pack.html
```

- [ ] **Step 4: Commit**

```bash
git commit -m "test(fixtures): capture LMNT PDP HTML for ingestion tests"
```

### Task 2.2: `navigate.fetch_product_page`

- [ ] **Step 1: Write `tests/test_navigate.py`**

```python
import httpx
import pytest
import respx

from healf_agent.tools.navigate import FetchError, fetch_product_page


@respx.mock
def test_fetch_returns_html_on_200() -> None:
    url = "https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack"
    respx.get(url).mock(return_value=httpx.Response(200, text="<html><body>ok</body></html>"))
    html = fetch_product_page(url)
    assert "<body>ok</body>" in html


@respx.mock
def test_fetch_raises_on_404() -> None:
    url = "https://healf.com/en-uk/products/does-not-exist"
    respx.get(url).mock(return_value=httpx.Response(404, text="missing"))
    with pytest.raises(FetchError):
        fetch_product_page(url)


def test_fetch_normalises_locale_prefix() -> None:
    # Healf URLs sometimes lack /en-uk; we should normalise.
    from healf_agent.tools.navigate import normalise_url
    assert normalise_url("https://healf.com/products/x") == "https://healf.com/en-uk/products/x"
    assert normalise_url("https://healf.com/en-uk/products/x") == "https://healf.com/en-uk/products/x"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `uv run pytest tests/test_navigate.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `healf_agent/tools/navigate.py`**

```python
"""Navigate capability: fetch a Healf PDP, with Playwright fallback."""
from __future__ import annotations

import os
from urllib.parse import urlparse, urlunparse

import httpx

DEFAULT_UA = os.getenv(
    "HEALF_USER_AGENT",
    "HealfProductIntelligenceAgent/0.1 (https://github.com/Danez-AI/healf-product-intelligence-agent)",
)


class FetchError(RuntimeError):
    pass


def normalise_url(url: str) -> str:
    parts = urlparse(url)
    path = parts.path
    if path.startswith("/products/"):
        path = "/en-uk" + path
    return urlunparse(parts._replace(path=path))


def fetch_product_page(url: str, *, timeout: float = 30.0) -> str:
    """Fetch a Healf product page. Falls back to Playwright if HTTPS GET fails."""
    target = normalise_url(url)
    try:
        r = httpx.get(target, timeout=timeout, headers={"User-Agent": DEFAULT_UA})
    except httpx.HTTPError as e:
        return _playwright_fetch(target) or _fail(f"http error: {e}")
    if r.status_code != 200:
        return _playwright_fetch(target) or _fail(f"status {r.status_code}")
    return r.text


def _playwright_fetch(url: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=DEFAULT_UA)
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            html = page.content()
            browser.close()
            return html
    except Exception:
        return None


def _fail(msg: str) -> str:
    raise FetchError(msg)
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `uv run pytest tests/test_navigate.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add healf_agent/tools/navigate.py tests/test_navigate.py
git commit -m "feat(navigate): httpx fetch with Playwright fallback + URL normalisation"
```

### Task 2.3: `ingest.parse_product` — JSON-LD path

- [ ] **Step 1: Write the failing test in `tests/test_ingest.py`**

```python
from pathlib import Path

from healf_agent.tools.ingest import extract_json_ld, parse_product


FIXTURE = Path("tests/fixtures/lmnt-recharge-electrolytes-variety-pack.html")


def test_extract_jsonld_finds_product_schema() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    blocks = extract_json_ld(html)
    products = [b for b in blocks if b.get("@type") == "Product"]
    assert products, "expected at least one Product JSON-LD block"
    assert products[0]["name"].lower().startswith("lmnt")


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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `healf_agent/tools/ingest.py`**

```python
"""Ingest capability: parse PDP HTML into a Product."""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from selectolax.parser import HTMLParser

from healf_agent.models import Image, Product

_GID_RE = re.compile(r"gid://shopify/Product/\d+")
_HANDLE_RE = re.compile(r"/products/([^/?#]+)")


def extract_json_ld(html: str) -> list[dict]:
    """Return all JSON-LD blocks parsed as dicts."""
    tree = HTMLParser(html)
    blocks: list[dict] = []
    for node in tree.css('script[type="application/ld+json"]'):
        text = node.text() or ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            blocks.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                blocks.extend(d for d in data["@graph"] if isinstance(d, dict))
            else:
                blocks.append(data)
    return blocks


def extract_rsc_flight(html: str) -> str:
    """Return concatenated text of all RSC flight chunks."""
    parts = re.findall(r'self\.__next_f\.push\(\[\d+,\s*"((?:[^"\\]|\\.)*)"\]\)', html)
    return "".join(parts).encode("utf-8", "ignore").decode("unicode_escape", "ignore")


def _first_product_block(blocks: list[dict]) -> dict:
    for b in blocks:
        if b.get("@type") == "Product":
            return b
    raise ValueError("no Product JSON-LD found")


def _handle_from_url(url: str) -> str:
    m = _HANDLE_RE.search(urlparse(url).path)
    if not m:
        raise ValueError(f"cannot parse handle from {url}")
    return m.group(1)


def _gid_from_html(html: str, fallback: str) -> str:
    m = _GID_RE.search(html)
    return m.group(0) if m else fallback


def _images_from_block(block: dict) -> list[Image]:
    raw = block.get("image") or []
    if isinstance(raw, str):
        raw = [raw]
    return [Image(url=u) for u in raw if isinstance(u, str)]


def parse_product(html: str, *, url: str) -> Product:
    blocks = extract_json_ld(html)
    pblock = _first_product_block(blocks)
    handle = _handle_from_url(url)
    offers = pblock.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    rating = pblock.get("aggregateRating") or {}
    price_raw = offers.get("price")
    try:
        price_gbp = float(price_raw) if price_raw is not None else 0.0
    except (TypeError, ValueError):
        price_gbp = 0.0
    brand_raw = pblock.get("brand")
    brand = brand_raw.get("name") if isinstance(brand_raw, dict) else (brand_raw or "Unknown")
    return Product(
        url=url,
        handle=handle,
        title=pblock.get("name") or handle,
        brand=brand,
        product_type=pblock.get("category") or "Unknown",
        description=pblock.get("description") or "",
        price_gbp=price_gbp,
        currency=(offers.get("priceCurrency") or "GBP"),
        sku=pblock.get("sku") or pblock.get("mpn") or handle,
        gid=_gid_from_html(html, fallback=f"gid://shopify/Product/{pblock.get('productID', '0')}"),
        images=_images_from_block(pblock),
        ingredients=[],
        claims=[],
        rating_value=float(rating["ratingValue"]) if rating.get("ratingValue") else None,
        rating_count=int(rating["reviewCount"]) if rating.get("reviewCount") else None,
        raw_jsonld=pblock,
    )
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add healf_agent/tools/ingest.py tests/test_ingest.py
git commit -m "feat(ingest): JSON-LD + RSC flight extraction, Product parsing from LMNT fixture"
```

### Task 2.4: `ingest.extract_metafields` — RSC flight path

- [ ] **Step 1: Append a test to `tests/test_ingest.py`**

```python
from healf_agent.tools.ingest import extract_metafields


def test_extract_metafields_pulls_ingredients_when_present() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    meta = extract_metafields(html)
    # We don't assert exact shape (LMNT may or may not have ingredient metafield),
    # but the function must return a dict and not raise.
    assert isinstance(meta, dict)
```

- [ ] **Step 2: Implement `extract_metafields` in `healf_agent/tools/ingest.py`**

Append:

```python
_METAFIELD_RE = re.compile(r'"(?P<key>(?:ingredients?|claims?|benefits?|how_to_use|directions?|metafield))"\s*:\s*(?P<val>"(?:[^"\\]|\\.)*"|\[[^\]]*\])', re.IGNORECASE)


def extract_metafields(html: str) -> dict[str, object]:
    """Pull ingredient/claim-like metafields from the RSC flight payload.

    Returns a flat dict of key -> value (str or list). Conservative: only keys
    matching a whitelist are returned. Empty dict if nothing matches.
    """
    flight = extract_rsc_flight(html)
    if not flight:
        return {}
    out: dict[str, object] = {}
    for m in _METAFIELD_RE.finditer(flight):
        key = m.group("key").lower().rstrip("s")
        raw = m.group("val")
        try:
            val = json.loads(raw)
        except json.JSONDecodeError:
            continue
        out.setdefault(key, val)
    return out
```

- [ ] **Step 3: Run tests — expect PASS**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add healf_agent/tools/ingest.py tests/test_ingest.py
git commit -m "feat(ingest): metafield extraction from RSC flight payload"
```

---

## Wave 3 — Reviews (Yotpo)

**Files:**
- Create: `healf_agent/tools/reviews.py`
- Create: `tests/test_reviews.py`

### Task 3.1: Discover Yotpo app key

- [ ] **Step 1: Scan PDP HTML for the Yotpo app key**

```bash
uv run python -c "import re,sys; h=open('tests/fixtures/lmnt-recharge-electrolytes-variety-pack.html',encoding='utf-8').read(); m=re.search(r'yotpo[^\"\\']{0,80}?app[_-]?key[\"\\\\\\\']?\\s*[:=]\\s*[\"\\\\\\\']?([A-Za-z0-9]{16,64})', h, re.IGNORECASE); print(m.group(1) if m else 'NOT FOUND — fall back to runtime discovery')"
```

If the regex hits, copy the value into `.env` as `YOTPO_APP_KEY=<value>`. If it misses, fall back to discovery at runtime in the next task (the public widget endpoint can be discovered from `<script src="...yotpo.com/...">` URLs).

### Task 3.2: `fetch_reviews_full` paginates Yotpo

- [ ] **Step 1: Write `tests/test_reviews.py`**

```python
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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `uv run pytest tests/test_reviews.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `healf_agent/tools/reviews.py`**

```python
"""Yotpo reviews fetcher."""
from __future__ import annotations

import os
from datetime import datetime

import httpx

from healf_agent.models import Review

YOTPO_BASE = "https://api.yotpo.com/v1/widget"


def _product_id_from_gid(gid: str) -> str:
    return gid.rsplit("/", 1)[-1]


def _to_review(raw: dict, product_gid: str) -> Review:
    score = int(raw.get("score") or raw.get("rating") or 0) or 1
    created_raw = raw.get("created_at")
    created: datetime | None = None
    if created_raw:
        try:
            created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except ValueError:
            created = None
    user = raw.get("user") or {}
    return Review(
        review_id=str(raw.get("id") or raw.get("review_id") or ""),
        product_gid=product_gid,
        author=(user.get("display_name") if isinstance(user, dict) else None),
        rating=max(1, min(5, score)),
        title=raw.get("title"),
        body=raw.get("content") or raw.get("body") or "",
        created_at=created,
        verified=bool(raw.get("verified_buyer", False)),
    )


def fetch_reviews_full(
    *,
    product_gid: str,
    app_key: str | None = None,
    per_page: int = 50,
    max_pages: int = 50,
    timeout: float = 30.0,
) -> list[Review]:
    """Paginate the Yotpo widget API for a product. Returns all reviews."""
    app_key = app_key or os.environ.get("YOTPO_APP_KEY")
    if not app_key:
        raise RuntimeError("YOTPO_APP_KEY missing")
    product_id = _product_id_from_gid(product_gid)
    url = f"{YOTPO_BASE}/{app_key}/products/{product_id}/reviews.json"
    out: list[Review] = []
    seen_ids: set[str] = set()
    with httpx.Client(timeout=timeout) as client:
        for page in range(1, max_pages + 1):
            r = client.get(url, params={"page": page, "per_page": per_page})
            if r.status_code != 200:
                break
            data = r.json().get("response", {})
            chunk = data.get("reviews") or []
            if not chunk:
                break
            for raw in chunk:
                rv = _to_review(raw, product_gid)
                if rv.review_id and rv.review_id not in seen_ids:
                    seen_ids.add(rv.review_id)
                    out.append(rv)
            total = (data.get("pagination") or {}).get("total")
            if total and len(out) >= total:
                break
    return out
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `uv run pytest tests/test_reviews.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add healf_agent/tools/reviews.py tests/test_reviews.py
git commit -m "feat(reviews): paginated Yotpo widget API fetcher"
```

---

## Wave 4 — Corpus (sitemap → stratified sample → embed → retrieve)

**Files:**
- Create: `healf_agent/corpus.py`
- Create: `tests/test_corpus.py`
- Create: `scripts/build_corpus.py`

### Task 4.1: Sitemap parser

- [ ] **Step 1: Write `tests/test_corpus.py` (sitemap section)**

```python
import httpx
import respx

from healf_agent.corpus import (
    parse_sitemap_index,
    parse_product_sitemap,
    stratified_sample,
)


SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://healf.com/sitemap-products.xml</loc></sitemap>
  <sitemap><loc>https://healf.com/sitemap-collections.xml</loc></sitemap>
</sitemapindex>"""

PRODUCT_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://healf.com/en-uk/products/a</loc></url>
  <url><loc>https://healf.com/en-uk/products/b</loc></url>
  <url><loc>https://healf.com/en-uk/products/c</loc></url>
</urlset>"""


def test_parse_sitemap_index_returns_sub_sitemaps() -> None:
    subs = parse_sitemap_index(SITEMAP_INDEX)
    assert "https://healf.com/sitemap-products.xml" in subs


def test_parse_product_sitemap_returns_urls() -> None:
    urls = parse_product_sitemap(PRODUCT_SITEMAP)
    assert urls == [
        "https://healf.com/en-uk/products/a",
        "https://healf.com/en-uk/products/b",
        "https://healf.com/en-uk/products/c",
    ]


def test_stratified_sample_returns_balanced_buckets() -> None:
    pool = {
        "Electrolytes": [f"https://x/{i}" for i in range(20)],
        "Supplements": [f"https://y/{i}" for i in range(50)],
        "Skincare": [f"https://z/{i}" for i in range(5)],
    }
    sample = stratified_sample(pool, target_total=30, min_per_bucket=3, seed=0)
    # Every bucket present at least min_per_bucket times if it has enough items
    assert sum(len(v) for v in sample.values()) <= 30
    assert len(sample["Skincare"]) >= 3
    assert len(sample["Electrolytes"]) >= 3
    assert len(sample["Supplements"]) >= 3
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `uv run pytest tests/test_corpus.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `healf_agent/corpus.py` (sitemap + sampler portion)**

```python
"""Corpus: site-wide standards retrieval layer."""
from __future__ import annotations

import math
import random
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Iterable

NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def parse_sitemap_index(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [el.text.strip() for el in root.iterfind(f".//{NS}sitemap/{NS}loc") if el.text]


def parse_product_sitemap(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [el.text.strip() for el in root.iterfind(f".//{NS}url/{NS}loc") if el.text]


def stratified_sample(
    pool: Mapping[str, list[str]],
    *,
    target_total: int,
    min_per_bucket: int = 3,
    seed: int = 0,
) -> dict[str, list[str]]:
    """Sample roughly `target_total` items across buckets, with a floor per bucket."""
    rng = random.Random(seed)
    result: dict[str, list[str]] = {}
    # Phase 1: minimum floor
    remaining_budget = target_total
    for bucket, items in pool.items():
        take = min(min_per_bucket, len(items))
        picked = rng.sample(items, take) if take < len(items) else list(items)
        result[bucket] = picked
        remaining_budget -= take
    if remaining_budget <= 0:
        return result
    # Phase 2: proportional fill across remaining
    total_remaining = sum(max(0, len(items) - len(result[b])) for b, items in pool.items())
    if total_remaining == 0:
        return result
    for bucket, items in pool.items():
        already = result[bucket]
        leftover = [u for u in items if u not in already]
        if not leftover:
            continue
        share = math.floor(remaining_budget * (len(leftover) / total_remaining))
        if share <= 0:
            continue
        take = min(share, len(leftover))
        result[bucket].extend(rng.sample(leftover, take))
    return result
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `uv run pytest tests/test_corpus.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add healf_agent/corpus.py tests/test_corpus.py
git commit -m "feat(corpus): sitemap parse + stratified sampling"
```

### Task 4.2: Embeddings + retrieval

- [ ] **Step 1: Append tests to `tests/test_corpus.py`**

```python
from unittest.mock import MagicMock

from healf_agent.corpus import embed_texts, build_corpus_text


def test_build_corpus_text_concatenates_title_description_claims() -> None:
    text = build_corpus_text(
        title="Creatine",
        description="Micronised creatine.",
        claims=["5g per serving", "no fillers"],
    )
    assert "Creatine" in text
    assert "Micronised" in text
    assert "5g per serving" in text


def test_embed_texts_uses_openai_client(monkeypatch) -> None:
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1, 0.2, 0.3]) for _ in range(2)]
    )
    vecs = embed_texts(["hello", "world"], client=fake_client, model="text-embedding-3-small")
    assert vecs == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    fake_client.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small", input=["hello", "world"]
    )
```

- [ ] **Step 2: Append implementation to `healf_agent/corpus.py`**

```python
def build_corpus_text(*, title: str, description: str, claims: Iterable[str]) -> str:
    parts = [title, description, "; ".join(claims)]
    return "\n".join(p for p in parts if p)


def embed_texts(texts: list[str], *, client, model: str = "text-embedding-3-small") -> list[list[float]]:
    if not texts:
        return []
    resp = client.embeddings.create(model=model, input=texts)
    return [d.embedding for d in resp.data]
```

- [ ] **Step 3: Run tests — expect PASS**

Run: `uv run pytest tests/test_corpus.py -v`
Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add healf_agent/corpus.py tests/test_corpus.py
git commit -m "feat(corpus): embedding helper and corpus text builder"
```

### Task 4.3: `scripts/build_corpus.py`

- [ ] **Step 1: Write `scripts/build_corpus.py`** (one-shot ingestion)

```python
"""Build corpus.sqlite by sampling Healf's product sitemap.

Run: `uv run python scripts/build_corpus.py --target 150 --out corpus.sqlite`
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import defaultdict
from pathlib import Path

import httpx
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from healf_agent.corpus import (
    build_corpus_text,
    embed_texts,
    parse_product_sitemap,
    parse_sitemap_index,
    stratified_sample,
)
from healf_agent.storage import Storage
from healf_agent.tools.ingest import parse_product
from healf_agent.tools.navigate import fetch_product_page


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=150)
    ap.add_argument("--out", default="corpus.sqlite")
    args = ap.parse_args()

    storage = Storage(args.out)
    storage.init_schema()

    with httpx.Client(timeout=30) as client:
        idx = client.get("https://healf.com/sitemap.xml").text
        products_sitemap_url = next(
            (u for u in parse_sitemap_index(idx) if "sitemap-products" in u), None
        )
        if not products_sitemap_url:
            raise SystemExit("could not find products sitemap")
        product_urls = parse_product_sitemap(client.get(products_sitemap_url).text)

    # Bucket by product_type via a cheap parse of the first page each.
    buckets: dict[str, list[str]] = defaultdict(list)
    for url in product_urls:
        try:
            html = fetch_product_page(url)
            p = parse_product(html, url=url)
        except Exception:
            continue
        buckets[p.product_type].append(url)

    sample = stratified_sample(buckets, target_total=args.target)
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    texts: list[str] = []
    rows: list[tuple[str, str, str, str]] = []  # (handle, product_type, title, text)
    for product_type, urls in sample.items():
        for url in urls:
            try:
                html = fetch_product_page(url)
                p = parse_product(html, url=url)
            except Exception:
                continue
            text = build_corpus_text(
                title=p.title, description=p.description, claims=p.claims
            )
            rows.append((p.handle, product_type, p.title, text))
            texts.append(text)

    vecs = embed_texts(texts, client=openai_client)
    for (handle, product_type, title, text), vec in zip(rows, vecs):
        storage.upsert_corpus_entry(
            handle=handle,
            product_type=product_type,
            title=title,
            text=text,
            embedding=vec,
        )
    print(f"corpus built: {len(rows)} entries across {len(sample)} buckets → {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test on a tiny target (10 products) to validate plumbing**

Run: `uv run python scripts/build_corpus.py --target 10 --out test_corpus.sqlite`
Expected: prints `corpus built: ~10 entries across N buckets → test_corpus.sqlite`. Delete `test_corpus.sqlite` afterwards.

- [ ] **Step 3: Build the real corpus (≥150 products)**

Run: `uv run python scripts/build_corpus.py --target 150 --out corpus.sqlite`
Expected: corpus.sqlite ≈ 5–10 MB.

- [ ] **Step 4: Commit corpus + script**

```bash
git add scripts/build_corpus.py corpus.sqlite
git commit -m "feat(corpus): build script + shipped corpus.sqlite (150 stratified products)"
```

---

## Wave 5 — Agent core

**Files:**
- Create: `healf_agent/agent.py`
- Create: `healf_agent/tools/field.py`
- Modify: `healf_agent/tools/__init__.py` (add `TOOL_SCHEMAS` + dispatcher)
- Create: `app.py`
- Create: `tests/test_agent.py`

### Task 5.1: `check_field` tool

- [ ] **Step 1: Write `tests/test_agent.py` (field-tool section)**

```python
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
```

- [ ] **Step 2: Implement `healf_agent/tools/field.py`**

```python
"""check_field: exact factual lookups grounded in the Product."""
from __future__ import annotations

from healf_agent.models import Product


def check_field(product: Product, *, field: str, value: str) -> dict:
    needle = value.lower()
    if field == "ingredient":
        present = any(needle in i.lower() for i in product.ingredients)
        return {"present": present, "evidence": product.ingredients}
    if field == "claim":
        present = any(needle in c.lower() for c in product.claims)
        return {"present": present, "evidence": product.claims}
    if field == "brand":
        return {"present": needle == product.brand.lower(), "evidence": product.brand}
    if field == "rating":
        return {"value": product.rating_value, "count": product.rating_count}
    return {"present": False, "evidence": None}
```

- [ ] **Step 3: Run field tests — expect PASS**

Run: `uv run pytest tests/test_agent.py::test_check_field_finds_ingredient_when_present tests/test_agent.py::test_check_field_misses_ingredient_when_absent -v`
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add healf_agent/tools/field.py tests/test_agent.py
git commit -m "feat(tools): check_field for exact factual lookups"
```

### Task 5.2: Tool schemas + dispatcher

- [ ] **Step 1: Append a dispatcher test to `tests/test_agent.py`**

```python
from healf_agent.tools import TOOL_SCHEMAS, dispatch_tool


def test_tool_schemas_advertise_check_field() -> None:
    names = {t["name"] for t in TOOL_SCHEMAS}
    assert "check_field" in names


def test_dispatch_check_field_returns_dict(monkeypatch) -> None:
    p = _p()  # reuse helper defined in earlier test
    out = dispatch_tool(
        name="check_field",
        arguments={"field": "ingredient", "value": "sodium"},
        product=p,
    )
    assert out["present"] is True
```

- [ ] **Step 2: Replace `healf_agent/tools/__init__.py`**

```python
"""Tool registry + dispatcher for the Healf agent."""
from __future__ import annotations

from typing import Any

from healf_agent.models import Product
from healf_agent.tools.field import check_field
from healf_agent.tools.ingest import parse_product, extract_metafields
from healf_agent.tools.navigate import fetch_product_page


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "fetch_product",
        "description": "Fetch a Healf product page by URL. Returns parsed product JSON.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "check_field",
        "description": "Look up an exact factual field on the current product (ingredient, claim, brand, rating).",
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "enum": ["ingredient", "claim", "brand", "rating"]},
                "value": {"type": "string"},
            },
            "required": ["field"],
        },
    },
]


def dispatch_tool(*, name: str, arguments: dict[str, Any], product: Product | None) -> Any:
    if name == "fetch_product":
        html = fetch_product_page(arguments["url"])
        p = parse_product(html, url=arguments["url"])
        # Augment with metafields if available
        meta = extract_metafields(html)
        if meta.get("ingredient"):
            ings = meta["ingredient"]
            if isinstance(ings, str):
                ings = [ings]
            p = p.model_copy(update={"ingredients": list(ings)})
        return p.model_dump(mode="json")
    if name == "check_field":
        if product is None:
            raise ValueError("check_field requires a current product")
        return check_field(product, field=arguments["field"], value=arguments.get("value", ""))
    raise ValueError(f"unknown tool: {name}")
```

- [ ] **Step 3: Run dispatcher tests — expect PASS**

Run: `uv run pytest tests/test_agent.py::test_tool_schemas_advertise_check_field tests/test_agent.py::test_dispatch_check_field_returns_dict -v`
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add healf_agent/tools/__init__.py tests/test_agent.py
git commit -m "feat(agent): tool registry + dispatcher with fetch_product and check_field"
```

### Task 5.3: Anthropic tool-use loop

- [ ] **Step 1: Append loop tests to `tests/test_agent.py`**

```python
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
```

- [ ] **Step 2: Implement `healf_agent/agent.py`**

```python
"""Anthropic tool-use loop."""
from __future__ import annotations

import json
from typing import Any

from healf_agent.models import Product
from healf_agent.tools import TOOL_SCHEMAS, dispatch_tool


SYSTEM_PROMPT = """You are the Healf Product Intelligence Agent, a colleague for the
Healf AI Transformation Team. You answer questions about Healf product pages
(https://healf.com) and the broader Healf catalogue.

Rules:
- Ground every claim in tool output. If you don't have evidence, say you don't.
- Prefer concrete, citable facts (ingredient lists, review counts, image counts) over generalities.
- For "what should I improve?" type questions, cite specific other Healf products from the corpus.
- Refuse politely if the user asks about anything outside the Healf catalogue.
"""


def run_agent_turn(
    *,
    client,
    model: str,
    user_message: str,
    product: Product | None,
    system: str = SYSTEM_PROMPT,
    max_iters: int = 8,
) -> tuple[str, list[dict[str, Any]]]:
    """Run a single agent turn (tool-use loop) and return (final_text, tool_trace)."""
    trace: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    for _ in range(max_iters):
        resp = client.messages.create(
            model=model,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=TOOL_SCHEMAS,
            messages=messages,
            max_tokens=2048,
        )
        if resp.stop_reason == "tool_use":
            tool_results: list[dict[str, Any]] = []
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                try:
                    result = dispatch_tool(name=block.name, arguments=block.input, product=product)
                    serialised = json.dumps(result, default=str)
                    trace.append({"tool": block.name, "input": block.input, "output": result})
                except Exception as e:
                    serialised = json.dumps({"error": str(e)})
                    trace.append({"tool": block.name, "input": block.input, "error": str(e)})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": serialised,
                    }
                )
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": tool_results})
            continue
        # end_turn or anything else final
        text = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text += block.text
        return text, trace
    return "Iteration cap reached without final answer.", trace
```

- [ ] **Step 3: Run loop test — expect PASS**

Run: `uv run pytest tests/test_agent.py::test_agent_loop_dispatches_tool_then_finalises -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add healf_agent/agent.py tests/test_agent.py
git commit -m "feat(agent): Anthropic SDK tool-use loop with trace surfacing"
```

### Task 5.4: Minimal Streamlit shell

- [ ] **Step 1: Write `app.py`**

```python
"""Healf Product Intelligence Agent — Streamlit chat (Tier 1 shell)."""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

from healf_agent.agent import run_agent_turn
from healf_agent.models import Product
from healf_agent.storage import Storage
from healf_agent.tools.ingest import extract_metafields, parse_product
from healf_agent.tools.navigate import fetch_product_page

load_dotenv()

st.set_page_config(page_title="Healf Product Intelligence Agent", layout="wide")
st.title("Healf Product Intelligence Agent")

storage = Storage(Path("healf.sqlite"))
storage.init_schema()

with st.sidebar:
    st.subheader("Current product")
    url = st.text_input(
        "Product URL",
        value="https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack",
    )
    fetch = st.button("Fetch")

if fetch and url:
    with st.spinner("Fetching…"):
        html = fetch_product_page(url)
        product = parse_product(html, url=url)
        meta = extract_metafields(html)
        if meta.get("ingredient"):
            ings = meta["ingredient"]
            product = product.model_copy(
                update={"ingredients": list(ings) if isinstance(ings, list) else [ings]}
            )
        storage.upsert_product(product)
        st.session_state["product"] = product.model_dump(mode="json")
        st.success(f"Loaded {product.title}")

product_dict = st.session_state.get("product")
product = Product.model_validate(product_dict) if product_dict else None
if product is not None:
    st.sidebar.markdown(f"**{product.title}**  \n{product.brand} · {product.product_type}")
    st.sidebar.markdown(f"⭐ {product.rating_value} ({product.rating_count} reviews)")

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["text"])
        if msg.get("trace"):
            with st.expander("tool trace"):
                st.json(msg["trace"])

user_input = st.chat_input("Ask the agent…")
if user_input:
    st.session_state["messages"].append({"role": "user", "text": user_input})
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            answer, trace = run_agent_turn(
                client=client,
                model="claude-sonnet-4-6",
                user_message=user_input,
                product=product,
            )
            st.markdown(answer)
            with st.expander("tool trace"):
                st.json(trace)
    st.session_state["messages"].append({"role": "assistant", "text": answer, "trace": trace})
```

- [ ] **Step 2: Smoke test — launch Streamlit, fetch LMNT, ask "does this have sodium?"**

Run: `uv run streamlit run app.py`
Expected: page loads, fetch succeeds, answer mentions sodium correctly.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(ui): Streamlit shell with product fetch and chat"
```

### Task 5.5: Full Tier 1 test sweep

- [ ] **Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: every test green.

- [ ] **Step 2: Tag Tier 1 complete**

```bash
git tag tier-1-complete
git push origin plan/healf-agent tier-1-complete
```

---

# Tier 2 outline (to be expanded as Plan 2 once Tier 1 lands)

| Wave | Component | Tools added |
|---|---|---|
| 6 | Review-theme clustering | `cluster_review_themes(product_gid, polarity)` — embed reviews, HDBSCAN cluster, Claude labels themes, persist to `review_themes` table. |
| 7 | Benchmark + evaluate | `benchmark_against_category(product)` — kNN over corpus; `evaluate_listing_quality(product)` — Claude rubric grounded in retrievals + review themes. |
| 8 | Vision + consistency | `score_images([url])` — Gemini Vision rubric; `check_consistency(product)` — cross-validates ingredients vs description vs label OCR vs review themes. |
| 9 | Compare + act | `compare_products([urls])` — multi-product side-by-side; `draft_rewrite(product, gaps)` — Claude in Healf voice; `enqueue_hitl(rewrite)`. |

**Tier 2 gate:** all 9 tools wired into `TOOL_SCHEMAS` and `dispatch_tool`. `tests/test_agent.py` covers a tool-use loop for each.

# Tier 3 outline (Plan 3)

| Wave | Component |
|---|---|
| 10 | Streamlit polish + HITL page (`pages/hitl.py`): pending rewrites with Approve/Edit/Reject; sidebar tool trace; source citations. |
| 11 | Eval harness: `evals/golden.jsonl` (30 hand-curated triples) + `evals/runner.py` (LLM-as-judge for open-ended, exact-match for factual). First run committed to `evals/results/`. |
| 12 | MCP server (`mcp_server.py`, FastMCP) exposing every tool over stdio + SSE; manifest + docs. Tested with Claude Desktop. |
| 13 | n8n companion: `n8n/healf-catalog-audit.json` + `webhook.py`. Daily sitemap diff → agent webhook → Slack post with rewrite draft + HITL link. |

# Tier 4 outline (Plan 4)

| Wave | Component |
|---|---|
| 14 | `examples/01..07.md` — 7 captured demo runs; README rewrite (architecture + 3-month roadmap); `docs/decisions.md` ADRs; optional 3-min Loom. |

---

## Risk register (whole-project)

| Risk | Mitigation |
|---|---|
| Yotpo widget API rate-limits or requires real app key | Discover key from PDP JS during dev; on block, fall back to JSON-LD's 10 embedded reviews + surface "showing top N" caveat. |
| Review clustering noisy for <20-review products | Gate `cluster_review_themes` on min count; below threshold return polarity counts only. |
| Cross-page consistency false positives | Conservative thresholds + human-readable evidence per flag. Treat output as "second look", not "definitive errors". |
| Healf rate-limits our fetcher | Concurrency cap + politeness sleep + cache-first reads; switch to fixture-based offline tests if mid-build block. |
| MCP client compatibility surprises | Target Claude Desktop first; document client-specific quirks. |
| n8n workflow scope creep | Single cron path only (sitemap diff → agent → Slack). All sophistication lives in the Python agent. |
| 30-question eval too small | Ship with explicit caveat in README; commit to expanding to 100 in week-1 roadmap. |
| Gemini Vision quota issues | `score_images` is most isolable tool; degrade gracefully to "vision disabled" badge. |
| Repo is private; reviewers can't read | Make public at submission; README readable cold. |
| 30-hour scope underestimated | Wave gating + tier-based cut order. Tier 4 polish is non-negotiable; cut from Tier 3 bottom-up if needed (workflow → MCP → eval → consistency → themes → comparison). |

---

## Verification (end-to-end)

**Already verified pre-plan:**
- `https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack` → 200, JSON-LD parsed, aggregateRating 4.9/445, 10 reviews, Shopify GID `7620180541679`.
- `https://healf.com/sitemap.xml` → 200, four sub-sitemaps.

**Tier 1 verification gate (this plan):**

1. `uv run pytest -v` → green (models, storage, navigate, ingest, reviews, corpus, agent).
2. `uv run python scripts/build_corpus.py --target 150 --out corpus.sqlite` → corpus.sqlite ≈ 5–10 MB.
3. `uv run streamlit run app.py` → fetch LMNT, ask "does this have sodium?" → answer cites the ingredient list correctly with a visible tool trace.

**Full-project verification (post Tier 4):**

1. Each of the 7 example prompts captured in `examples/` with tool trace + final answer.
2. `python -m evals.runner` produces a scorecard committed to `evals/results/`. Targets: ≥80% factual exact-match, ≥3.5/5 LLM-judge open-ended.
3. MCP server demoed from Claude Desktop on the same prompts; screenshot or Loom.
4. n8n workflow end-to-end on 5 sample URLs → Slack post + HITL approve cycle screenshotted.
5. README cold-readable, clearly states the 3-month roadmap (audit bot → rewrite bot → completeness bot → comparison bot → brand-onboarding bot → review-insight bot → SEO bot).

---

## Self-review notes

**Spec coverage:** Navigate (Wave 2), Ingest (Waves 2 + 3), Evaluate (Tier 2 waves 6–8), Act (Tier 2 wave 9). LLM-reasoning requirement met via Claude in agent loop (Wave 5) and again in evaluate/act (Tier 2). Three surfaces (chat/MCP/HTTP) all in Tier 3. Site-wide standards corpus in Wave 4. Three-tier fallback (JSON-LD → RSC flight → Playwright) in Wave 2. HITL queue (Tier 3 wave 10). All four "wow" features (corpus, vision, theme clustering, consistency) covered across Tiers 1–2. AI-as-colleague pitch carried by Tier 3 (MCP server + n8n workflow).

**Placeholder scan:** every code step contains executable code; every command step has an exact command and expected output. No TBDs. Tier 2/3/4 outlines are *outlines*, not placeholders — they explicitly defer to follow-up plans authored at the start of each tier (per superpowers Scope Check guidance).

**Type consistency:** `Product`, `Review`, `Image`, `EvalReport`, `RubricScore`, `CorpusReference`, `ConsistencyFinding`, `ConsistencyReport`, `HITLEntry`, `Comparison`, `ReviewTheme` defined once in `models.py` (Wave 1); referenced by name throughout. Tool signatures match `TOOL_SCHEMAS` entries.

---

## First execution step after exiting plan mode

1. Copy this plan into the repo (Task 0.1).
2. Run `/init` to generate `CLAUDE.md`.
3. Begin Wave 0 Task 0.2 (uv init + dependencies).
4. Subagent-driven execution recommended (`superpowers:subagent-driven-development`) — one subagent per task, two-stage review between tasks.
