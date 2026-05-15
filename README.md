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
