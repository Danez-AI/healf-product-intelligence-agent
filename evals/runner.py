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
import re
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
    text_block = next((b for b in resp.content if getattr(b, "type", None) == "text"), None)
    raw = text_block.text.strip() if text_block else "0"
    m = re.search(r"[1-5]", raw)
    if not m:
        return False, f"llm_rubric: unparseable score {raw!r}"
    score = int(m.group())
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
        judge = JUDGES[case["judge"]]
        if case["judge"] == "llm_rubric":
            ok, detail = judge(output, case["expect"], anthropic_client=anthropic_client)
        else:
            ok, detail = judge(output, case["expect"])
        result = {"id": case["id"], "pass": ok, "detail": detail, "output": output}
        _persist(storage, run_id, case["id"], 1.0 if ok else 0.0, detail)
        return result
    except Exception as e:  # noqa: BLE001
        result = {"id": case["id"], "pass": False, "detail": f"dispatch error: {e}", "output": None}
        try:
            _persist(storage, run_id, case["id"], 0.0, result["detail"])
        except Exception:
            pass
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
