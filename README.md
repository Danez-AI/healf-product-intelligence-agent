# Healf Product Intelligence Agent

A natural-language agent for the Healf health & wellness marketplace. Load any Healf product URL and ask questions in plain English: the agent evaluates listings against the full site corpus, spots copy gaps, scores images via Gemini Vision, clusters review themes, drafts Healf-voice rewrites, and queues suggested edits for human review — all surfaced through a Streamlit chat, an MCP server, and an n8n catalog-audit workflow.

## Status

✅ **Feature-complete.** 57 tests passing. Tier 1–3 shipped (Waves 0–14).

## Architecture

```
Surfaces:   Streamlit chat  │  MCP server (FastMCP)  │  HTTP webhook (FastAPI → n8n)
                             ↓
Agent core: Anthropic SDK tool-use loop (claude-sonnet-4-6)
                             ↓
Tools:      fetch_product · fetch_reviews_full · check_field · benchmark_against_category
            cluster_review_themes · score_images · check_consistency · evaluate_listing_quality
            draft_rewrite · enqueue_hitl · compare_products
                             ↓
Storage:    SQLite  (products · reviews · corpus+embeddings · hitl_queue · eval_runs · review_themes)
```

## Quick Start

```bash
python -m uv sync
python -m uv run playwright install chromium
cp .env.example .env   # fill in 4 API keys (see table below)
python -m uv run pytest -v
python -m uv run streamlit run app.py
```

## Required Environment Variables

| Variable | Purpose | Required for |
|----------|---------|--------------|
| `ANTHROPIC_API_KEY` | Agent LLM + eval LLM judge | Core agent, evals (eval-007, eval-009) |
| `OPENAI_API_KEY` | Corpus embeddings (text-embedding-3-small) | Corpus kNN, benchmark, cluster |
| `GEMINI_API_KEY` | Image scoring (Gemini 2.5 Flash) | `score_images` (eval-006) |
| `YOTPO_APP_KEY` | Yotpo review API | `fetch_reviews_full` |

`HEALF_USER_AGENT` is optional (sensible default included in `.env.example`).

## Surfaces

The same agent core is reachable three ways:

### 1. Streamlit chat
```bash
python -m uv run streamlit run app.py
```
HITL queue at `pages/hitl.py` (sidebar nav). See `docs/gotchas.md` G-19 for stale-process cleanup.

### 2. MCP server
```bash
python -m uv run python mcp_server.py
```
Stdio transport. Clients (Claude Desktop, Claude Code, n8n MCP node) call `set_current_product(url)` once, then any of the 10 agent tools.

### 3. Webhook + n8n
```bash
python -m uv run uvicorn webhook:app --host 0.0.0.0 --port 8000
```
`POST /audit {url, draft?}` runs the full audit chain. Import `n8n/healf-catalog-audit.json` into n8n; set `HEALF_WEBHOOK_URL` and `SLACK_WEBHOOK_URL` env vars on the n8n instance.

## Evals

```bash
python -m uv run python -m evals.runner
```
Reads `evals/golden.jsonl` (9 cases, one per tool dimension), persists to the `eval_runs` SQLite table, exits non-zero on any failure.

## Examples

See `examples/` for annotated walkthroughs of the seven core tool paths:

| File | Prompt | Tools fired |
|------|--------|-------------|
| `01-ingredient-check.md` | "Does this have sodium?" | `check_field` |
| `02-full-evaluation.md` | "Evaluate this listing" | `evaluate_listing_quality`, `benchmark_against_category`, `cluster_review_themes` |
| `03-image-score.md` | "How good are the product images?" | `score_images` |
| `04-rewrite.md` | "Draft a better product description" | `draft_rewrite`, `enqueue_hitl` |
| `05-compare.md` | "Compare LMNT vs Humantra electrolytes" | `compare_products` |
| `06-consistency.md` | "Are the claims consistent across the listing?" | `check_consistency` |
| `07-review-themes.md` | "What do customers love and hate?" | `cluster_review_themes`, `fetch_reviews_full` |

## Roadmap

This MVP demonstrates the core Navigate / Ingest / Evaluate / Act loop. The natural next milestones for a production AI Transformation Team:

| Month | Milestone |
|-------|-----------|
| 1 | **Catalog audit bot** — scheduled n8n workflow scans all product pages nightly, flags newly incomplete listings, posts digest to Slack |
| 2 | **Rewrite bot** — auto-drafts copy improvements for flagged listings, queues for human approval via the HITL interface |
| 3 | **SEO + completeness bot** — benchmarks each listing against top-ranked competitors, generates structured completeness scores and keyword gap reports |

Beyond month 3: brand onboarding assistant, cross-category comparison agent, review-insight digest, image quality monitor.
