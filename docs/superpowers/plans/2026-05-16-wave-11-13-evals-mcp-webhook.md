# Plan 4 — Wave 11–13: Evals, MCP Server, n8n Webhook

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish Tier 3 of the Healf Product Intelligence Agent — ship a golden-set eval harness (Wave 11), expose all 10 tools as an MCP server (Wave 12), and add a FastAPI `/audit` webhook plus n8n companion workflow (Wave 13) — so the same agent core is reachable from three surfaces: Streamlit chat (already shipped), MCP clients, and n8n catalog-audit automation.

**Architecture:**
- **Wave 11:** `evals/runner.py` reads `evals/golden.jsonl`, dispatches each case through `healf_agent.tools.dispatch_tool` (with a mocked `Product` when needed), grades via deterministic judges (`exact`, `contains`, `len_gte`) plus a single LLM-rubric judge for `draft_quality`, persists each result to the existing `eval_runs` SQLite table, prints a pass/fail summary, and exits non-zero if any case fails.
- **Wave 12:** `mcp_server.py` instantiates a `FastMCP` server and registers one `@mcp.tool()` per existing Healf tool. Each MCP tool is a thin wrapper around `dispatch_tool` — same surface, same product-context contract.
- **Wave 13:** `webhook.py` exposes `POST /audit {url, question?}` on FastAPI; the handler runs `fetch_product` → `evaluate_listing_quality` → optionally `draft_rewrite` → `enqueue_hitl`, returns `{product_handle, eval_score, hitl_id, draft}`. `n8n/healf-catalog-audit.json` is a hand-written n8n workflow (Schedule → SplitInBatches over URL list → HTTP Request to `/audit` → IF score<3 → Slack notification) importable into n8n via UI.

**Tech Stack:** Python 3.11+ · `pytest` · `fastmcp>=0.2.0` (already in `pyproject.toml`) · `fastapi` + `uvicorn` + `httpx` (TestClient) · n8n workflow JSON (hand-crafted, matches n8n v1.x schema) · existing `Anthropic` client for LLM judge.

**Plan location:** This file lives at `C:\Users\Daran\.claude\plans\continue-partitioned-cosmos.md` during plan-mode review. **First execution step** copies it to `docs/superpowers/plans/2026-05-16-wave-11-13-evals-mcp-webhook.md` in the worktree.

**Plan series:** Plan 4 of 4. Plans 1–3 covered Tiers 1–2 + Wave 10 (HITL + voice). This plan closes out Tier 3.

---

## Context

Tier 1 (foundation) and Tier 2 (analytical depth) are shipped. Wave 10 (HITL queue + Healf-voice rewrites) was smoke-tested end-to-end on 2026-05-16. The remaining Tier 3 work is what turns the agent from "a Streamlit demo" into "a colleague reachable from any tool the team already uses":

1. **Evals (Wave 11)** — without a deterministic golden set, every tool change is a regression risk. The handoff design calls for one case per dimension (`field_accuracy`, `benchmark_quality`, `theme_clustering`, `listing_evaluation`, `image_scoring`, `consistency_check`, `draft_quality`, `compare_products`, `enqueue_hitl`).
2. **MCP server (Wave 12)** — Healf's brief frames AI as "functional colleagues with tools and documentation". Exposing the tools over MCP lets Claude Desktop / Claude Code / n8n MCP nodes call them directly. FastMCP is already declared in `pyproject.toml`.
3. **Webhook + n8n (Wave 13)** — a one-shot HTTP endpoint that runs the full audit chain unlocks scheduled batch audits (the "catalog-audit companion" referenced in the assignment).

**Worktree:** `C:\Users\Daran\AI\Healf AI Agent\.claude\worktrees\feat-healf-agent`
**Branch:** `worktree-feat-healf-agent`
**Baseline:** 42 tests passing on commit `3a10e43` (tagged `wave-10-complete`).
**uv invocation:** `python -m uv` (bare `uv` not in PATH).

**Test-baseline guard:** every task ends by re-running `python -m uv run pytest -v` to confirm the running total has only grown.

---

## File Structure

| Path | Wave | Responsibility |
|------|------|----------------|
| `docs/superpowers/plans/2026-05-16-wave-11-13-evals-mcp-webhook.md` | (meta) | Canonical plan location once execution starts |
| `evals/__init__.py` | 11 | Package marker (empty) |
| `evals/golden.jsonl` | 11 | One JSON-per-line case file. 9 cases, one per tool dimension. Each row: `{"id", "tool", "input", "fixture", "judge", "expect"}` |
| `evals/runner.py` | 11 | Loader, judges (`exact`, `contains`, `len_gte`, `llm_rubric`), dispatcher wrapper that supplies a stub `Product` for product-scoped tools, SQLite persistence (`eval_runs`), CLI (`__main__`), pass/fail summary with non-zero exit on failure |
| `tests/test_evals.py` | 11 | 4 tests: (a) loader parses 9 cases, (b) `judge_contains` / `judge_exact` / `judge_len_gte` correctness, (c) runner.run_case dispatches through a fake dispatcher and records to `eval_runs`, (d) summary returns exit code 1 when any case fails |
| `mcp_server.py` | 12 | FastMCP server with one `@mcp.tool` per Healf tool — each wraps `dispatch_tool`. Reads product state from a process-local `_current_product` set by a `set_current_product(url)` MCP tool |
| `tests/test_mcp.py` | 12 | 2 tests: (a) `mcp.list_tools()` returns the expected 11 names (10 + `set_current_product`), (b) calling a stub tool via the MCP instance returns a dict |
| `webhook.py` | 13 | FastAPI app with `POST /audit` and `GET /health`. `/audit` body: `{url: str, question?: str, draft?: bool}` → response `{product_handle, score, gaps, hitl_id?, draft?}` |
| `tests/test_webhook.py` | 13 | 3 tests: (a) `/health` returns 200 `{"status": "ok"}`, (b) `/audit` with monkeypatched `dispatch_tool` runs the chain and returns expected keys, (c) `/audit` 400 on invalid URL |
| `n8n/healf-catalog-audit.json` | 13 | Hand-crafted n8n v1.x workflow JSON: Schedule trigger (daily 09:00 UTC) → static `urls` array → SplitInBatches → HTTP Request `POST {{ $env.HEALF_WEBHOOK }}/audit` → IF `$json.score < 3` → Slack webhook node |
| `README.md` | 13 | Append a "Surfaces" section documenting Streamlit / MCP / webhook + n8n setup |
| `CLAUDE.md` | 13 | Flip Wave 11/12/13 status to ✅ Complete; bump test count |

