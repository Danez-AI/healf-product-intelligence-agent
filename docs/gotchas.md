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

## G-10: ~~MISDIAGNOSIS~~ — LMNT ingredients ARE in RSC payload; regex was wrong → see G-29

**Original symptom:** `check_field(field="ingredient", value="sodium")` returned `present: false, evidence: []`  
**Original misdiagnosis:** Claimed LMNT had no ingredient data in JSON-LD or RSC metafields  
**Actual root cause:** The old `_METAFIELD_RE` regex looked for `"ingredients":"<value>"` (a direct JSON property), but Shopify embeds metafields as `{"key":"ingredients","value":"..."}` objects inside a `"metafields":[...]` array — a completely different shape that the regex never matched.  
**Fix:** Replaced regex with bracket-walking JSON array decode anchored on `"metafields":[`. See G-29 for the correct extraction pattern and `healf_agent/tools/ingest.py` → `extract_metafields`.  
**Status:** Resolved — 2026-05-16 Session 12

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

## G-19: Multiple stale Streamlit processes accumulate on port 8501

**Symptom:** After multiple sessions, `netstat -ano | findstr :8501` shows 8+ PIDs all listening. The HITL page throws `AttributeError: 'Storage' object has no attribute 'list_hitl'` even after the import reorder fix — because a stale process is serving requests with an old in-memory module that pre-dates `list_hitl`.  
**Root cause:** Each `python -m uv run streamlit run app.py &` in a Bash tool session starts a new Streamlit process. The old ones are never cleaned up between sessions.  
**Fix:** Before every smoke test, kill all listeners on 8501 and start fresh:
```powershell
Get-NetTCPConnection -LocalPort 8501 -State Listen | Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
$worktree = "C:\Users\Daran\AI\Healf AI Agent\.claude\worktrees\feat-healf-agent"
Start-Process -FilePath "python" -ArgumentList "-m","uv","run","streamlit","run","app.py","--server.headless","true","--server.port","8501" -WorkingDirectory $worktree -WindowStyle Hidden
```
**Applies to:** Any session that runs Streamlit smoke tests

---

## G-20: `--filter eval-00` does NOT exclude eval-009 — substring match catches "00" in "009"

**Symptom:** Running `python -m evals.runner --filter eval-00 --db healf.sqlite` was intended to match eval-001 through eval-008 while skipping eval-009 (the LLM-rubric case). Instead, all 9 cases ran. eval-009 failed with `dispatch error: 'ANTHROPIC_API_KEY'` and a score-0.0 row was still persisted.  
**Root cause:** The `--filter` argument performs a plain substring match (`args.filter in c["id"]`). The string `"eval-00"` is a substring of `"eval-009"` because "009" contains "00". The naming scheme `eval-001 … eval-009` does not create a natural partition under substring matching.  
**Fix options:**  
1. Rename the LLM-rubric case to `eval-010` (two-digit suffix breaks the substring overlap).  
2. Use a more specific filter prefix, e.g. `--filter eval-00` won't work; instead filter on the tool name or add a `"tags"` field to golden.jsonl and filter on that.  
3. Change the runner's `--filter` to support a regex or a comma-separated list of IDs.  
**Fix applied (2026-05-16):** Changed `--filter` from substring match to **comma-separated exact-ID match**. `--filter eval-001` now matches only `eval-001`. `--filter eval-001,eval-002` matches both. Regression test `test_filter_exact_match_excludes_eval_009` added.  
**Applies to:** `evals/runner.py` (`--filter` flag)

---

## G-21: `fastmcp-slim` requires `[server]` extra for `from fastmcp import FastMCP`

**Symptom:** After changing `pyproject.toml` to use `fastmcp-slim` (without extras), `uv sync` installs the slim package but `from fastmcp import FastMCP` raises `ImportError: FastMCP server support is not installed. Install fastmcp or fastmcp-slim[server]`.  
**Root cause:** `fastmcp-slim` splits server and client functionality into optional extras. The bare `fastmcp-slim` package installs only the core; the `[server]` extra pulls in `sse-starlette`, `uvicorn`, and related deps required for `FastMCP`.  
**Fix:** Use `fastmcp-slim[server]>=3.3.0` in `pyproject.toml`. This is the correct dependency for `mcp_server.py` which uses `FastMCP` from the server module.  
**Note:** The original `fastmcp>=0.2.0` constraint was satisfied by `fastmcp-slim 3.3.0` (with server support pre-included) because the slim package provides the `fastmcp` namespace. A tighter `<0.3.0` pin caused uv to install legacy `fastmcp 0.2.0` (a completely different package with no `__init__.py`) instead.  
**Applies to:** `pyproject.toml`, `mcp_server.py`

