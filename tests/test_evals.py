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


def test_run_case_records_dispatch_error(tmp_path) -> None:
    from evals.runner import run_case
    from healf_agent.storage import Storage

    storage = Storage(tmp_path / "evals.sqlite")
    storage.init_schema()

    def boom(*, name, arguments, product):
        raise RuntimeError("tool unavailable")

    case = {
        "id": "err-001",
        "tool": "x",
        "fixture": None,
        "input": {},
        "judge": "exact",
        "expect": {"path": "", "equals": None},
    }
    result = run_case(case, storage=storage, run_id="r-err", dispatch=boom)
    assert result["pass"] is False
    assert "dispatch error" in result["detail"]