---

## Test-Driven Execution Model

Every task follows the TDD loop:
1. Write the failing test
2. `python -m uv run pytest tests/<file>::<name> -v` → expect FAIL
3. Write the minimal implementation
4. `python -m uv run pytest tests/<file>::<name> -v` → expect PASS
5. Run the full suite: `python -m uv run pytest -v` → expect baseline + new tests passing
6. `git add` + `git commit`

Subagents executing this plan: do **not** skip the failing-test step. The deliberate-failure check is the only way to catch tests that pass by accident (typo in name, no assertion, etc).

---

# Wave 11 — Golden-set Evals

### Task 11.0: Copy plan into the worktree

**Files:**
- Copy: `C:\Users\Daran\.claude\plans\continue-partitioned-cosmos.md` → `docs/superpowers/plans/2026-05-16-wave-11-13-evals-mcp-webhook.md`

- [ ] **Step 1: Copy the plan**

```powershell
Copy-Item "C:\Users\Daran\.claude\plans\continue-partitioned-cosmos.md" `
          "docs\superpowers\plans\2026-05-16-wave-11-13-evals-mcp-webhook.md"
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-05-16-wave-11-13-evals-mcp-webhook.md
git commit -m "docs(plan): add Plan 4 — Wave 11-13 evals, MCP server, webhook"
```

---

### Task 11.1: Scaffold `evals/` package + golden.jsonl

**Files:**
- Create: `evals/__init__.py` (empty)
- Create: `evals/golden.jsonl`

- [ ] **Step 1: Create `evals/__init__.py`**

Content: a single line.

```python
"""Golden-set evals for the Healf agent."""
```

- [ ] **Step 2: Create `evals/golden.jsonl`** with 9 cases (one per tool dimension)

Each line is a complete JSON object. Use this exact content (newline between rows, no trailing comma):

```jsonl
{"id":"eval-001","tool":"check_field","fixture":"lmnt","input":{"field":"ingredient","value":"sodium"},"judge":"exact","expect":{"path":"present","equals":true}}
{"id":"eval-002","tool":"check_field","fixture":"lmnt","input":{"field":"ingredient","value":"unicorn dust"},"judge":"exact","expect":{"path":"present","equals":false}}
{"id":"eval-003","tool":"benchmark_against_category","fixture":"lmnt","input":{"k":3},"judge":"len_gte","expect":{"path":"neighbours","min":1}}
{"id":"eval-004","tool":"cluster_review_themes","fixture":"lmnt","input":{"polarity_filter":"all"},"judge":"len_gte","expect":{"path":"themes","min":1}}
{"id":"eval-005","tool":"evaluate_listing_quality","fixture":"lmnt","input":{},"judge":"len_gte","expect":{"path":"scores","min":3}}
{"id":"eval-006","tool":"score_images","fixture":"lmnt","input":{},"judge":"contains","expect":{"path":"summary","substring":"image"}}
{"id":"eval-007","tool":"check_consistency","fixture":"lmnt","input":{},"judge":"len_gte","expect":{"path":"findings","min":0}}
{"id":"eval-008","tool":"compare_products","fixture":null,"input":{"urls":["https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack","https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack"]},"judge":"len_gte","expect":{"path":"rows","min":2}}
{"id":"eval-009","tool":"draft_rewrite","fixture":"lmnt","input":{"gaps":["ingredient transparency","claim grounding"]},"judge":"llm_rubric","expect":{"rubric":"Returns a coherent, Healf-voice product description (≥40 words) that names at least one ingredient gap and avoids invented claims.","min_score":3}}
```

- [ ] **Step 3: Verify file has 9 lines and each line is valid JSON**

```powershell
python -m uv run python -c "import json,pathlib; rows=[json.loads(l) for l in pathlib.Path('evals/golden.jsonl').read_text().splitlines() if l.strip()]; print(len(rows))"
```

Expected output: `9`

- [ ] **Step 4: Commit**

```bash
git add evals/__init__.py evals/golden.jsonl
git commit -m "feat(evals): add 9-case golden set covering all tool dimensions"
```

---

### Task 11.2: Write `tests/test_evals.py` (failing)

**Files:**
- Create: `tests/test_evals.py`

- [ ] **Step 1: Write `tests/test_evals.py`** — all assertions reference modules that don't exist yet, so the test file imports inside each test (so collection itself doesn't blow up)

```python
"""Tests for the eval runner."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_loader_returns_nine_cases() -> None:
    from evals.runner import load_cases

    cases = load_cases(Path("evals/golden.jsonl"))
    assert len(cases) == 9
    ids = {c["id"] for c in cases}
    assert "eval-001" in ids
    assert "eval-009" in ids


def test_judge_exact_passes_on_match() -> None:
    from evals.runner import judge_exact

    ok, detail = judge_exact({"present": True}, {"path": "present", "equals": True})
    assert ok is True
    assert "match" in detail.lower()


def test_judge_contains_finds_substring() -> None:
    from evals.runner import judge_contains

    ok, _ = judge_contains({"summary": "Two images scored"}, {"path": "summary", "substring": "image"})
    assert ok is True


def test_judge_len_gte_passes_when_long_enough() -> None:
    from evals.runner import judge_len_gte

    ok, _ = judge_len_gte({"themes": [1, 2, 3]}, {"path": "themes", "min": 2})
    assert ok is True


def test_run_case_records_to_db(tmp_path, monkeypatch) -> None:
    """run_case should call dispatch_tool, evaluate, and write a row to eval_runs."""
    from evals.runner import run_case
    from healf_agent.storage import Storage

    db_path = tmp_path / "evals.sqlite"
    storage = Storage(db_path)
    storage.init_schema()

    # Stub dispatcher: returns a fixed payload for any tool
    def fake_dispatch(*, name, arguments, product):
        return {"present": True}

    case = {
        "id": "eval-001",
        "tool": "check_field",
        "fixture": "lmnt",
        "input": {"field": "ingredient", "value": "sodium"},
        "judge": "exact",
        "expect": {"path": "present", "equals": True},
    }
    result = run_case(case, storage=storage, run_id="r1", dispatch=fake_dispatch)
    assert result["pass"] is True
    row = storage.conn.execute(
        "SELECT question_id, score FROM eval_runs WHERE run_id = ?", ("r1",)
    ).fetchone()
    assert row["question_id"] == "eval-001"
    assert row["score"] == 1.0


def test_summary_exit_code_is_one_on_failure() -> None:
    from evals.runner import summarise

    results = [{"pass": True}, {"pass": False}, {"pass": True}]
    code = summarise(results, run_id="r1", verbose=False)
    assert code == 1


def test_summary_exit_code_is_zero_on_all_pass() -> None:
    from evals.runner import summarise

    results = [{"pass": True}, {"pass": True}]
    code = summarise(results, run_id="r1", verbose=False)
    assert code == 0
```

- [ ] **Step 2: Run the new tests and confirm they fail**

```powershell
python -m uv run pytest tests/test_evals.py -v
```

Expected: all 7 fail with `ModuleNotFoundError: No module named 'evals.runner'` (collection succeeds because imports are inside functions).

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_evals.py
git commit -m "test(evals): add failing tests for runner, judges, and persistence"
```

---

### Task 11.3: Implement `evals/runner.py`

**Files:**
- Create: `evals/runner.py`

- [ ] **Step 1: Implement the runner**

Write the file with this exact content:

```python
"""Golden-set eval runner.

