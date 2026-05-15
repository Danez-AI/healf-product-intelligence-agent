# Healf Product Intelligence Agent

A natural-language agent for Healf product pages — answers questions, evaluates listings against the site corpus, drafts copy improvements, and surfaces them through a Streamlit chat, an MCP server, and an n8n catalog-audit workflow.

## Status

Tier 1 (foundation) in progress. See `docs/superpowers/plans/` for the live build plans.

## Quickstart

```bash
python -m uv sync
python -m uv run playwright install chromium
cp .env.example .env  # fill in keys
python -m uv run streamlit run app.py
```

## Architecture

See `docs/superpowers/plans/2026-05-15-healf-product-intelligence-agent.md`.

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
