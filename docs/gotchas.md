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