---

## G-22: `from ... import name` inside a function body makes `name` local for the WHOLE function

**Symptom:** `cannot access local variable 'fetch_product_page' where it is not associated with a value` — raised on every call to the `fetch_product` branch of `dispatch_tool`, even though `fetch_product_page` is imported at module level.  
**Root cause:** Python's scoping rule: if a name is assigned *anywhere* in a function (including via `from module import name`), Python treats it as local throughout the entire function. The `compare_products` branch at line 233 had a redundant `from healf_agent.tools.navigate import fetch_product_page` — this made `fetch_product_page` a local in `dispatch_tool`, shadowing the module-level import and causing `UnboundLocalError` at line 104.  
**Fix:** Remove the redundant local import inside `compare_products` branch (`healf_agent/tools/__init__.py` line 233). Both `fetch_product_page` and `parse_product` were already imported at module level.  
**Applies to:** `healf_agent/tools/__init__.py`

---

## G-23: n8n homeserver cannot reach Windows PC webhook on port 8000 — Windows Firewall blocks it

**Symptom:** n8n workflow executions complete in ~150ms with "success" — POST /audit node silently fails, IF node never sees a `score` field, workflow takes false branch and ends. The `onError: continueRegularOutput` setting masks the failure.  
**Root cause:** Windows Firewall blocks inbound TCP port 8000 from other LAN hosts. The webhook server at `192.168.0.179:8000` is unreachable from the n8n homeserver at `192.168.0.87`.  
**Fix (requires admin):** `netsh advfirewall firewall add rule name="Healf Webhook 8000" dir=in action=allow protocol=TCP localport=8000`  
**Applies to:** `docs/n8n-setup.md` (add as Step 0 prerequisite)

---

## G-24: `.env` line 5 (`HEALF_USER_AGENT`) causes `uv --env-file` parse warning

**Symptom:** `python -m uv run --env-file .env uvicorn webhook:app` prints `warning: Failed to parse environment file '.env' at position 34: HealfProductIntelligenceAgent/0.1 (https://...)`. All API keys (lines 1–4) still load correctly.  
**Root cause:** `HEALF_USER_AGENT` value contains a URL with `/` characters that uv's env-file parser chokes on.  
**Status:** Warning only — no functional impact. API keys load fine.  
**Fix (optional):** Quote the value in `.env`: `HEALF_USER_AGENT="HealfProductIntelligenceAgent/0.1 (https://...)"`.  
**Applies to:** `.env`, any `python -m uv run --env-file .env` invocation

---

## G-25: Stale Python process holds port 8000 between sessions

**Symptom:** Starting `uvicorn webhook:app --port 8000` fails with `[WinError 10048] only one usage of each socket address`.  
**Root cause:** A previous uvicorn process was started in background and never killed when the session ended.  
**Fix:** `netstat -ano | findstr ":8000" | findstr "LISTENING"` → get PID → `Stop-Process -Id <PID> -Force`.  
**Applies to:** Any session that restarts the webhook server

---

## G-26: n8n-mcp MCP API tools unavailable — N8N_API_URL not configured for this project

**Symptom:** `mcp__n8n-mcp__n8n_test_workflow`, `mcp__n8n-mcp__n8n_executions`, etc. not in available tools. Only the 7 "always available" tools show up (search_nodes, get_node, validate_node, validate_workflow, search_templates, get_template, tools_documentation).  
**Root cause:** The Healf AI Agent project had no `.mcp.json`, so the n8n-mcp MCP server ran without `N8N_API_URL`/`N8N_API_KEY`.  
**Fix:** Created `C:\Users\Daran\AI\Healf AI Agent\.mcp.json` with the same n8n-mcp config as `C:\Users\Daran\AI\Personal Trainer Agent\.mcp.json`. Restart Claude Code to load.  
**Applies to:** All sessions in this project — must restart Claude Code once after `.mcp.json` creation