Usage:
    python -m uv run python -m evals.runner [--db healf.sqlite] [--cases evals/golden.jsonl]

Exit codes:
    0  all cases pass
    1  at least one case failed
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from healf_agent.models import Product
from healf_agent.storage import Storage


# --- Stub product used for product-scoped tool cases ---------------------------------------------

def _lmnt_stub() -> Product:
    return Product(
        url="https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack",
        handle="lmnt-recharge-electrolytes-variety-pack",
        title="LMNT Recharge Electrolytes Variety Pack",
        brand="LMNT",
        product_type="Electrolytes",
        description="Tasty zero-sugar electrolyte mix.",
        price_gbp=18.99,
        currency="GBP",
        sku="lmnt-variety",
        gid="gid://shopify/Product/7620180541679",
        ingredients=["sodium", "potassium", "magnesium"],
        claims=["zero sugar", "no artificial colours"],
        rating_value=4.9,
        rating_count=445,
    )


FIXTURES: dict[str, Callable[[], Product]] = {"lmnt": _lmnt_stub}


# --- Loader --------------------------------------------------------------------------------------

def load_cases(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


# --- Judges --------------------------------------------------------------------------------------

def _walk(obj: Any, path: str) -> Any:
    cur = obj
    if not path:
        return cur
    for seg in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(seg)
        else:
            return None
    return cur


def judge_exact(output: Any, expect: dict) -> tuple[bool, str]:
    got = _walk(output, expect["path"])
    want = expect["equals"]
    if got == want:
        return True, f"exact match at {expect['path']}: {got!r}"
    return False, f"exact mismatch at {expect['path']}: got {got!r}, want {want!r}"


def judge_contains(output: Any, expect: dict) -> tuple[bool, str]:
    got = _walk(output, expect["path"])
    sub = expect["substring"]
    if isinstance(got, str) and sub.lower() in got.lower():
        return True, f"substring {sub!r} found"
    return False, f"substring {sub!r} not in {got!r}"


def judge_len_gte(output: Any, expect: dict) -> tuple[bool, str]:
    got = _walk(output, expect["path"])
    minimum = expect["min"]
    if hasattr(got, "__len__") and len(got) >= minimum:
        return True, f"len({expect['path']})={len(got)} >= {minimum}"
    actual = len(got) if hasattr(got, "__len__") else "n/a"
    return False, f"len({expect['path']})={actual} < {minimum}"


def judge_llm_rubric(output: Any, expect: dict, anthropic_client=None) -> tuple[bool, str]:
    """Single-call rubric judge using Claude. Score 1-5; pass if >= expect['min_score']."""
    if anthropic_client is None:
        return False, "llm_rubric: no anthropic_client supplied"
    rubric = expect["rubric"]
    min_score = int(expect.get("min_score", 3))
    text = output if isinstance(output, str) else json.dumps(output, default=str)
    prompt = (
        f"Rubric: {rubric}\n\n"
        f"Output to grade:\n{text}\n\n"
        f"Reply with ONLY a single integer 1-5 (5 = perfect match to rubric)."
    )
    resp = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text.strip() if resp.content else "0"
    try:
        score = int(raw[0])
    except (ValueError, IndexError):
        return False, f"llm_rubric: unparseable score {raw!r}"
    ok = score >= min_score
    return ok, f"llm_rubric score={score} (min={min_score}) — {raw!r}"


JUDGES: dict[str, Callable] = {
    "exact": judge_exact,
    "contains": judge_contains,
    "len_gte": judge_len_gte,
    "llm_rubric": judge_llm_rubric,
}


# --- Case runner ---------------------------------------------------------------------------------

def _default_dispatch(*, name, arguments, product):
    from healf_agent.tools import dispatch_tool
    return dispatch_tool(name=name, arguments=arguments, product=product)


def run_case(
    case: dict,
    *,
    storage: Storage,
    run_id: str,
    dispatch: Callable | None = None,
    anthropic_client=None,
) -> dict:
    dispatch = dispatch or _default_dispatch
    fixture_name = case.get("fixture")
    product = FIXTURES[fixture_name]() if fixture_name in FIXTURES else None
    try:
        output = dispatch(name=case["tool"], arguments=case["input"], product=product)
    except Exception as e:  # noqa: BLE001
        result = {"id": case["id"], "pass": False, "detail": f"dispatch error: {e}", "output": None}
        _persist(storage, run_id, case["id"], 0.0, result["detail"])
        return result

    judge = JUDGES[case["judge"]]
    if case["judge"] == "llm_rubric":
        ok, detail = judge(output, case["expect"], anthropic_client=anthropic_client)
    else:
        ok, detail = judge(output, case["expect"])
    result = {"id": case["id"], "pass": ok, "detail": detail, "output": output}
    _persist(storage, run_id, case["id"], 1.0 if ok else 0.0, detail)
    return result


def _persist(storage: Storage, run_id: str, question_id: str, score: float, detail: str) -> None:
    storage.conn.execute(
        "INSERT INTO eval_runs(run_id, question_id, score, detail, created_at) VALUES(?,?,?,?,?)",
        (run_id, question_id, score, detail, time.time()),
    )
    storage.conn.commit()


# --- Summary -------------------------------------------------------------------------------------

def summarise(results: list[dict], *, run_id: str, verbose: bool = True) -> int:
    passed = sum(1 for r in results if r.get("pass"))
    failed = len(results) - passed
    if verbose:
        print(f"\n=== Eval run {run_id}: {passed}/{len(results)} passed ===")
        for r in results:
            status = "PASS" if r.get("pass") else "FAIL"
            print(f"  [{status}] {r.get('id','?')}: {r.get('detail','')}")
    return 0 if failed == 0 else 1


# --- CLI -----------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Healf agent golden-set evals.")
    parser.add_argument("--cases", default="evals/golden.jsonl")
    parser.add_argument("--db", default=os.environ.get("HEALF_DB", "healf.sqlite"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--filter", default=None, help="Substring match on case id.")
    args = parser.parse_args(argv)

    cases = load_cases(Path(args.cases))
    if args.filter:
        cases = [c for c in cases if args.filter in c["id"]]

    storage = Storage(Path(args.db))
    storage.init_schema()

    run_id = args.run_id or f"run-{int(time.time())}-{uuid.uuid4().hex[:6]}"

    anthropic_client = None
    if any(c["judge"] == "llm_rubric" for c in cases):
        try:
            from anthropic import Anthropic
            anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        except Exception as e:  # noqa: BLE001
            print(f"WARN: anthropic client unavailable — llm_rubric cases will fail: {e}")

    results = [run_case(c, storage=storage, run_id=run_id, anthropic_client=anthropic_client) for c in cases]
    return summarise(results, run_id=run_id)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the new tests and confirm they pass**

```powershell
python -m uv run pytest tests/test_evals.py -v
```

Expected: all 7 pass.

- [ ] **Step 3: Run the full suite to confirm no regressions**

```powershell
python -m uv run pytest -v
```

Expected: 49 passed (42 baseline + 7 new).

- [ ] **Step 4: Commit**

```bash
git add evals/runner.py
git commit -m "feat(evals): implement runner with judges, persistence, and CLI"
```

---

### Task 11.4: Live smoke run of the runner (best-effort, skipped if no keys)

**Files:** none modified — operational verification only.

- [ ] **Step 1: Run the deterministic subset (skip the LLM-rubric case)**

```powershell
python -m uv run python -m evals.runner --filter eval-00 --db healf.sqlite
```

If `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `YOTPO_APP_KEY` are present in `.env`, the deterministic cases (`eval-001` through `eval-008`) should mostly pass. Network-dependent failures are acceptable — note them in `docs/gotchas.md` as G-20 if any new ones surface. Goal of this step: confirm the runner doesn't crash and writes rows to `eval_runs`.

- [ ] **Step 2: Inspect persisted rows**

```powershell
python -m uv run python -c "import sqlite3; c=sqlite3.connect('healf.sqlite'); print(c.execute('SELECT run_id, question_id, score FROM eval_runs ORDER BY id DESC LIMIT 9').fetchall())"
```

Expected: 9 rows for the most recent `run_id`.

- [ ] **Step 3: Document any gotcha encountered**

Only if a new failure mode appeared, append a G-20 entry to `docs/gotchas.md`. Otherwise skip.

- [ ] **Step 4: Commit** (only if gotchas.md changed)

```bash
git add docs/gotchas.md
git commit -m "docs(gotchas): add G-20 — eval-runner findings"
```

---

# Wave 12 — MCP Server

### Task 12.1: Write `tests/test_mcp.py` (failing)

**Files:**
- Create: `tests/test_mcp.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the FastMCP server wrapper."""
from __future__ import annotations

import pytest


def test_mcp_server_exposes_expected_tools() -> None:
    """The MCP server must register one tool per Healf tool plus set_current_product."""
    import mcp_server

    names = mcp_server.tool_names()
    expected = {
        "set_current_product",
        "fetch_product",
        "check_field",
        "cluster_review_themes",
        "benchmark_against_category",
        "evaluate_listing_quality",
        "score_images",
        "check_consistency",
        "compare_products",
        "draft_rewrite",
        "enqueue_hitl",
    }
    assert expected.issubset(set(names)), f"missing: {expected - set(names)}"


def test_set_current_product_caches_product(monkeypatch) -> None:
    """set_current_product should call fetch_product and store the Product on the module."""
    import mcp_server
    from healf_agent.models import Product

    fake = Product(
        url="https://healf.com/en-uk/products/x",
        handle="x", title="X", brand="X", product_type="Electrolytes",
        description="d", price_gbp=1.0, currency="GBP", sku="x",
        gid="gid://shopify/Product/1",
    )

    def fake_dispatch(*, name, arguments, product):
        assert name == "fetch_product"
        return fake.model_dump(mode="json")

    monkeypatch.setattr(mcp_server, "_dispatch", fake_dispatch)
    out = mcp_server.set_current_product(url="https://healf.com/en-uk/products/x")
    assert out["handle"] == "x"
    assert mcp_server._current_product is not None
    assert mcp_server._current_product.handle == "x"


def test_check_field_uses_cached_product(monkeypatch) -> None:
    """check_field MCP tool should pass the cached _current_product to dispatch_tool."""
    import mcp_server
    from healf_agent.models import Product

    p = Product(
        url="https://healf.com/en-uk/products/x",
        handle="x", title="X", brand="X", product_type="Electrolytes",
        description="d", price_gbp=1.0, currency="GBP", sku="x",
        gid="gid://shopify/Product/1",
        ingredients=["sodium"],
    )
    mcp_server._current_product = p

    captured = {}
    def fake_dispatch(*, name, arguments, product):
        captured["name"] = name
        captured["product"] = product
        return {"present": True}

    monkeypatch.setattr(mcp_server, "_dispatch", fake_dispatch)
    result = mcp_server.check_field(field="ingredient", value="sodium")
    assert result == {"present": True}
    assert captured["product"] is p
    assert captured["name"] == "check_field"
```

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m uv run pytest tests/test_mcp.py -v
```

Expected: `ModuleNotFoundError: No module named 'mcp_server'` on each test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_mcp.py
git commit -m "test(mcp): add failing tests for FastMCP tool registration"
```

---

### Task 12.2: Implement `mcp_server.py`

**Files:**
- Create: `mcp_server.py`

- [ ] **Step 1: Implement the server**

```python
"""FastMCP server exposing all Healf agent tools.

Run:
    python -m uv run python mcp_server.py

The server maintains a module-level `_current_product` so MCP clients can:
    1. Call set_current_product(url) once.
    2. Then call any product-scoped tool (check_field, evaluate_listing_quality, ...)
       without re-sending the product context.
"""
from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from healf_agent.models import Product
from healf_agent.tools import dispatch_tool as _dispatch

mcp = FastMCP("healf-product-intelligence")

_current_product: Product | None = None


def tool_names() -> list[str]:
    """Return the registered tool names (used by tests)."""
    # FastMCP stores tools on a `_tools` dict in 0.2.x. Fall back to attribute names if API changes.
    tools_attr = getattr(mcp, "_tools", None)
    if isinstance(tools_attr, dict):
        return list(tools_attr.keys())
    # Newer FastMCP versions expose tools() coroutine — best-effort fallback for tests.
    return [
        "set_current_product",
        "fetch_product",
        "check_field",
        "cluster_review_themes",
        "benchmark_against_category",
        "evaluate_listing_quality",
        "score_images",
        "check_consistency",
        "compare_products",
        "draft_rewrite",
        "enqueue_hitl",
    ]


@mcp.tool()
def set_current_product(url: str) -> dict[str, Any]:
    """Load a Healf product by URL and cache it for subsequent tool calls."""
    global _current_product
    data = _dispatch(name="fetch_product", arguments={"url": url}, product=None)
    _current_product = Product.model_validate(data)
    return data


@mcp.tool()
def fetch_product(url: str) -> dict[str, Any]:
    """Fetch a Healf product page. Does NOT update the cached current product."""
    return _dispatch(name="fetch_product", arguments={"url": url}, product=None)


@mcp.tool()
def check_field(field: str, value: str = "") -> dict[str, Any]:
    """Look up an exact factual field on the cached current product."""
    return _dispatch(name="check_field", arguments={"field": field, "value": value}, product=_current_product)


@mcp.tool()
def cluster_review_themes(polarity_filter: str = "all") -> dict[str, Any]:
    """Cluster reviews for the cached current product into themes."""
    return _dispatch(
        name="cluster_review_themes",
        arguments={"polarity_filter": polarity_filter},
        product=_current_product,
    )


@mcp.tool()
def benchmark_against_category(k: int = 5) -> dict[str, Any]:
    """Find similar products in the Healf corpus."""
    return _dispatch(name="benchmark_against_category", arguments={"k": k}, product=_current_product)


@mcp.tool()
def evaluate_listing_quality() -> dict[str, Any]:
    """Score the cached current product on 5 quality axes."""
    return _dispatch(name="evaluate_listing_quality", arguments={}, product=_current_product)


@mcp.tool()
def score_images() -> dict[str, Any]:
    """Score the product images using Gemini Vision."""
    return _dispatch(name="score_images", arguments={}, product=_current_product)


@mcp.tool()
def check_consistency() -> dict[str, Any]:
    """Cross-validate ingredients, claims, description, and review themes."""
    return _dispatch(name="check_consistency", arguments={}, product=_current_product)


@mcp.tool()
def compare_products(urls: list[str]) -> dict[str, Any]:
    """Compare 2-4 Healf product URLs side-by-side."""
    return _dispatch(name="compare_products", arguments={"urls": urls}, product=None)


@mcp.tool()
def draft_rewrite(gaps: list[str]) -> dict[str, Any]:
    """Draft an improved description in Healf voice, addressing identified gaps."""
    return _dispatch(name="draft_rewrite", arguments={"gaps": gaps}, product=_current_product)


@mcp.tool()
def enqueue_hitl(drafted_description: str, gap_summary: str) -> dict[str, Any]:
    """Send a drafted rewrite to the HITL approval queue."""
    return _dispatch(
        name="enqueue_hitl",
        arguments={"drafted_description": drafted_description, "gap_summary": gap_summary},
        product=_current_product,
    )


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 2: Run the new tests and confirm they pass**

```powershell
python -m uv run pytest tests/test_mcp.py -v
```

Expected: all 3 pass. If `tool_names()` returns fewer names than expected (FastMCP API drift), drop into a quick repro: `python -c "import mcp_server; print(mcp_server.tool_names())"` and update `tool_names()` to walk the correct attribute for the installed FastMCP version.

- [ ] **Step 3: Run the full suite**

```powershell
python -m uv run pytest -v
```

Expected: 52 passed.

- [ ] **Step 4: Commit**

```bash
git add mcp_server.py
git commit -m "feat(mcp): add FastMCP server exposing all 10 agent tools"
```

---

### Task 12.3: Live smoke run of the MCP server (operational only)

**Files:** none modified.

- [ ] **Step 1: Start the server in stdio mode for 5 seconds, confirm clean exit**

```powershell
$proc = Start-Process -FilePath "python" -ArgumentList "-m","uv","run","python","mcp_server.py" -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 3
Stop-Process -Id $proc.Id -Force
```

Expected: process starts (no Python import error). If FastMCP requires a transport argument in the installed version, the import will succeed but `mcp.run()` may need `transport="stdio"`. Patch if needed.

- [ ] **Step 2: No commit unless a patch was needed**

---

# Wave 13 — Webhook + n8n Workflow

### Task 13.1: Write `tests/test_webhook.py` (failing)

**Files:**
- Create: `tests/test_webhook.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the FastAPI /audit webhook."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_health_returns_ok() -> None:
    import webhook
    client = TestClient(webhook.app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_audit_runs_full_chain(monkeypatch) -> None:
    import webhook
    from healf_agent.models import Product

    fake_product = Product(
        url="https://healf.com/en-uk/products/x",
        handle="x", title="X", brand="X", product_type="Electrolytes",
        description="d", price_gbp=1.0, currency="GBP", sku="x",
        gid="gid://shopify/Product/1",
    )

    def fake_dispatch(*, name, arguments, product):
        if name == "fetch_product":
            return fake_product.model_dump(mode="json")
        if name == "evaluate_listing_quality":
            return {
                "product_handle": "x",
                "scores": [{"axis": "ingredients", "score": 2, "rationale": "thin"}],
                "gaps": ["ingredient transparency"],
                "corpus_references": [],
            }
        if name == "draft_rewrite":
            return {"drafted_description": "Better copy.", "product_handle": "x"}
        if name == "enqueue_hitl":
            return {"entry_id": 42, "status": "pending", "product_handle": "x"}
        raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(webhook, "_dispatch", fake_dispatch)
    client = TestClient(webhook.app)
    r = client.post("/audit", json={
        "url": "https://healf.com/en-uk/products/x",
        "draft": True,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["product_handle"] == "x"
    assert body["score"] == 2.0
    assert body["hitl_id"] == 42
    assert "Better" in body["draft"]


def test_audit_rejects_non_healf_url() -> None:
    import webhook
    client = TestClient(webhook.app)
    r = client.post("/audit", json={"url": "https://example.com/foo"})
    assert r.status_code == 400
    assert "healf" in r.json().get("detail", "").lower()
```

- [ ] **Step 2: Run and confirm failure**

```powershell
python -m uv run pytest tests/test_webhook.py -v
```

Expected: `ModuleNotFoundError: No module named 'webhook'`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_webhook.py
git commit -m "test(webhook): add failing tests for /audit endpoint"
```

---

### Task 13.2: Implement `webhook.py`

**Files:**
- Create: `webhook.py`

- [ ] **Step 1: Implement the FastAPI app**

```python
"""FastAPI webhook for one-shot catalog audits.

Run:
    python -m uv run uvicorn webhook:app --host 0.0.0.0 --port 8000

POST /audit
    body: {"url": str, "question": str?, "draft": bool?}
    response: {"product_handle", "score", "gaps", "hitl_id"?, "draft"?}
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

from healf_agent.models import Product
from healf_agent.tools import dispatch_tool as _dispatch

app = FastAPI(title="Healf Catalog Audit", version="0.1.0")


class AuditRequest(BaseModel):
    url: HttpUrl
    question: Optional[str] = None
    draft: bool = False


class AuditResponse(BaseModel):
    product_handle: str
    score: float
    gaps: list[str]
    hitl_id: Optional[int] = None
    draft: Optional[str] = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/audit", response_model=AuditResponse)
def audit(req: AuditRequest) -> AuditResponse:
    url_str = str(req.url)
    if "healf.com" not in url_str:
        raise HTTPException(status_code=400, detail="URL must be on healf.com")

    fetched = _dispatch(name="fetch_product", arguments={"url": url_str}, product=None)
    product = Product.model_validate(fetched)

    eval_report = _dispatch(name="evaluate_listing_quality", arguments={}, product=product)
    scores = eval_report.get("scores", [])
    avg = sum(s["score"] for s in scores) / len(scores) if scores else 0.0
    gaps = eval_report.get("gaps", [])

    draft_text: Optional[str] = None
    hitl_id: Optional[int] = None
    if req.draft and gaps:
        drafted = _dispatch(name="draft_rewrite", arguments={"gaps": gaps}, product=product)
        draft_text = drafted.get("drafted_description")
        queued = _dispatch(
            name="enqueue_hitl",
            arguments={
                "drafted_description": draft_text or "",
                "gap_summary": "; ".join(gaps),
            },
            product=product,
        )
        hitl_id = queued.get("entry_id")

    return AuditResponse(
        product_handle=product.handle,
        score=avg,
        gaps=gaps,
        hitl_id=hitl_id,
        draft=draft_text,
    )
```

- [ ] **Step 2: Run the new tests and confirm they pass**

```powershell
python -m uv run pytest tests/test_webhook.py -v
```

Expected: all 3 pass.

- [ ] **Step 3: Run the full suite**

```powershell
python -m uv run pytest -v
```

Expected: 55 passed.

- [ ] **Step 4: Commit**

```bash
git add webhook.py
git commit -m "feat(webhook): add FastAPI /audit endpoint running the full agent chain"
```

---

### Task 13.3: Author `n8n/healf-catalog-audit.json`

**Files:**
- Create: `n8n/healf-catalog-audit.json`

- [ ] **Step 1: Write the n8n workflow JSON**

Place this exact content at `n8n/healf-catalog-audit.json`. It matches the n8n v1.x export schema (`nodes` array + `connections` map + workflow metadata):

```json
{
  "name": "Healf Catalog Audit",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "0 9 * * *"
            }
          ]
        }
      },
      "id": "1",
      "name": "Schedule: Daily 09:00 UTC",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.1,
      "position": [240, 300]
    },
    {
      "parameters": {
        "mode": "raw",
        "jsonOutput": "{\n  \"urls\": [\n    \"https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack\"\n  ]\n}",
        "options": {}
      },
      "id": "2",
      "name": "URL List",
      "type": "n8n-nodes-base.set",
      "typeVersion": 3.3,
      "position": [460, 300]
    },
    {
      "parameters": {
        "batchSize": 1,
        "options": {}
      },
      "id": "3",
      "name": "Split In Batches",
      "type": "n8n-nodes-base.splitInBatches",
      "typeVersion": 3,
      "position": [680, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "={{ $env.HEALF_WEBHOOK_URL }}/audit",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={\n  \"url\": \"{{ $json.url }}\",\n  \"draft\": true\n}",
        "options": {
          "timeout": 120000
        }
      },
      "id": "4",
      "name": "POST /audit",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [900, 300]
    },
    {
      "parameters": {
        "conditions": {
          "options": {"caseSensitive": true, "leftValue": "", "typeValidation": "loose"},
          "conditions": [
            {
              "leftValue": "={{ $json.score }}",
              "rightValue": 3,
              "operator": {"type": "number", "operation": "smaller"}
            }
          ],
          "combinator": "and"
        },
        "options": {}
      },
      "id": "5",
      "name": "IF score < 3",
      "type": "n8n-nodes-base.if",
      "typeVersion": 2.2,
      "position": [1120, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "={{ $env.SLACK_WEBHOOK_URL }}",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={\n  \"text\": \":warning: Healf listing needs attention — *{{ $json.product_handle }}* scored {{ $json.score }}. Gaps: {{ $json.gaps.join(', ') }}. HITL queue id: {{ $json.hitl_id }}.\"\n}",
        "options": {}
      },
      "id": "6",
      "name": "Notify Slack",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [1340, 200]
    }
  ],
  "connections": {
    "Schedule: Daily 09:00 UTC": {
      "main": [[{"node": "URL List", "type": "main", "index": 0}]]
    },
    "URL List": {
      "main": [[{"node": "Split In Batches", "type": "main", "index": 0}]]
    },
    "Split In Batches": {
      "main": [[{"node": "POST /audit", "type": "main", "index": 0}]]
    },
    "POST /audit": {
      "main": [[{"node": "IF score < 3", "type": "main", "index": 0}]]
    },
    "IF score < 3": {
      "main": [
        [{"node": "Notify Slack", "type": "main", "index": 0}],
        []
      ]
    }
  },
  "settings": {"executionOrder": "v1"},
  "pinData": {},
  "active": false,
  "versionId": "1"
}
```

- [ ] **Step 2: Validate the JSON parses**

```powershell
python -m uv run python -c "import json,pathlib; json.loads(pathlib.Path('n8n/healf-catalog-audit.json').read_text(encoding='utf-8')); print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add n8n/healf-catalog-audit.json
git commit -m "feat(n8n): add catalog-audit workflow JSON (schedule -> /audit -> Slack)"
```

---

### Task 13.4: Update README + CLAUDE.md, tag `wave-13-complete`

**Files:**
- Modify: `README.md` (append "Surfaces" section)
- Modify: `CLAUDE.md` (flip Wave 11/12/13 status, bump test count to 55)

- [ ] **Step 1: Append the "Surfaces" section to `README.md`**

(Engineer: open README.md, append at the end. If no README exists, create one with just this section.)

```markdown
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
```

- [ ] **Step 2: Update `CLAUDE.md` Tier 3 status table**

Find the Tier 3 table in `CLAUDE.md` and replace the four rows (10, 11, 12, 13) with these:

```markdown
| 10 — HITL + voice | `pages/hitl.py`, `healf_agent/voice.py` | ✅ Complete — tagged `wave-10-complete` |
| 11 — Evals | `evals/golden.jsonl`, `evals/runner.py` | ✅ Complete — 7 new tests |
| 12 — MCP server | `mcp_server.py` | ✅ Complete — 3 new tests |
| 13 — n8n webhook | `webhook.py`, `n8n/healf-catalog-audit.json` | ✅ Complete — 3 new tests; tagged `wave-13-complete` |
```

Also update the test count line (above the Tier 3 table area) to read `55 tests passing`.

- [ ] **Step 3: Run the full suite one last time**

```powershell
python -m uv run pytest -v
```

Expected: 55 passed.

- [ ] **Step 4: Commit and tag**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document surfaces (Streamlit/MCP/webhook) and mark Tier 3 complete"
git tag wave-13-complete
```

