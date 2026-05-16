# Example 4 — Copy Rewrite

**Product loaded:** Recharge Electrolytes - Variety Pack
**URL:** `https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack`

**Prompt:** "Draft a better product description for this listing."

## Tool trace

1. → `cluster_review_themes(polarity_filter="all")`
2. → `benchmark_against_category(k=5)`
3. → `score_images()`
4. → `check_consistency()`
5. → `evaluate_listing_quality()`
6. → `draft_rewrite(gaps=['Serving size and preparation instructions missing', 'Specific electrolyte amounts per serving not listed (1000mg sodium, 200mg potassium, 60mg magnesium confirmed via OCR)', 'No indication of sachet count or flavours included in variety pack', 'Encoding artefacts in claims copy need cleaning', 'No certifications or quality credentials mentioned (no sugar, no gluten, vegan, keto/paleo-friendly, made in USA — all confirmed via OCR)', 'Differentiation rationale absent — high-sodium formula rationale and target use cases not explained', 'No mention of suitability (vegan, athlete-friendly, keto/fasting)', 'No lifestyle imagery, missing emotional/aspirational connection'])`
7. → `enqueue_hitl(drafted_description="## LMNT Recharge Electrolytes — Variety Pack

Hydration isn't just about drinking more water. It's about the minerals your body actually loses — and replacing them in the right amounts.

Each LMNT sachet delivers a precisely formulated electrolyte hit: **1,000mg sodium, 200mg potassium, and 60mg magnesium** per serving. That's the ratio designed to support genuine hydration during training, low-carb eating, intermittent fasting, or simply getting through a demanding day. Magnesium contributes to normal muscle and psychological function, supports energy-yielding metabolism, and helps reduce tiredness and fatigue.

The higher sodium count is deliberate. Sweat, fasting, and low-carbohydrate diets deplete sodium faster than most people realise — and most sports drinks don't come close to replacing it. LMNT addresses this directly, with no added sugar, no artificial sweeteners beyond stevia, no caffeine, and nothing dodgy.

**What's in the box:**
12 sachets — 3 each of four bold flavours:
- 🍉 **Watermelon Salt** — sweet, salty, and refreshing
- 🍋 **Lemonade** — bright and tangy
- 🍊 **Citrus Salt** — crisp lemon-lime zing
- 🫐 **Raspberry Salt** — bold and fruity

Each flavour is sugar-free, gluten-free, vegan-friendly, and paleo/keto compatible. Made in the USA.

**How to use:**
Mix one sachet with 500ml of water (or more, to taste). Try it with sparkling water for an easy, zero-alcohol mocktail. Drink before, during, or after exercise — or any time you need a hydration boost.

Rated **4.9/5 from 445 reviews** on Healf. A favourite among athletes, endurance runners, and anyone serious about clean, no-compromise hydration.

---
*Food supplements should not replace a varied, balanced diet. If pregnant, breastfeeding, or taking medication, consult a healthcare professional before use.*", gap_summary="5 key gaps addressed: (1) Electrolyte quantities (1000mg Na / 200mg K / 60mg Mg) added — sourced from image OCR label text. (2) All 4 flavours and 12-sachet count now explicitly listed. (3) Certifications (no sugar, no gluten, vegan, keto/paleo, made in USA) added — confirmed via OCR. (4) High-sodium formula rationale and target audiences (athletes, keto, fasting) now explained. (5) Encoding artefacts (Â) removed from all claims. Bonus: suggested-use instructions integrated into body copy; 4.9/5 rating surfaced as social proof signal. No lifestyle imagery exists in the current gallery — recommend adding one action/lifestyle shot to complement the studio images.")`

## Agent response

The rewrite is drafted ✅ and queued for human approval (entry #8). Here's a full breakdown of what was done and why:

---

## 📋 What the Analysis Found

| Axis | Score | Key Issue |
|---|---|---|
| Completeness | 2/5 | No sachet count, no flavour list, no electrolyte quantities |
| Differentiation | 2/5 | Nothing explaining *why* LMNT's formula is different |
| Trust signals | 4/5 | Strong rating (4.9/5, 445 reviews) but certifications absent |
| Ingredient transparency | 2/5 | Mg/K/Na amounts completely missing from copy |
| Copy quality | 2/5 | Encoding artefacts (`Â`), terse, no Healf brand voice |

---

## ✍️ What the Rewrite Fixes

1. **Electrolyte quantities added** — `1,000mg sodium · 200mg potassium · 60mg magnesium` per sachet, sourced directly from image OCR (label nutrition panel, image 4).
2. **All 4 flavours named** — Watermelon Salt, Lemonade, Citrus Salt, Raspberry Salt, with the 12-sachet / 3-per-flavour structure made explicit.
3. **Formula rationale explained** — The high-sodium design choice is contextualised for athletes, keto, and fasting use-cases.
4. **Certifications surfaced** — No sugar · No gluten · Vegan · Keto/Paleo · Made in USA, all confirmed via OCR from the product label.
5. **Encoding artefacts removed** — The `Â` character stripped from all claims.
6. **Suggested use integrated** — 500ml mixing instruction and sparkling water mocktail tip woven naturally into the copy.
7. **Social proof activated** — 4.9/5 from 445 reviews called out in copy, not just metadata.

---

## 🖼️ One Remaining Gap: Lifestyle Imagery

All 4 current images are clean studio shots (avg clarity: 5/5, which is great) but **none are lifestyle photos**. Competitors and high-performing Healf listings typically include at least one action or in-context shot (e.g. athlete mid-run, packet next to a gym bag). Worth flagging to the creative team.

## Run metadata

- Iterations: 5
- Total latency: 39,471 ms
- Tokens: 9,233 input / 1,834 output (cache_read: 11,414)
- Model: claude-sonnet-4-6

---
*Tools used: `cluster_review_themes`, `benchmark_against_category`, `score_images`, `check_consistency`, `evaluate_listing_quality`, `draft_rewrite`, `enqueue_hitl` · Surface: Streamlit chat*
