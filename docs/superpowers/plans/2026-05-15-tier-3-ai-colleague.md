# Plan 3 — Tier 3, Wave 10: HITL Review Page + Healf Voice Module

> **Final destination after approval:** copy this plan to
> `docs/superpowers/plans/2026-05-15-tier-3-ai-colleague.md` and tag the
> commit with the `wave-10-start` reference. This file (the dynamic plan)
> is the working draft.

---

## Context

Tier 2 delivered the analytical depth (clustering, benchmarking, vision,
compare, draft, enqueue). The agent now produces evidence-based listing
audits — **smoke-tested on LMNT 2026-05-15 22:24**, with the trace showing
high-quality recommendations (Ingredients Critical, Claims High, etc.).

The next gap in the "AI as functional colleague" story is the human review
loop. Today `enqueue_hitl` writes drafts into `hitl_queue`, but **nothing
reads from that queue** — there's no UI, no approve/reject path, no
audit trail. Tier 3 Wave 10 closes that loop with two pieces:

1. **`pages/hitl.py`** — a Streamlit multipage sibling to `app.py` that
   lists pending drafts, lets a reviewer inline-edit the copy, and
   approves / rejects / saves-edited with a reviewer note.
2. **`healf_agent/voice.py`** — extracts the inline Healf-voice prompt
   currently buried at `healf_agent/tools/act.py:9–20` into a dedicated,
   testable module. `draft_rewrite` becomes a thin wrapper.

Outcome: a reviewer can open the HITL page, see "LMNT — gap_summary
mentions ingredients/claims missing", read the AI draft, refine it
in-place, click **Save as edited**, and the row flips status with an
audit trail. That single workflow is the demo for the "AI colleague"
pitch.

---

## Decisions (from clarifying questions)

- **Audit fields:** Add `reviewer_note TEXT` and `reviewed_at REAL` to
  `hitl_queue`. Migration runs in `Storage.init_schema()` via
  `ALTER TABLE … ADD COLUMN IF NOT EXISTS …` (SQLite needs a try/except
  on duplicate-column).
- **Edit flow:** Yes — use the existing `"edited"` status from
  `HITLEntry.status` (`healf_agent/models.py:115`). UI offers three
  actions: **Approve**, **Reject**, **Save as edited**.
- **Smoke-test prompt fix:** Deferred to Wave 14 polish.

---

## Wave 10 Task Breakdown

| Task | Deliverable | File(s) |
|------|-------------|---------|
| 10.1 | HITL CRUD + schema migration | `healf_agent/storage.py`, `healf_agent/models.py` |
| 10.2 | `voice.py` module + `draft_rewrite` refactor | `healf_agent/voice.py`, `healf_agent/tools/act.py` |
| 10.3 | Streamlit HITL page | `pages/hitl.py` |
| 10.4 | Tests | `tests/test_voice.py`, `tests/test_storage.py`, `tests/test_agent.py` |
| 10.5 | Manual smoke test + commit + tag | — |

Total target: **40+ tests passing** (35 → ~42).

---

## Task 10.1 — HITL CRUD + schema migration

**File:** `healf_agent/storage.py`

**Schema migration** in `init_schema()`:

```python
# After existing hitl_queue CREATE TABLE
for col, decl in [("reviewer_note", "TEXT"), ("reviewed_at", "REAL")]:
    try:
        self.conn.execute(f"ALTER TABLE hitl_queue ADD COLUMN {col} {decl}")
    except sqlite3.OperationalError:
        pass  # column already exists — idempotent
```

**Add three methods** to `Storage`:

- `list_hitl(self, status: str | None = None) -> list[HITLEntry]`
  Returns newest-first. If `status` is None, returns all.
- `get_hitl(self, hitl_id: int) -> HITLEntry | None`
- `update_hitl(self, hitl_id: int, *, status: str, drafted_description: str | None = None, reviewer_note: str | None = None) -> None`
  Sets `reviewed_at = time.time()` server-side. `drafted_description` is
  only updated for the `"edited"` flow.