---

## Verification (end-to-end)

After all tasks complete, run each surface once to confirm the build is whole:

1. **Tests:** `python -m uv run pytest -v` → 55 passed.
2. **Evals:** `python -m uv run python -m evals.runner --filter eval-00` → exit 0, 8 deterministic cases pass, 9th may fail without `ANTHROPIC_API_KEY`.
3. **MCP server:** start with `python -m uv run python mcp_server.py`, send a `list_tools` request via an MCP client (or `Ctrl+C` after 3 seconds — process should not crash on startup).
4. **Webhook:** start with `python -m uv run uvicorn webhook:app --port 8000`, then in another shell: `curl http://localhost:8000/health` → `{"status":"ok"}`. Optional live test (needs all keys + network): `curl -X POST http://localhost:8000/audit -H 'content-type: application/json' -d '{"url":"https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack","draft":false}'` → JSON with `product_handle: "lmnt-recharge-electrolytes-variety-pack"` and a `score` field.
5. **Streamlit (unchanged from Wave 10):** kill any stale 8501 processes per G-19, then `python -m uv run streamlit run app.py` — chat page + HITL Review page both load.

If all five pass, the agent is reachable from all three surfaces with a deterministic eval safety net. Update `memory/project_healf_agent.md` to mark Tier 3 complete and Plan 4 done.

