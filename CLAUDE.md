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
├── voice.py             ✅ Done — Healf-voice prompts (Wave 10)
└── tools/
    ├── __init__.py      ✅ Done — TOOL_SCHEMAS + dispatcher
    ├── navigate.py      ✅ Done — httpx fetch + Playwright fallback
    ├── ingest.py        ✅ Done — JSON-LD parse + RSC metafields
    ├── reviews.py       ✅ Done — Yotpo pagination
    ├── field.py         ✅ Done — check_field exact lookups
    ├── review_themes.py ✅ Done — cluster_review_themes (Wave 6)
    ├── benchmark.py     ✅ Done — benchmark_against_category (Wave 7)
    ├── vision.py        ✅ Done — score_images/Gemini Vision (Wave 8)
    ├── consistency.py   ✅ Done — check_consistency (Wave 8)
    ├── evaluate.py      ✅ Done — evaluate_listing_quality (Wave 7)
    ├── act.py           ✅ Done — draft_rewrite + enqueue_hitl (Wave 9)
    └── compare.py       ✅ Done — compare_products (Wave 9)

tests/
├── fixtures/
│   └── lmnt-recharge-electrolytes-variety-pack.html  ✅ (452KB real PDP)
├── test_models.py       ✅ 4 tests
├── test_storage.py      ✅ 7 tests (+3 HITL CRUD)
├── test_navigate.py     ✅ 3 tests
├── test_ingest.py       ✅ 3 tests
├── test_reviews.py      ✅ 1 test
├── test_corpus.py       ✅ 5 tests
├── test_review_themes.py ✅ 2 tests
├── test_voice.py        ✅ 4 tests (Wave 10 — new)
└── test_agent.py        ✅ 13 tests (Tier 1: 5, Tier 2: 8)