**Model change:** add `reviewer_note: str | None = None` and
`reviewed_at: datetime | None = None` to `HITLEntry`
(`healf_agent/models.py:109–116`). Existing rows load with None — safe.

**Reusable pattern:** mirror the row→model mapping in
`Storage.upsert_product` / `get_product` (existing pattern).

---

## Task 10.2 — `healf_agent/voice.py` + `draft_rewrite` refactor

**Create `healf_agent/voice.py`:**

```python
"""Healf-voice prompt scaffolding. API-call-free — pure templates."""
from __future__ import annotations
from healf_agent.models import Product

HEALF_VOICE = (
    "Healf voice: confident, evidence-led, warm but not preachy. "
    "British English. No hype. Concrete benefits over adjectives. "
    "Premium but approachable."
)

REWRITE_SYSTEM = (
    "You are a senior copywriter for Healf, a UK premium health & "
    "wellness marketplace. " + HEALF_VOICE
)

def build_rewrite_prompt(product: Product, gap_summary: str) -> str:
    """Return the user-message prompt for draft_rewrite. No API call."""
    return (
        f"Rewrite the product description for '{product.title}' by "
        f"{product.brand}.\n\n"
        f"Current description: {product.description}\n\n"
        f"Identified gaps to address:\n{gap_summary}\n\n"
        "Requirements: 150–250 words. Address each gap concretely. "
        "Do not invent ingredients or claims not in the source. "
        "Return only the rewritten description body."
    )
```

**Refactor `healf_agent/tools/act.py`:**

- Delete the inline `_REWRITE_PROMPT` (lines 9–20).
- Import `REWRITE_SYSTEM` and `build_rewrite_prompt` from `voice`.
- `draft_rewrite` calls `client.messages.create(system=REWRITE_SYSTEM, …)`
  with `messages=[{"role":"user","content": build_rewrite_prompt(...)}]`.
- Keep signature, return type, and dispatcher integration unchanged.

---

## Task 10.3 — `pages/hitl.py`

**Create `pages/hitl.py`** (Streamlit auto-discovers it as a sidebar nav
entry next to "app").

Layout:

```
┌─ HITL Review Queue (sidebar status filter: pending | all)
│  [pending count badge]
│
├─ Selectbox: pending entries by id + product_handle + truncated gap
│
├─ Two-column view:
│    LEFT:  Original description (read-only, st.code)
│    RIGHT: Drafted description (st.text_area — editable)
│
├─ Gap summary expander
│
├─ Reviewer note: st.text_input
│
└─ Action row:
     [✅ Approve]   [✏️ Save as edited]   [❌ Reject]
```

Behaviour:
- **Approve** → `update_hitl(id, status="approved", reviewer_note=note)`
- **Save as edited** → `update_hitl(id, status="edited",
  drafted_description=textarea_value, reviewer_note=note)`
- **Reject** → `update_hitl(id, status="rejected", reviewer_note=note)`
- After action: `st.success(...)`, `st.rerun()` to refresh the queue.
- Empty queue: show "No pending drafts. Run an audit in the chat first."

**Reuse:** `Storage(Path("healf.sqlite"))` + `init_schema()` boilerplate
from `app.py:22–23`.

---

## Task 10.4 — Tests

**`tests/test_voice.py`** (new — API-free):
- `test_healf_voice_contains_british_english_signal` — assertion on the
  HEALF_VOICE constant.
- `test_build_rewrite_prompt_includes_product_title_and_gaps`
- `test_build_rewrite_prompt_includes_word_count_target`
- `test_rewrite_system_starts_with_role`

**`tests/test_storage.py`** (extend):
- `test_list_hitl_returns_newest_first`
- `test_update_hitl_sets_reviewed_at`
- `test_update_hitl_edit_overwrites_drafted_description`

