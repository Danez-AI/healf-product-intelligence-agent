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
├── agent.py             ✅ Done — Anthropic tool-use loop + SYSTEM_PROMPT
├── corpus.py            ✅ Done — Sitemap → sample → embed → kNN
├── voice.py             🔲 Wave 10 — Healf-voice prompts
└── tools/
    ├── __init__.py      ✅ Done — TOOL_SCHEMAS + dispatcher
    ├── navigate.py      ✅ Done — httpx fetch + Playwright fallback
    ├── ingest.py        ✅ Done — JSON-LD parse + RSC metafields
    ├── reviews.py       ✅ Done — Yotpo pagination
    ├── field.py         ✅ Done — check_field exact lookups
    ├── review_themes.py 🔲 Wave 6
    ├── benchmark.py     🔲 Wave 7
    ├── vision.py        🔲 Wave 8
    ├── consistency.py   🔲 Wave 8
    ├── evaluate.py      🔲 Wave 7
    ├── act.py           🔲 Wave 9
    └── compare.py       🔲 Wave 9

tests/
├── fixtures/
│   └── lmnt-recharge-electrolytes-variety-pack.html  ✅ (452KB real PDP)
├── test_models.py       ✅ 4 tests
├── test_storage.py      ✅ 4 tests
├── test_navigate.py     ✅ 3 tests
├── test_ingest.py       ✅ 3 tests
├── test_reviews.py      ✅ 1 test
├── test_corpus.py       ✅ 5 tests
└── test_agent.py        ✅ 5 tests

app.py                   ✅ Done — Streamlit chat shell (smoke tested)
corpus.sqlite            ✅ Done — 150 products pre-built
scripts/build_corpus.py  ✅ Done — CLI for corpus rebuild
docs/gotchas.md          ✅ Running log of surprises and fixes
mcp_server.py            🔲 Wave 12
webhook.py               🔲 Wave 13
pages/hitl.py            🔲 Wave 10
evals/golden.jsonl       🔲 Wave 11
evals/runner.py          🔲 Wave 11
n8n/healf-catalog-audit.json  🔲 Wave 13
```

## Build Plan — Tier Status

**Tier 1 (Foundation) — ✅ COMPLETE** — tagged `tier-1-complete` — 25 tests passing

| Wave | Tasks | Status |
|------|-------|--------|
| 0 — Scaffold | 0.1–0.5 | ✅ Complete |
| 1 — Models + Storage | 1.1–1.2 | ✅ Complete |
| 2 — Ingestion | 2.1–2.4 | ✅ Complete |
| 3 — Reviews | 3.1–3.2 | ✅ Complete |
| 4 — Corpus | 4.1–4.3 | ✅ Complete |
| 5 — Agent core | 5.1–5.5 | ✅ Complete |

**Tier 2 (Analytical depth) — IN PROGRESS**

| Wave | Tasks | Status |
|------|-------|--------|
| 6 — Review-theme clustering | `cluster_review_themes` | 🔲 Next |
| 7 — Benchmark + evaluate | `benchmark_against_category`, `evaluate_listing_quality` | 🔲 Planned |
| 8 — Vision + consistency | `score_images`, `check_consistency` | 🔲 Planned |
| 9 — Compare + act | `compare_products`, `draft_rewrite`, `enqueue_hitl` | 🔲 Planned |

**Tier 3 (AI-as-colleague proof) — Wave 10–13 — Planned**
**Tier 4 (Polish) — Wave 14 — Planned**

## Key Decisions

- **Stack:** Python 3.11+ + Anthropic SDK + Pydantic v2 + SQLite (not PostgreSQL — ship corpus.sqlite in repo)
- **`uv` invocation:** `python -m uv` (not bare `uv`) on this machine
- **No vanilla Shopify JSON endpoint:** Healf uses Next.js App Router; JSON-LD is the data source
- **Yotpo key:** `bgzgoRGnLi5wOF0jyQdbzIfRCFKCpcmV701bZUJP` — set as `YOTPO_APP_KEY` in `.env`
- **Yotpo CDN host:** DevTools shows `api-cdn.yotpo.com`; code uses `api.yotpo.com` — both work
- **Currency clamping:** ingest.py clamps unknown currencies to `"GBP"` to satisfy Pydantic Literal
- **Test fixture:** `lmnt-recharge-electrolytes-variety-pack.html` force-committed despite .gitignore
- **corpus.sqlite product_type:** All 150 entries are "Unknown" — Healf JSON-LD has no `category` field. Fix needed in Wave 7 before kNN type-filtering is meaningful.
- **Product context injection:** `app.py` prepends product title/brand/URL/ingredients/claims to every user message so the agent knows what's loaded
- **Execution mode:** superpowers:subagent-driven-development — one subagent per task, spec + quality review after each
- **Gotchas log:** `docs/gotchas.md` — running log of surprises and fixes

## Workflow for Next Session

1. Resume in the worktree: `C:\Users\Daran\AI\Healf AI Agent\.claude\worktrees\feat-healf-agent`
2. Verify tests: `python -m uv run pytest -v` (should be 25 passing)
3. Use `superpowers:subagent-driven-development` to continue Tier 2 from **Wave 6**
4. Plan 2 document needed before Wave 6 — author it first

## Reference Product (LMNT — golden fixture)

- URL: `https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack`
- GID: `gid://shopify/Product/7620180541679`
- Rating: 4.9 / 445 reviews
- Price: £18.99 GBP
- Brand: LMNT
- Category: Electrolytes