app.py                   ✅ Done — Streamlit chat shell; uses st.navigation() API (G-18)
corpus.sqlite            ✅ Done — 150 products pre-built
scripts/build_corpus.py  ✅ Done — CLI for corpus rebuild
docs/gotchas.md          ✅ Running log of surprises and fixes
mcp_server.py            🔲 Wave 12
webhook.py               🔲 Wave 13
pages/hitl.py            ✅ Done — Streamlit HITL review queue (Wave 10) ⚠️ G-17 runtime bug
evals/golden.jsonl       🔲 Wave 11
evals/runner.py          🔲 Wave 11
n8n/healf-catalog-audit.json  🔲 Wave 13
```

## Build Plan — Tier Status

**Tier 1 (Foundation) — ✅ COMPLETE** — tagged `tier-1-complete`

| Wave | Tasks | Status |
|------|-------|--------|
| 0 — Scaffold | 0.1–0.5 | ✅ Complete |
| 1 — Models + Storage | 1.1–1.2 | ✅ Complete |
| 2 — Ingestion | 2.1–2.4 | ✅ Complete |
| 3 — Reviews | 3.1–3.2 | ✅ Complete |
| 4 — Corpus | 4.1–4.3 | ✅ Complete |
| 5 — Agent core | 5.1–5.5 | ✅ Complete |

**Tier 2 (Analytical depth) — ✅ COMPLETE** — tagged `tier-2-complete`

| Wave | Tasks | Status |
|------|-------|--------|
| 6 — Review-theme clustering | `cluster_review_themes` | ✅ Complete |
| 7 — Benchmark + evaluate | `benchmark_against_category`, `evaluate_listing_quality` | ✅ Complete |
| 8 — Vision + consistency | `score_images`, `check_consistency` | ✅ Complete |
| 9 — Compare + act | `compare_products`, `draft_rewrite`, `enqueue_hitl` | ✅ Complete |

**Tier 3 (AI-as-colleague proof) — Wave 10–13 — ✅ COMPLETE** — tagged `wave-13-complete` — 56 tests passing

| Wave | Tasks | Status |
|------|-------|--------|
| 10 — HITL + voice | `pages/hitl.py`, `healf_agent/voice.py` | ✅ Complete — tagged `wave-10-complete` |
| 11 — Evals | `evals/golden.jsonl`, `evals/runner.py` | ✅ Complete — 8 new tests |
| 12 — MCP server | `mcp_server.py` | ✅ Complete — 3 new tests |
| 13 — n8n webhook | `webhook.py`, `n8n/healf-catalog-audit.json` | ✅ Complete — 3 new tests; tagged `wave-13-complete` |

**Tier 4 (Polish) — Wave 14 — ✅ COMPLETE** — tagged `wave-14-final` — 57 tests passing

| Task | Files | Status |
|------|-------|--------|
| README rewrite | `README.md` | ✅ Status banner, arch diagram, Quick Start, env vars table |
| Eval filter fix (G-20) | `evals/runner.py`, `tests/test_evals.py` | ✅ Exact comma-separated match; regression test |
| fastmcp dep fix (G-21) | `pyproject.toml`, `uv.lock` | ✅ `fastmcp-slim[server]>=3.3.0` |
| Submission checklist | `docs/submission-checklist.md` | ✅ New file |
| Gotchas update | `docs/gotchas.md` | ✅ G-20 resolved, G-21 added |
| examples/ (7 demo runs) | `examples/01–07.md` | ✅ All 7 tool paths covered |
| README 3-month roadmap | `README.md` | ✅ Examples table + Roadmap section added |
| docs/decisions.md ADRs | `docs/decisions.md` | ✅ 5 ADRs: SQLite, fastmcp, JSON-LD, 3 surfaces, tool-use loop |

**Post-submission bugfix (Session 9) — 2026-05-16**

| Fix | Files | Status |
|-----|-------|--------|
| G-22: `fetch_product_page` UnboundLocalError in `dispatch_tool` | `healf_agent/tools/__init__.py` line 233 | ✅ Removed redundant local import |
| G-23: Windows Firewall blocks port 8000 from n8n homeserver | `docs/n8n-setup.md` | ✅ Firewall rule added (Session 10) |
| G-24: `uv --env-file` chokes on `HEALF_USER_AGENT` URL value | `.env` | ⚠️ Warning only — API keys still load |
| G-25: Stale Python process holds port 8000 between sessions | kill PID via netstat | ✅ Documented |
| G-26: n8n-mcp API tools unavailable — no `.mcp.json` for project | `C:\Users\Daran\AI\Healf AI Agent\.mcp.json` | ✅ Created (restart Claude Code to activate) |
| G-27: Split In Batches v3 skips batch output in manual test mode | `n8n/healf-catalog-audit.json` | ✅ Removed from live workflow — URL List → POST /audit direct |
| G-28: IF node errors with `caseSensitive` undefined when score is string-typed | n8n IF node — "Convert types where required" toggle | ✅ Enabled toggle; all 6 nodes green (Session 11) |

**n8n end-to-end test status: COMPLETE ✅** — All 6 nodes green confirmed 2026-05-16 Session 11. Score 2 < 3 → true branch → Notify Slack (fails gracefully). Workflow versionId: `0292c2e7-78c0-42b9-9d35-6a2753456dc4`.

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
- **Metafield extraction:** Shopify embeds metafields as `{"key":K,"value":V}` objects inside a `"metafields":[...]` array in the RSC payload — NOT as direct JSON properties. `extract_metafields` uses balanced-bracket JSON slicing anchored on `"metafields":[` (see `tools/ingest.py` and G-29 in gotchas.md). Regex on the array body is fragile and was the root cause of the ingredient extraction bug (G-10/G-29).
- **Product loading:** All product fetching goes through `load_full_product(url) -> Product` in `healf_agent/tools/ingest.py`. Both `app.py` (Streamlit Fetch button) and `dispatch_tool("fetch_product")` call this helper — do not inline this logic anywhere else. Two diverged copies caused the Wave 16 regression (G-30).

## Workflow for Next Session

1. Resume in the worktree: `C:\Users\Daran\AI\Healf AI Agent\.claude\worktrees\feat-healf-agent`
2. Verify tests: `python -m uv run pytest -v` (should be 56 passing)
3. **Kill stale Streamlit processes (G-19):** run the PowerShell cleanup from `docs/gotchas.md` G-19 before any smoke testing
4. **Wave 14 (Polish) or submission prep** — see `docs/handoff/2026-05-16-session-5-handoff.md` for context
5. Use context-mode skill when needed to ensure context preservation in between sessions

## Reference Product (LMNT — golden fixture)

- URL: `https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack`
- GID: `gid://shopify/Product/7620180541679`
- Rating: 4.9 / 445 reviews
- Price: £18.99 GBP
- Brand: LMNT
- Category: Electrolytes
