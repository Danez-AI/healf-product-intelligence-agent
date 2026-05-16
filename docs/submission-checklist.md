# Wave 14 Submission Checklist

Verified 2026-05-16 before tagging `wave-14-complete`.

| # | Item | Status | How verified |
|---|------|--------|--------------|
| 1 | 57 tests passing | ✅ | `python -m uv run pytest -v` |
| 2 | `corpus.sqlite` (150 products, 1.29 MB) committed | ✅ | `git ls-files corpus.sqlite` returns path |
| 3 | `.env.example` lists all 4 required keys | ✅ | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `YOTPO_APP_KEY` all present |
| 4 | README has Quick Start + architecture diagram | ✅ | README.md rewritten in Wave 14 |
| 5 | Eval `--filter` no longer hits G-20 substring trap | ✅ | `test_filter_exact_match_excludes_eval_009` passes |
| 6 | `mcp_server.py` boots on stdio without crashing | ✅ | `python -m uv run python mcp_server.py` — Ctrl-C after banner |
| 7 | `webhook:app` boots and `/audit {}` returns HTTP 422 | ✅ | `uvicorn webhook:app --port 8000` + curl/Invoke-RestMethod |
| 8 | `fastmcp-slim[server]>=3.3.0` in `pyproject.toml` | ✅ | Explicit server extra required for `from fastmcp import FastMCP` (slim variant omits server by default) |
| 9 | All gotchas resolved or documented | ✅ | G-17 fixed, G-18 fixed, G-19 documented, G-20 resolved |
| 10 | Three-surface walkthrough in README | ✅ | Streamlit / MCP / Webhook+n8n sections present |

## Running the three surfaces

```powershell
# 1. Streamlit chat (kill stale PIDs first — see G-19 in docs/gotchas.md)
python -m uv run streamlit run app.py

# 2. MCP server (stdio transport — connect via Claude Desktop or Claude Code)
python -m uv run python mcp_server.py

# 3. Webhook + n8n
python -m uv run uvicorn webhook:app --host 0.0.0.0 --port 8000
# POST /audit {"url": "https://healf.com/en-uk/products/<handle>"}
# Import n8n/healf-catalog-audit.json into n8n for the scheduled audit workflow
```

## Running evals

```powershell
# Deterministic subset only (no API keys needed)
python -m uv run python -m evals.runner --filter eval-001,eval-002,eval-007 --db healf.sqlite

# Full suite (requires all 4 API keys in .env)
python -m uv run python -m evals.runner --db healf.sqlite
```