---

## G-27: Split In Batches v3 skips batch output in manual test mode

**Symptom:** n8n workflow manual execution stops at Split In Batches (144ms total). `lastNodeExecuted: "Split In Batches"`. POST /audit never runs. Execution shows output 0 (batch) empty, output 1 (done) has the URL item.  
**Root cause:** Split In Batches v3 in n8n manual test mode doesn't loop back — with 1 item and batchSize=1, it routes the item to the "done" output (1) rather than the "batch" output (0). This only affects manual/test execution; scheduled runs work correctly.  
**Fix applied (2026-05-16):** Removed Split In Batches from the live n8n workflow via REST API. URL List now connects directly to POST /audit. New workflow versionId: `5e5ec0b4-16d9-4e98-bad1-9ed7c56b231e`.  
**Applies to:** `n8n/healf-catalog-audit.json` (should be updated to match live workflow)

---

## G-24: `uv run --env-file .env` warns on HEALF_USER_AGENT line but still loads prior keys

**Symptom:** `warning: Failed to parse environment file .env at position 34: HealfProductIntelligenceAgent/0.1 (https://...)` — uv chokes on the URL value containing `(` and `)`.  
**Impact:** HEALF_USER_AGENT is not set; all API keys on lines 1–4 load fine.  
**Fix options:** Quote the value in `.env` (`HEALF_USER_AGENT="..."`) or accept the warning (user-agent is optional, has a default).  
**Applies to:** `.env`, `healf_agent/tools/navigate.py`

---

## G-28: n8n IF node errors with `Cannot read properties of undefined (reading 'caseSensitive')` when score is a string

**Symptom:** Full workflow run — nodes 1–4 green, IF score < 3 shows red with error: `Cannot read properties of undefined (reading 'caseSensitive')`. The score value in the POST /audit HTTP response arrives as `"2"` (JSON number, but n8n treats it as string in some contexts).  
**Root cause:** n8n IF node's numeric `is less than` operator internally calls a string-comparison method when type coercion is disabled and the left-hand value has an ambiguous type. n8n suggests enabling "Convert types where required" as the fix.  
**Fix applied (2026-05-16 Session 11):** Enabled **Convert types where required** toggle in the IF score < 3 node Parameters tab. Workflow saved and republished. All 6 nodes now run green. New versionId: `0292c2e7-78c0-42b9-9d35-6a2753456dc4`.  
**Applies to:** `n8n/healf-catalog-audit.json` — IF node, `convertTypesWhenComparing` must be `true`

---

## G-30: Two product-load code paths drifted after Wave 15 — Streamlit showed `present: null` despite tests passing

**Symptom:** All 67 tests passed post-Wave-15, but clicking **Fetch** in the live Streamlit app and asking "Does this product have sodium?" still returned `present: null, extraction_status: "no_metafields"`.  
**Root cause:** `app.py` has its own inline product-load block (lines 38-50) that predated the dispatcher. Wave 15 updated `dispatch_tool("fetch_product")` in `healf_agent/tools/__init__.py` but left `app.py`'s copy intact. The copy still called `meta.get("ingredient")` (singular), whereas the new extractor returns `"ingredients"` (plural Shopify key). `raw_metafields` was never set, so `check_field` correctly returned `present: null`.  
**Fix:** Extracted a single `load_full_product(url) -> Product` helper in `healf_agent/tools/ingest.py`. Both `app.py` and `dispatch_tool("fetch_product")` now call it — one source of truth, zero drift.  
**Lesson:** Whenever you change ingestion shape, `grep -n "extract_metafields("` across the repo to find every caller and update all of them. Unit tests only cover the paths they exercise; the Streamlit UI's load path was untested.  
**Fixed:** 2026-05-16 Session 12 (Wave 16) — `load_full_product` helper introduced; `test_load_full_product_populates_ingredients_and_metafields` added.

---

## G-29: Shopify metafields are `{key, value}` objects inside an array — NOT direct JSON properties

