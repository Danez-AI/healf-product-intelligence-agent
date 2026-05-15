# Healf Product Intelligence Agent — CLAUDE.md

## Project Overview

A natural-language agent for Healf (UK health & wellness Shopify marketplace) that answers questions about product pages, evaluates listings against the site corpus, drafts copy improvements, and surfaces them through three interfaces: Streamlit chat, MCP server, and n8n catalog-audit companion workflow.

**Submission context:** Healf AI Transformation Team technical assignment. The agent demonstrates the "AI agent as functional colleague" vision from their job brief.

## Key Facts

- **Live site:** https://healf.com (Next.js App Router custom storefront — NOT vanilla Shopify)
- **Main branch:** `main` | **Dev branch:** `worktree-feat-healf-agent` (in `.claude/worktrees/feat-healf-agent/`)
- **Plan file:** `docs/superpowers/plans/2026-05-15-healf-product-intelligence-agent.md`
- **Python version:** 3.11+ (running on 3.14.0 on this machine)
- **Package manager:** `uv` — invoke as `python -m uv` (not in PATH as bare `uv`)

## Architecture

```
Surfaces: Streamlit chat | MCP server (FastMCP) | HTTP webhook (FastAPI → n8n)
            ↓
Agent core: Anthropic SDK tool-use loop (claude-sonnet-4-6)
            ↓
Tools: fetch_product · fetch_reviews_full · check_field · benchmark_against_category
       cluster_review_themes · score_images · check_consistency · evaluate_listing_quality
       draft_rewrite · enqueue_hitl · compare_products
            ↓
Storage: SQLite (products · reviews · corpus+embeddings · hitl_queue · eval_runs · review_themes)
```

**Data ingestion path:** JSON-LD `<script type="application/ld+json">` → primary; RSC flight payload (`__next_f.push`) → metafields; Playwright → fallback if httpx fails.

**Key discovery:** Healf's static HTML pre-renders JSON-LD reviews but the Yotpo widget JS (with app key) is NOT in the server-rendered HTML — must be discovered at runtime via live page fetch or set via `YOTPO_APP_KEY` env var.

## Environment Setup

```bash
cp .env.example .env   # fill in keys
python -m uv sync
python -m uv run playwright install chromium
```

Required env vars:
- `ANTHROPIC_API_KEY` — Anthropic SDK
- `OPENAI_API_KEY` — embeddings (text-embedding-3-small)
- `GEMINI_API_KEY` — vision scoring (Gemini 2.5 Flash)
- `YOTPO_APP_KEY` — Yotpo widget API (discover from live page network tab)
- `HEALF_USER_AGENT` — optional, has sensible default

## Running Things

```bash
# Tests
python -m uv run pytest -v

# Run specific test file
python -m uv run pytest tests/test_models.py -v

# Streamlit chat (once app.py exists, Wave 5.4)
python -m uv run streamlit run app.py

# Build corpus (Wave 4.3 — requires OPENAI_API_KEY)
python -m uv run python scripts/build_corpus.py --target 150 --out corpus.sqlite

# MCP server (Wave 12)
python -m uv run python mcp_server.py

# Webhook server (Wave 13)
python -m uv run uvicorn webhook:app --reload
```

## File Structure

```
healf_agent/
├── __init__.py          ✅ Done
├── models.py            ✅ Done — Product, Image, Review, ReviewTheme, EvalReport, etc.
├── storage.py           ✅ Done — SQLite CRUD for all 6 tables
├── agent.py             🔲 Wave 5 — Anthropic tool-use loop
├── corpus.py            🔲 Wave 4 — Sitemap → sample → embed → kNN
├── voice.py             🔲 Wave 10 — Healf-voice prompts
└── tools/
    ├── __init__.py      🔲 Wave 5 — TOOL_SCHEMAS + dispatcher (partial)
    ├── navigate.py      ✅ Done — httpx fetch + Playwright fallback
    ├── ingest.py        ✅ Done — JSON-LD parse + RSC metafields
    ├── reviews.py       ✅ Done — Yotpo pagination
    ├── review_themes.py 🔲 Wave 6
    ├── benchmark.py     🔲 Wave 7
    ├── vision.py        🔲 Wave 8
    ├── consistency.py   🔲 Wave 8
    ├── evaluate.py      🔲 Wave 7
    ├── act.py           🔲 Wave 9
    ├── compare.py       🔲 Wave 9
    └── field.py         🔲 Wave 5

tests/
├── fixtures/
│   └── lmnt-recharge-electrolytes-variety-pack.html  ✅ (452KB real PDP)
├── test_models.py       ✅ 4 tests
├── test_storage.py      ✅ 4 tests
├── test_navigate.py     ✅ 3 tests
├── test_ingest.py       ✅ 3 tests
└── test_reviews.py      ✅ 1 test

app.py                   🔲 Wave 5.4 — Streamlit chat shell
mcp_server.py            🔲 Wave 12
webhook.py               🔲 Wave 13
pages/hitl.py            🔲 Wave 10
scripts/build_corpus.py  🔲 Wave 4.3
evals/golden.jsonl       🔲 Wave 11
evals/runner.py          🔲 Wave 11
n8n/healf-catalog-audit.json  🔲 Wave 13
```

