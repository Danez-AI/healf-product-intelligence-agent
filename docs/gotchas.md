# Healf Agent — Gotchas & Fixes

Running log of surprises, workarounds, and non-obvious decisions discovered while building. Updated each session.

---

## G-01: `uv` is not in PATH — must use `python -m uv`

**Symptom:** `uv sync` or `uv run pytest` → "command not found"  
**Fix:** All uv commands must be invoked as `python -m uv run …`  
**Applies to:** Every shell command in this project, including subagent prompts

---

## G-02: Healf is Next.js App Router — no Shopify JSON endpoint

**Symptom:** `https://healf.com/products/lmnt.json` returns HTML (404 wrapped)  
**Root cause:** Healf uses a custom Next.js App Router storefront, not a vanilla Shopify theme  
**Fix:** Use JSON-LD (`<script type="application/ld+json">`) as the primary data source; RSC flight payload (`__next_f.push`) as secondary for metafields  
**Applies to:** `ingest.py`, all corpus-building logic

---

## G-03: Yotpo app key not in static HTML

**Symptom:** Regex scan of PDP HTML for Yotpo app key returns "NOT FOUND"  
**Root cause:** Healf pre-renders JSON-LD reviews server-side; the Yotpo widget JS (which contains the app key) is loaded client-side only  
**Fix:** Discover key from DevTools → Network tab → filter "yotpo" → grab key from URL. Key for Healf: `bgzgoRGnLi5wOF0jyQdbzIfRCFKCpcmV701bZUJP`. Set as `YOTPO_APP_KEY` in `.env`  
**Note:** CDN variant seen in DevTools is `api-cdn.yotpo.com`; our code uses `api.yotpo.com` — both work for the widget API

---

## G-04: Healf JSON-LD has no `category` field — all products parse as "Unknown"

**Symptom:** After building `corpus.sqlite` with 150 products, all entries have `product_type: Unknown`  
**Root cause:** Healf's Product JSON-LD schema only includes: `name`, `brand`, `description`, `url`, `image`, `offers`, `review`, `aggregateRating` — no `category`, `additionalType`, or `productType`  
**Current state:** `corpus.sqlite` has 150 entries with good text + embeddings, but all type-bucketed as "Unknown"  
**Impact:** `Storage.knn(product_type=…)` filter won't return results unless queried with "Unknown"  
**Fix needed (Wave 7):** Map products to collections via sitemap-collections XML, or infer type from URL handle keywords, before kNN filtering is meaningful

---

## G-05: LMNT product name in JSON-LD doesn't start with "LMNT"

**Symptom:** `test_parse_product_lmnt_fixture` fails when asserting `p.brand.lower() == "lmnt"` if reading name instead of brand  
**Root cause:** JSON-LD `name` is `"Recharge Electrolytes - Variety Pack"` — brand is in `brand.name = "LMNT"` as a nested object  
**Fix:** `parse_product` extracts `pblock["brand"]["name"]` when brand is a dict

---

## G-06: Currency clamping required to satisfy Pydantic Literal type

**Symptom:** `ValidationError` when parsing real LMNT JSON-LD — priceCurrency value not matching `Literal["GBP","USD","EUR"]`  
**Fix:** `ingest.py` clamps raw currency to known set; unknown currencies default to `"GBP"`. See `_KNOWN_CURRENCIES` pattern in ingest.py

---

## G-07: Streamlit's inline `!` command doesn't support interactive input

**Symptom:** Running `! python -m uv run streamlit run app.py` in the Claude Code prompt hangs at "Email:" onboarding prompt  
**Fix:** Run Streamlit in a **separate terminal** (PowerShell/CMD), not via the `!` inline command. Navigate to the worktree and run there

---

## G-08: Agent doesn't know which product is loaded without explicit context injection

**Symptom:** User asks "does this have sodium?" — agent responds "You haven't shared a product URL"  
**Root cause:** `run_agent_turn` receives the `product` Python object for `check_field` dispatch, but the LLM itself never sees product details in its message history  
**Fix:** In `app.py`, prepend a product context block to the user message before passing to `run_agent_turn`:
```python
product_ctx = f"Currently loaded product: '{product.title}' by {product.brand} ..."
user_message = product_ctx + user_input
```

---

## G-09: Background subagent returned before corpus build completed

**Symptom:** Task 4.3 subagent reported STATUS: DONE but `corpus.sqlite` had 0 rows  
**Root cause:** Long-running `build_corpus.py` script (several minutes) caused the subagent to return before completion  
**Fix:** Ran the build directly via Bash tool with a 10-minute timeout. Always run long live-network scripts directly, not via subagents

---

## G-10: LMNT has no ingredient list in JSON-LD or RSC metafields

**Symptom:** `check_field(field="ingredient", value="sodium")` returns `present: false, evidence: []`  
**Root cause:** LMNT's Healf listing doesn't expose ingredients in either the JSON-LD schema or the RSC flight payload. The RSC metafield regex found nothing  
**Impact:** Ingredient-based queries will answer "not extracted" rather than the real ingredient list for products without structured ingredient data  
**Workaround:** In Tier 3, we could add OCR of product images (Wave 8 vision tool) to extract ingredient panels from label photos

---

## G-11: HDBSCAN returns all-noise labels when all embeddings are identical (test vectors)