**Symptom:** Ingredient/claim data silently missing; `extract_metafields` returns `{}`; agent says "sodium not found" for LMNT despite website listing "Salt (Sodium Chloride)".  
**Root cause:** Shopify stores metafields in the RSC flight payload as a JSON array of objects: `"metafields":[null, {"key":"ingredients","value":"Citrus:\nSalt (Sodium Chloride)..."}]`. A regex looking for `"ingredients":"..."` (a direct key-value property) never matches this shape.  
**Correct extraction pattern:**
1. Find the literal `"metafields":[` in the decoded RSC text.
2. Walk forward character-by-character, tracking `[`/`]` depth while respecting string boundaries (escaped chars), to find the matching `]`.
3. Slice out the balanced substring and decode with `json.loads`.
4. Iterate entries; for each non-null `{"key": K, "value": V}` dict, clean V (strip `<br>` HTML, unescape entities) and store `{K: V}`.
**Why not regex:** Metafield values contain commas, nested brackets, `<br>` tags, and escaped quotes — all of which break `[^\]]*` and similar patterns.  
**Why scan all occurrences:** RSC is multiple concatenated JSON chunks; `"metafields":[` can appear more than once with varying completeness. Keep the longest value per key.  
**Implementation:** `extract_metafields` in `healf_agent/tools/ingest.py` (uses `_slice_balanced_array` helper).  
**Fixed:** 2026-05-16 Session 12 — `_METAFIELD_RE` regex replaced, G-10 misdiagnosis corrected.

---

## G-31: Multi-flavour ingredient blobs were flattened — per-flavour structure lost

**Symptom:** Agent marks both Malic Acid and Citric Acid as present in all flavours of a Variety Pack; adds caveat "the ingredient data appears to be stored as a single combined list." Both claims are wrong — the metafield *does* break out ingredients per flavour.  
**Root cause:** `_split_ingredient_blob` (the original helper) deduplicates across flavours into a single flat list. `check_field("ingredient", "malic acid")` returned `present: True` but had no way to surface "only in Watermelon."  
**Fix:** Added `_split_ingredient_blob_by_flavour(blob) -> dict[str, list[str]]` in `healf_agent/tools/ingest.py`. `load_full_product` now populates `Product.ingredients_by_flavour` when headers are detected. `check_field` enriches ingredient answers with `per_flavour: [...]` and `all_flavours: [...]` so the agent can say "malic acid is only in Watermelon — the other three flavours use citric acid."  
**Backward compat:** `Product.ingredients` (flat deduplicated list) is unchanged — all existing tools (eval, consistency, draft, compare) continue to work.  
**Added:** 2026-05-16 Session 14 — Wave 17.

---

## G-32: Healf benefit prose is split across RSC Flight HTML and metafields — none of it reached the agent

**Symptom:** Agent answered "What are the health benefits?" with "The claims field on the Healf listing is currently empty — I'd recommend a manual check on the live Healf page." The page clearly states EFSA-style benefits ("Contributes to electrolyte balance", "Helps reduce tiredness and fatigue") and has a suggested-use section.  
**Root cause (3 parts):**  
1. `<div class="old-description">` with the benefit bullets lives inside the RSC Flight payload as an escaped HTML string (`__next_f.push([1, "\\u003cdiv class=\\"old-description\\"..."])`). Parsing the raw page DOM with selectolax doesn't find it — selectolax sees a `<script>` tag, not a `<div>`. Must parse the decoded RSC flight text instead.  
2. `raw_metafields["why_its_healf"]` is `"$24"` on the LMNT product — an unresolved RSC Flight pointer (reference to another server-component chunk), not real text. Passing it to the agent produces gibberish.  
3. `raw_metafields["suggested_use"]` was extracted correctly but never surfaced — not in `product_ctx`, not in any tool output.  
**Fix:** `_extract_descriptive_text(html, meta)` in `healf_agent/tools/ingest.py` — decodes RSC flight text, parses it with selectolax to find `div.old-description`, appends real metafield values (`why_its_healf`, `suggested_use`) after filtering RSC pointer values (regex `^\$\d+$`). Result stored in `Product.page_text`. `app.py` injects `page_text` into the per-turn agent context between `--- Page description text ---` delimiters.  
**Added:** 2026-05-16 Session 14 — Wave 18.