**`tests/test_agent.py`** (extend):
- Update `test_draft_rewrite_returns_string` to confirm the system arg
  passed to the mocked Anthropic client contains "Healf".

UI page is **not** unit-tested — manual smoke test covers it. Pattern
matches the rest of the suite (Storage/tools tested, Streamlit not).

---

## Task 10.5 — Manual smoke test + commit + tag

Run from worktree (`C:\Users\Daran\AI\Healf AI Agent\.claude\worktrees\feat-healf-agent`):

```bash
python -m uv run pytest -v               # 35 → ~42 passing
python -m uv run streamlit run app.py    # already runs on 8501
```

Manual flow:
1. In **chat page** — fetch LMNT, ask "draft a rewrite of the description
   addressing the missing ingredients and claims". This should trigger
   `draft_rewrite` + `enqueue_hitl`.
2. Click **HITL Review** in sidebar nav.
3. Verify the LMNT draft appears.
4. Tweak the textarea, add a reviewer note, click **Save as edited**.
5. Reload — confirm status is now `edited` and `reviewer_note` is stored.

**Commit pattern (atomic per task):**
- `feat(storage): HITL CRUD + reviewer audit columns (Wave 10.1)`
- `feat(voice): healf_agent/voice.py — extracted Healf-voice prompts (Wave 10.2)`
- `refactor(act): draft_rewrite uses voice.build_rewrite_prompt (Wave 10.2)`
- `feat(pages): hitl.py — Streamlit review queue UI (Wave 10.3)`
- `test: voice + HITL CRUD tests (Wave 10.4)`

Final tag once Wave 10 passes: `wave-10-complete`.

---

## Critical Files (modified or created)

| Path | Change |
|------|--------|
| `healf_agent/storage.py` | +3 methods, schema migration in `init_schema()` |
| `healf_agent/models.py` | `HITLEntry` gains `reviewer_note`, `reviewed_at` |
| `healf_agent/voice.py` | **NEW** — HEALF_VOICE, REWRITE_SYSTEM, build_rewrite_prompt |
| `healf_agent/tools/act.py` | Delete inline prompt; import from voice |
| `pages/hitl.py` | **NEW** — Streamlit HITL review UI |
| `tests/test_voice.py` | **NEW** — 4 prompt-template tests |
| `tests/test_storage.py` | +3 tests |
| `tests/test_agent.py` | Update draft_rewrite test to assert "Healf" in system |
| `docs/gotchas.md` | Add G-17 if anything surprises (e.g., Streamlit pages caveat) |
| `CLAUDE.md` | Update Wave 10 row to ✅ once done |

---

## Verification (end-to-end)

A reviewer must be able to:

1. **Generate a draft** via chat (Tier 2 path, already working).
2. **Open HITL page** from the auto-generated sidebar nav.
3. **See pending drafts** with product handle + gap summary.
4. **Inline-edit** the drafted description.
5. **Save** with status flipped to `edited`, `reviewer_note` persisted,
   `reviewed_at` populated.
6. **Re-open the page** — the edited row is no longer in "pending" view.

Plus all unit tests passing (`pytest -v` shows ~42 tests green).

---

## Out of Scope (deferred)

- SYSTEM_PROMPT tightening for benchmark→evaluate→draft chain → **Wave 14 polish**.
- Multi-section rewrites (title, bullets, claims, alt text) → not in
  Wave 10; current `draft_rewrite` outputs description-only.
- Reviewer authentication / multi-user — single-reviewer assumption holds
  for assignment submission.
- Diff highlighting (red/green) in the review UI — nice-to-have; not
  blocking.

---

## Execution Mode

Use `superpowers:subagent-driven-development`: one subagent per task
(10.1–10.4), each completing with tests green and an atomic commit
before the next is dispatched. Task 10.3 (Streamlit page) followed by
Task 10.5 (manual smoke test) — UI verification is human-driven.