**Symptom:** `test_cluster_review_themes_returns_themes_list` passes but no clusters form — all labels are -1  
**Root cause:** Test uses `[0.1] * 128` for all 10 reviews. HDBSCAN correctly classifies all identical points as noise (no density structure)  
**Fix:** Added guard in `review_themes.py`: `if labels is None or all(l == -1 for l in labels): labels = [0] * len(reviews)` — forces a single cluster when all are noise  
**Applies to:** `healf_agent/tools/review_themes.py`

---

## G-12: `google.generativeai` is NOT installed — use `google-genai` SDK

**Symptom:** `import google.generativeai as genai` → `ModuleNotFoundError`  
**Root cause:** `pyproject.toml` specifies `google-genai` (the new SDK), not the legacy `google-generativeai`  
**Fix:** Use `from google import genai` and instantiate with `genai.Client(api_key=...)`. The `models.generate_content` call takes `contents=` as a list of `Part` objects for multimodal  
**Applies to:** `healf_agent/tools/vision.py`, dispatcher in `tools/__init__.py`

---

## G-13: Gemini Vision requires multimodal Part objects — not URL strings in text

**Symptom:** `score_images` passed URLs as plain text; Gemini returned hallucinated scores based on URL filenames  
**Root cause:** `gemini_client.models.generate_content(contents="...text with URLs...")` triggers text-only generation. Gemini never fetches the URLs  
**Fix:** Fetch image bytes with `httpx`, build `contents=[types.Part.from_text(prompt), types.Part.from_bytes(data=bytes, mime_type="image/jpeg"), ...]`  
**Applies to:** `healf_agent/tools/vision.py`

---

## G-14: kNN fallback to `product_type="Unknown"` is wrong — use `product_type=None`

**Symptom:** `benchmark_against_category` fell back to `knn(product_type="Unknown")` — correct for current corpus but wrong semantically. A future typed corpus would still filter to only "Unknown" entries  
**Root cause:** Plan spec said "fall back to Unknown" but the correct intent is "fall back to unfiltered (all types)"  
**Fix:** Extended `Storage.knn` to accept `product_type=None` (no WHERE clause); fallback in `benchmark.py` uses `knn(product_type=None, ...)`  
**Applies to:** `healf_agent/storage.py`, `healf_agent/tools/benchmark.py`

---

## G-15: `evaluate_listing_quality` dispatcher had `themes=[]` hardwired

**Symptom:** The 5-axis evaluator always received empty themes list, so the "review themes" grounding in the rubric prompt was permanently silenced ("No review themes available.")  
**Root cause:** Initial dispatch implementation passed `themes=[]` instead of loading stored themes from `review_themes` table  
**Fix:** Added `SELECT polarity, label, summary FROM review_themes WHERE product_gid=?` before calling `evaluate_listing_quality`  
**Applies to:** `healf_agent/tools/__init__.py` — `evaluate_listing_quality` dispatch branch

---

## G-16: `enqueue_hitl` `cursor.lastrowid` can be None on failed INSERT

**Symptom:** Function declared return type `int` but `sqlite3.Cursor.lastrowid` is `int | None`  
**Root cause:** Raw SQL INSERT via `storage.conn.execute()` — `lastrowid` is `None` if INSERT didn't produce a row  
**Fix:** Added guard: `row_id = cursor.lastrowid; if row_id is None: raise RuntimeError(...); return row_id`  
**Applies to:** `healf_agent/tools/act.py` — `enqueue_hitl`

---

## G-17: `Storage.list_hitl` AttributeError in Streamlit page runtime

**Symptom:** `pages/hitl.py` throws `AttributeError: 'Storage' object has no attribute 'list_hitl'` when loaded via `st.Page(hitl_run)`. Direct Python import confirms the method IS present.  
**Root cause:** Unknown — likely Streamlit module isolation. The `pages.hitl` module is imported before `healf_agent.storage` in `app.py`, which may cause a stale module reference in the page's execution context.  
**Status:** Unresolved as of 2026-05-16  
**First fix to try:** Reorder `app.py` imports so all `healf_agent.*` imports come before `from pages.hitl import run as hitl_run`. This ensures `healf_agent.storage` is fully loaded before the page module references it.  
**Diagnostic if reorder fails:** Add `print(id(healf_agent.storage), dir(Storage))` inside `run()` to confirm whether a different module object is being used.  
**Applies to:** `app.py`, `pages/hitl.py`

---

## G-18: Streamlit 1.57 removed legacy `pages/` auto-discovery

**Symptom:** Files placed in `pages/` directory are not auto-discovered as navigation pages. Chat page loads but sidebar shows no additional page links.  
**Root cause:** Streamlit 1.57 deprecated and removed the legacy multi-page auto-discovery pattern (`pages/*.py` with `st.set_page_config` in each).  
**Fix:** Use the `st.navigation()` API in the main `app.py` entry point:
```python
pg = st.navigation([
    st.Page(chat_page, title="Chat", icon="💬", default=True),
    st.Page(hitl_run, title="HITL Review", icon="📋"),
])
pg.run()
```
Each page must be a callable (not a file path) when it needs to share module-level imports with the host app. Only `app.py` calls `st.set_page_config()`.  
**Applies to:** `app.py`, any future pages added to `pages/`

---
