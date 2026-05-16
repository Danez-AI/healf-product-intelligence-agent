# Session 15 Handoff — 2026-05-16

## What was completed this session

### Wave 19 — Accuracy & Observability (tagged `wave-19-accuracy-and-observability`)

User reported 3 wrong answers + asked about logging after testing the LMNT product page.

#### Wave 0 — Shopify endpoint probe
- Confirmed all `/products/{handle}.json` endpoints return HTML (Next.js intercepts). No Shopify JSON API available. Documented as **G-33**.

#### Wave A — Image gallery extraction (`a03ff9e`)
- **Problem:** `score_images` reported `image_count: 1`; live PDP has 4 images.
- **Root cause:** `_images_from_block` only read JSON-LD `image` (single scalar). RSC `variant_base_images` metafield holds the gallery as a JSON-encoded array — but `_clean_metafield_text` was destroying the JSON structure.
- **Fix:** `_extract_variant_base_image_urls(flight_text)` parses `variant_base_images` as JSON before text-cleaning. `_fallback_shopify_image_urls(flight_text)` regex-scans CDN URLs. `load_full_product` merges all sources with order-preserving dedup.
- **Tests:** +3 (total 77)

#### Wave B — Claims + `$1e` pointer fix (`14b38e8`)
- **Problem:** `Product.claims == ["$1e"]` — hex RSC pointer leaked through.
- **Root cause:** `_RSC_PTR_RE = r"^\$\d+$"` only matched decimal digits; `$1e` has hex letter `e`.
- **Fix 1:** `_RSC_PTR_RE` → `r"^\$[0-9a-f]+$"` with `re.IGNORECASE`.
- **Fix 2:** `_claims_from_old_description(html)` extracts `<li>` items from `<div class="old-description">` in RSC flight (same source as `_extract_descriptive_text`). Now the primary claims source in `load_full_product`; metafield fallback is pointer-filtered.
- **Tests:** +3 (total 80)

#### Wave C — Vision OCR (`9bdec15`)
- **Problem:** Agent said "serving size missing" — it's printed on the label image.
- **Fix:** `_VISION_PROMPT` extended to request `on_pack_text` (label OCR) and `contains_nutrition_panel` per image. `score_images` returns `aggregated_on_pack_text` and `any_nutrition_panel`. `SYSTEM_PROMPT` directs agent to call `score_images` for nutrition/serving-size questions.
- **Tests:** +3 (total 83, new `tests/test_vision.py`)

#### Wave D — Streamlit observability (`589a103`)
- **Problem:** No logging anywhere; bad agent answers undebuggable.
- **Fix:** `run_agent_turn` now returns `(text, trace, debug)` 3-tuple. `debug` captures: system prompt, injected product context, per-iteration messages snapshot, LLM response content, token usage (input/output/cache), stop_reason, model, latency_ms, request_id. Two new Streamlit expanders: "debug — prompts & messages" and "debug — usage & timing". In-memory only (no disk persistence).
- **Tests:** +1 (total 84)

#### Wave E — Docs
- `docs/gotchas.md`: G-33..G-37
- `CLAUDE.md` Key Decisions: 7 new bullets for Session 15

## Current state

| Item | Value |
|------|-------|
| Branch | `worktree-feat-healf-agent` |
| Worktree | `C:\Users\Daran\AI\Healf AI Agent\.claude\worktrees\feat-healf-agent` |
| Latest tag | `wave-19-accuracy-and-observability` |
| Latest commit | `fe30623` |
| Tests passing | 84 |

## Known issues / follow-up candidates

1. **Triple `extract_rsc_flight` call per `load_full_product`** — Wave A image merge + `_extract_descriptive_text` + `extract_metafields` each call it. Not a correctness bug; ~3-5ms wasted per load. Fix: cache with `functools.lru_cache(maxsize=4)` or pass `flight_text` as a parameter. Flagged by code quality reviewer.
2. **DRY: `_claims_from_old_description` duplicates `_extract_descriptive_text` core** — both parse `div.old-description`. Could extract a shared helper. Low priority.
3. **No test for malformed Gemini response with new OCR fields** — the regex fallback path in `score_images` is untested with `on_pack_text`. Consider adding `test_score_images_malformed_gemini_response`.
4. **Live Streamlit smoke not yet done** — the plan called for end-to-end browser verification of the 3 original bad answers. Recommend doing this at the start of Session 16.

## How to resume

```powershell
cd "C:\Users\Daran\AI\Healf AI Agent\.claude\worktrees\feat-healf-agent"
python -m uv run pytest -v   # 84 passing

# Kill stale Streamlit (G-19)
Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*streamlit*' } | Stop-Process

# Run Streamlit
python -m uv run streamlit run app.py
```

Then smoke-test the 3 original issues:
1. Fetch LMNT → ask "how many images?" → expect 3+
2. Ask "what claims does this product make?" → expect EFSA bullets, no `$1e`
3. Ask "what's the serving size?" → agent should call `score_images`, quote OCR text
4. Check the two new debug expanders are populated