---

## G-33: Healf Shopify JSON endpoints all blocked (Wave 0 probe result)

**Probe date:** 2026-05-16 Session 15  
**URLs tested:**
- `https://healf.com/products/lmnt-recharge-electrolytes-variety-pack.json` → 404 (HTML)
- `https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack.json` → 200 but HTML content-type (Next.js renders the PDP, ignores `.json` suffix)
- `https://healf.com/products/lmnt-recharge-electrolytes-variety-pack.js` → 404
- `https://healf.com/products.json?limit=1` → 200 but HTML (same issue)

**Conclusion:** Healf's Next.js App Router intercepts all these paths and returns HTML, not Shopify JSON. No canonical product JSON API is reachable publicly. (Previously noted as G-02 in general terms; this confirms with specific probes.)  
**Impact on Wave A:** Image extraction must use RSC flight payload merge (variant_base_images metafield + Shopify CDN regex fallback) rather than the Shopify products JSON endpoint.  
**Added:** 2026-05-16 Session 15 — Wave 0.

---

## G-34: `_RSC_PTR_RE` was digits-only — hex pointers like `$1e` slipped through (Wave B)

**Symptom:** `Product.claims == ["$1e"]` — a raw RSC Flight chunk pointer appeared in agent output.  
**Root cause:** `_RSC_PTR_RE = re.compile(r"^\$\d+$")` only matches decimal digit sequences. RSC pointers use hex chunk indices (`$1e`, `$2a`, etc.) — these contain letters a–f and were not matched.  
**Fix:** Changed to `re.compile(r"^\$[0-9a-f]+$", re.IGNORECASE)` in `ingest.py`. The two existing call sites in `_extract_descriptive_text` and the new claims-extraction fallback all use this regex.  
**Added:** 2026-05-16 Session 15 — Wave B.

---

## G-35: Image gallery lives in RSC `variant_base_images` metafield, not JSON-LD (Wave A)

**Symptom:** `score_images` reported `image_count: 1` even though the live PDP shows 4 images.  
**Root cause:** `_images_from_block` only read the JSON-LD `"image"` field, which Healf emits as a single scalar string (the hero). The remaining gallery images are stored in the `variant_base_images` RSC metafield as a JSON-encoded array: `[{"src":"https://cdn.shopify.com/...","altText":null}]`. `extract_metafields` was calling `_clean_metafield_text` on this value, which stripped the JSON structure entirely.  
**Fix:** `_extract_variant_base_image_urls(flight_text)` parses `variant_base_images` as JSON (before text-cleaning). `_fallback_shopify_image_urls(flight_text)` regex-scans for any Shopify/Backblaze CDN URLs as a last resort. `load_full_product` merges all sources with order-preserving dedup into `Product.images`.  
**Added:** 2026-05-16 Session 15 — Wave A.

---

## G-36: Vision OCR pass adds `on_pack_text` / `contains_nutrition_panel` — ~30% token bump (Wave C)

**Context:** Serving sizes, electrolyte mg quantities, and nutrition panels are printed on product label images — the structured fields never contained them. The agent was falsely saying these details were "missing".  
**Fix:** Extended `_VISION_PROMPT` to also request `on_pack_text` (verbatim label OCR) and `contains_nutrition_panel` (bool) per image. `score_images` now returns `aggregated_on_pack_text` and `any_nutrition_panel`. `SYSTEM_PROMPT` directs the agent to call `score_images` for serving size / nutrition questions.  
**Cost:** ~30% more output tokens per `score_images` call (max 8 images → ~£0.001/call). OCR output is advisory — Gemini may miss text on blurry crops.  
**Added:** 2026-05-16 Session 15 — Wave C.

---

## G-37: `run_agent_turn` now returns a 3-tuple — debug expanders in Streamlit (Wave D)