## Git History (feat-healf-agent branch)

```
6dcbc9b feat(reviews): paginated Yotpo widget API fetcher
ef33240 feat(ingest): metafield extraction from RSC flight payload
1c70f15 feat(ingest): JSON-LD + RSC flight extraction, Product parsing from LMNT fixture
88faaf8 feat(navigate): httpx fetch with Playwright fallback + URL normalisation
eae59c8 test(fixtures): capture LMNT PDP HTML for ingestion tests
fa97ec5 feat(storage): SQLite schema and CRUD for products, reviews, corpus, HITL
ee3ff91 feat(models): Pydantic v2 schema for product, review, eval, consistency, HITL
52a6125 build: package skeleton and README
c907eae build: env template and gitignore
5cc6321 build: initialise uv project with full dependency set
e9a9f3c docs: import Tier 1 superpowers plan into repo
34871b8 Initial commit: assignment brief and CV (planning workspace)
```

## Build Plan — Tier Status

**Tier 1 (Foundation) — IN PROGRESS**

| Wave | Tasks | Status |
|------|-------|--------|
| 0 — Scaffold | 0.1–0.5 | ✅ Complete |
| 1 — Models + Storage | 1.1–1.2 | ✅ Complete |
| 2 — Ingestion | 2.1–2.4 | ✅ Complete |
| 3 — Reviews | 3.1–3.2 | ✅ Complete |
| 4 — Corpus | 4.1–4.3 | 🔲 Next |
| 5 — Agent core | 5.1–5.5 | 🔲 Next |

**Tier 2 (Analytical depth) — Wave 6–9 — Planned**
**Tier 3 (AI-as-colleague proof) — Wave 10–13 — Planned**
**Tier 4 (Polish) — Wave 14 — Planned**

## Key Decisions

- **Stack:** Python 3.11+ + Anthropic SDK + Pydantic v2 + SQLite (not PostgreSQL — ship corpus.sqlite in repo)
- **`uv` invocation:** `python -m uv` (not bare `uv`) on this machine
- **No vanilla Shopify JSON endpoint:** Healf uses Next.js App Router; JSON-LD is the data source
- **Yotpo key:** Not in static HTML; must come from `YOTPO_APP_KEY` env var
- **Currency clamping:** `_KNOWN_CURRENCIES = {"GBP", "USD", "EUR"}` in ingest.py to prevent Pydantic ValidationError
- **Test fixture:** `lmnt-recharge-electrolytes-variety-pack.html` force-committed despite .gitignore
- **Execution mode:** superpowers:subagent-driven-development — one subagent per task, spec + quality review after each

## Workflow for Next Session

1. Resume in the worktree: `C:\Users\Daran\AI\Healf AI Agent\.claude\worktrees\feat-healf-agent`
2. Verify tests: `python -m uv run pytest -v` (should be 15 passing)
3. Use `superpowers:subagent-driven-development` to continue from **Task 4.1**
4. See handoff document: `docs/handoff/2026-05-15-session-1-handoff.md`

## Reference Product (LMNT — golden fixture)

- URL: `https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack`
- GID: `gid://shopify/Product/7620180541679`
- Rating: 4.9 / 445 reviews
- Price: £18.99 GBP
- Brand: LMNT
- Category: Electrolytes