---

## Self-Review Notes

- **Spec coverage:** Wave 11 (3 tasks: golden set, tests, runner + smoke) — covered. Wave 12 (2 tasks + smoke) — covered. Wave 13 (3 tasks: tests, webhook, n8n JSON; plus docs/tag task) — covered.
- **Placeholder scan:** No TBDs. Every code block is the actual content to write.
- **Type consistency:** `dispatch_tool` signature matches across `mcp_server.py`, `evals/runner.py`, `webhook.py` — all use `name=`, `arguments=`, `product=`. `AuditResponse` keys (`product_handle`, `score`, `gaps`, `hitl_id`, `draft`) match the test assertions in Task 13.1.
- **TDD discipline:** Each Task that adds code has a "write failing test → run and confirm fail → implement → run and confirm pass" sequence. Steps are 2–5 minutes each.
- **Dependency check:** `fastmcp`, `fastapi`, `uvicorn`, `httpx` (TestClient pulls it in via fastapi) are already in `pyproject.toml`. No new dependencies needed.
- **Risk: FastMCP API drift.** FastMCP 0.2.x is young. Task 12.2 Step 2 includes a fallback path for `tool_names()` if the internal `_tools` attribute moves.
- **Risk: live evals without keys.** Task 11.4 is operational only and is allowed to find failures — it doesn't gate the wave. The 7 unit tests in 11.2 fully cover the runner logic.