**Change:** `run_agent_turn` signature changed from `(text, trace)` to `(text, trace, debug)`. The `debug` dict captures per-iteration: full messages snapshot, LLM response content, token usage (input/output/cache), stop_reason, model, latency_ms, request_id, system prompt, and injected product context.  
**Callers updated:** `app.py` and `tests/test_agent.py` — both unpack the 3-tuple. No other callers exist.  
**Streamlit:** Two new collapsed expanders on every agent reply: "debug — prompts & messages" (system prompt, injected context, per-iter messages/response) and "debug — usage & timing" (dataframe with token counts and latency). Historical messages also re-render these expanders.  
**No disk persistence:** Debug data lives in `st.session_state` only (per user choice). Extend later via `agent_runs` table or JSONL if needed.  
**Added:** 2026-05-16 Session 15 — Wave D.


---

## G-38 — Fake/404 Product URL Raises Raw Traceback in Streamlit UI

**Discovered:** 2026-05-17 Session 10 (interviewer review)  
**Symptom:** Entering a URL that returns a 404 (e.g. `healf.com/en-uk/products/this-does-not-exist-zzz123`) triggers `ValueError: no Product JSON-LD found` in `load_full_product`. Streamlit renders the full Python traceback including internal file paths in the main chat area — visible to the end user.  
**Root cause:** `load_full_product` in `healf_agent/tools/ingest.py` raises `ValueError` when JSON-LD is absent. The Streamlit Fetch button handler in `app.py` does not catch this exception.  
**Fix:** Wrap the `load_full_product` call in the `app.py` Fetch button handler with `try/except ValueError as e: st.error(f"Could not load product: {e}")`. Optionally also catch `httpx.HTTPError` for network failures.  
**Status:** OPEN — not yet fixed.


---

## G-39 — `benchmark_against_category` always read from the wrong database

**Discovered:** 2026-05-17 Session 11 (E2E test after corpus rebuild)
**Symptom:** `benchmark_against_category` always returned "no neighbours" even after corpus was rebuilt with real product types. The agent fell back to domain-knowledge comparison every time.
**Root cause:** `dispatch_tool` in `healf_agent/tools/__init__.py` opened `healf.sqlite` (via `HEALF_DB` env var) for both benchmark and evaluate calls. But corpus embeddings are written to `corpus.sqlite` by `scripts/build_corpus.py`. The `corpus` table in `healf.sqlite` was always empty.
**Fix:** Changed benchmark/evaluate dispatch blocks to use `HEALF_CORPUS_DB` env var (default `corpus.sqlite`). `evaluate_listing_quality` split into `corpus_storage` (corpus.sqlite, for kNN) and `healf_storage` (healf.sqlite, for review_themes). Committed `86042dc`.
**Added:** 2026-05-17 Session 11.


---

## G-40 — Corpus accumulates stale rows across rebuilds

**Discovered:** 2026-05-17 Session 11 (distribution check after clean rebuild)
**Symptom:** After two corpus rebuilds, `SELECT COUNT(*) FROM corpus` returned ~267 rows (expected 147). Old `"Unknown"` and `"-"` rows from pre-fix builds persisted. The `upsert_corpus_entry` uses `ON CONFLICT(handle) DO UPDATE` — it updates matching handles but never deletes rows for handles not in the current build.
**Fix:** Run `DELETE FROM corpus; VACUUM;` before each rebuild, or delete `corpus.sqlite` and let the build recreate it. Always verify row count after rebuild matches the build log.
**Added:** 2026-05-17 Session 11.

---

## G-41 — `compare_products` dispatcher called undefined `fetch_product_page`

**Discovered:** 2026-05-17 Session 12 (Playwright E2E test of G-39 fix)
**Symptom:** `compare_products` tool always returned `"error": "name 'fetch_product_page' is not defined"` in the tool trace. The agent fell back to benchmark data only — no structured side-by-side table.
**Root cause:** The `compare_products` block in `dispatch_tool` (`healf_agent/tools/__init__.py`) called `fetch_product_page(url)` and `parse_product(html, url=url)` — two functions that were never imported in that block and don't exist in scope. This was leftover scaffolding that predated the `load_full_product` consolidation (see CLAUDE.md — "all product fetching goes through `load_full_product`").
**Fix:** Replace the two-step `fetch_product_page` + `parse_product` calls with a single `load_full_product(url)` call:
```python
from healf_agent.tools.ingest import load_full_product
p = load_full_product(url)
```
**File:** `healf_agent/tools/__init__.py` (compare_products dispatch block)
**Added:** 2026-05-17 Session 12.
