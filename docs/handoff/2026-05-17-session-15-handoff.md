# Session 15 Handoff — 2026-05-17

## What Was Done This Session

### G-44: Full-catalog corpus build — fix silent 78% product drop

**User report:** Thorne Vitamin B12 exists on Healf, is in their sitemap, parses cleanly — but was missing from `corpus.sqlite` and never appeared in any build log line.

**Root cause:** `stratified_sample(target=1500)` with 86 buckets kept only ~22% of each large bucket. "Vitamins & Supplements" (142 URLs) got ~33 slots; Thorne B12 was not drawn. Sampling drops are completely silent — no per-URL log.

**Three fixes in `scripts/build_corpus.py`:**
1. Default `--target` raised to 10000. When `target >= total_classified`, skip `stratified_sample` and embed the full catalog (~6078 URLs).
2. `DELETE FROM corpus` runs at script start — enforces G-40 automatically.
3. `corpus_skipped.jsonl` written after every build (phase + reason per dropped URL).

**Also fixed:** `embed_texts` in `healf_agent/corpus.py` — crashed with OpenAI 400 when sending 6076 texts in one batch (limit is 2048). Now chunks at `batch_size=2000`.

**Commits:** `e983c94` (build script), `4abf252` (embed batch fix), `bd9dcbd` (corpus.sqlite rebuild)

**Final corpus:** 6077 rows, 48.2 MB, B12 collection = 32 products (was 11).

---

### G-45: Filter generic collections before knn — fix BioCare-only peers

**User report:** E2E smoke test still showed 3 BioCare products as peers; Thorne B12 absent.

**Root cause:** BioCare Vitamin B12 has 29 collections — most are site-wide tags (`all-products-1`: 6077, `best-sellers`: 6077, `blc`: 6071, `replenishables-running-low`: 3422). The `knn()` ANY-overlap logic matched ~100% of corpus. Cosine similarity then dominated, returning the most text-similar products — other BioCare items.

**Fix in `healf_agent/tools/find_similar.py`:**
- New `_specific_collections(collections, storage)` helper: queries corpus for collection frequency, keeps only those with ≤200 members.
- For BioCare B12: keeps `vitamin-b12` (32), `b-vitamins` (77), `biocare` (118). Drops all generic tags.
- Fallback: if all collections exceed threshold, keep the 3 smallest.

**Commit:** `8c21542` — 101 tests passing (+1 new `test_find_similar_ignores_generic_collections`)

---

## State for Next Session

**E2E smoke test still needs verification** — session ended before re-running after G-45 fix.

1. Kill stale Streamlit (G-19):
```powershell
Get-Process -Name python | Where-Object { $_.CommandLine -like '*streamlit*' } | Stop-Process
```

2. Start Streamlit:
```powershell
cd "C:\Users\Daran\AI\Healf AI Agent\.claude\worktrees\feat-healf-agent"
python -m uv run streamlit run app.py
```

3. Smoke test:
   - Paste `https://healf.com/en-uk/products/biocare-vitamin-b12` → Fetch
   - Ask: "How does this compare to similar products?"
   - **Expect:** Thorne Vitamin B12 and/or Vimergy Organic Liquid B12 in the table (NOT just other BioCare products)

4. Regression: LMNT Recharge Variety Pack benchmark → still returns ≥3 corpus neighbours.

5. If smoke test passes: commit/push branch, update memory.

## Current Branch State

- **Branch:** `worktree-feat-healf-agent`
- **Latest commit:** `8c21542`
- **Tests:** 101 passing
- **corpus.sqlite:** 6077 rows, 48.2 MB, committed

## Commands to Resume

```bash
cd "C:\Users\Daran\AI\Healf AI Agent\.claude\worktrees\feat-healf-agent"
python -m uv run pytest -v  # 101 passing
```
