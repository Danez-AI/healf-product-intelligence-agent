# Session 5 Handoff — 2026-05-16

## What Was Built This Session

### Wave 10.5 smoke test — COMPLETE

Full end-to-end smoke test of the Wave 10 HITL flow, driven by Playwright CLI:

1. **G-17 fixed** — reordered imports in `app.py` so all `healf_agent.*` imports come before `from pages.hitl import run as hitl_run`. Committed: `3a10e43`.
2. **Root cause confirmed** — G-17 was caused by stale Streamlit processes (8 PIDs on port 8501 from previous sessions) serving old in-memory module state. Fixed by killing all PIDs and restarting clean.
3. **Smoke test results** — all steps passed:
   - Chat page loads with sidebar nav (Chat + HITL Review)
   - LMNT product fetches (4.9★, 445 reviews, £18.99)
   - Agent produces full diagnostic + Healf-voice rewrite with editorial warnings
   - `enqueue_hitl` writes to `hitl_queue` (confirmed via DB query)
   - HITL Review page loads without error
   - Two-column view (Original vs Drafted) renders correctly
   - "Save as edited" action flips status → `edited`, persists `reviewer_note` + `reviewed_at`
   - Pending count drops to 0 after action, page reruns correctly

4. **`wave-10-complete` tag** — applied to `3a10e43` (force-updated from stale pointer).

### Tests: 42 passing (unchanged)

### Git commits this session

```
3a10e43 fix(app): reorder imports so healf_agent.* loads before pages.hitl (G-17)
```

---

## New Gotcha: G-19

**Multiple stale Streamlit processes on port 8501** — see `docs/gotchas.md` G-19.

---

## What to Do Next

### Wave 11 — Golden-set evals

Author **Plan 4** before writing any code. Scope for Plan 4:

| Wave | Task | Files |
|------|------|-------|
| 11 | Golden-set evals | `evals/golden.jsonl`, `evals/runner.py`, `tests/test_evals.py` |
| 12 | MCP server | `mcp_server.py`, `tests/test_mcp.py` |
| 13 | n8n webhook | `webhook.py`, `n8n/healf-catalog-audit.json`, `tests/test_webhook.py` |

**Wave 11 design notes:**

- `evals/golden.jsonl` — 8+ cases, one per tool dimension: `field_accuracy`, `benchmark_quality`, `theme_clustering`, `listing_evaluation`, `image_scoring`, `consistency_check`, `draft_quality`, `compare_products`, `enqueue_hitl`
- Each case: `{"id": "eval-001", "tool": "check_field", "input": {...}, "expect": {"contains": [...]} }`
- `evals/runner.py` — loads cases, dispatches via `dispatch_tool`, runs judge (exact/contains/len/llm), records to `eval_runs` table, prints pass/fail summary
- LLM judge only for `draft_quality` (uses Anthropic API with simple rubric)
- `tests/test_evals.py` — 3-4 tests: loader, mock-dispatch runner, summary format

**Wave 12 design notes:**

- FastMCP — `pip install fastmcp` (check pyproject.toml first)
- Expose all 10 tools as `@mcp.tool()` decorated functions
- Reuse dispatcher logic from `healf_agent/tools/__init__.py`
- Runnable: `python -m uv run python mcp_server.py`

**Wave 13 design notes:**

- FastAPI webhook: `POST /audit {url}` → runs full chain → returns `{product_title, eval_score, hitl_id, draft}`
- n8n workflow: Schedule trigger → static URL list → HTTP Request node → Slack/webhook notification
- n8n JSON exported from n8n UI (can be handcrafted JSON matching n8n schema)

---

## Critical Context for Next Session

### Environment
- **Worktree:** `C:\Users\Daran\AI\Healf AI Agent\.claude\worktrees\feat-healf-agent`
- **Branch:** `worktree-feat-healf-agent`
- **uv invocation:** `python -m uv` — bare `uv` NOT in PATH
- **Python:** 3.14.0
- **Streamlit:** running on port 8501 (started via PowerShell `Start-Process`)
- **Tests:** 42 passing

### Stale process warning (G-19)

Before starting Streamlit for any future smoke test:
```powershell
Get-NetTCPConnection -LocalPort 8501 -State Listen | Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
```
Then start fresh:
```powershell
Start-Process -FilePath "python" -ArgumentList "-m","uv","run","streamlit","run","app.py","--server.headless","true","--server.port","8501" -WorkingDirectory $worktree -WindowStyle Hidden
```

### HITL DB state

`healf.sqlite` has 1 HITL entry (id=1, status=`edited`) from the smoke test. Safe to leave — runner uses a fresh in-memory DB for evals.

### playwright-cli headed mode

playwright-cli always runs headless (no `--headed` flag supported). Use `playwright-cli screenshot` after each key step to show the user visual progress. The browser IS visible in the user's environment despite `headed: false` in the session info.

### Agent behaviour note

When asked "draft a rewrite addressing missing ingredients", the agent correctly asks for exact ingredient data before drafting (no hallucination guardrail). To trigger `draft_rewrite + enqueue_hitl` in smoke test, follow up with: "Please proceed with the draft using available information. Note gaps as editorial warnings. Submit to HITL queue."
