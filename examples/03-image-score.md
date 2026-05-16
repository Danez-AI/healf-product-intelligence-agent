# Example 3 — Image Scoring

**Product loaded:** Recharge Electrolytes - Variety Pack
**URL:** `https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack`

**Prompt:** "How good are the product images? Score them and explain what's missing."

## Tool trace

1. → `score_images()`

## Agent response

Here's a full breakdown of the 4 product images scored across three axes — **clarity**, **lifestyle presence**, and **label legibility**:

---

## 📸 Image Score Summary

| # | Clarity | Lifestyle Shot | Label Legible | Overall |
|---|---------|---------------|---------------|---------|
| Image 1 | ⭐⭐⭐⭐⭐ | ❌ | ✅ | 4/5 |
| Image 2 | ⭐⭐⭐⭐⭐ | ❌ | ✅ | 5/5 |
| Image 3 | ⭐⭐⭐⭐⭐ | ❌ | ✅ | 4/5 |
| Image 4 | ⭐⭐⭐⭐⭐ | ❌ | ✅ | 5/5 |

**Average clarity: 5.0 / 5** ✅ | **Lifestyle shots: 0 of 4** ❌

---

## ✅ What's Working Well

- **Crystal-clear photography** — all 4 images score a perfect 5/5 for clarity, with sharp, well-lit product shots
- **Label legibility is strong** — the Gemini OCR confirmed all key on-pack text is readable, including electrolyte quantities (**1,000mg sodium, 200mg potassium, 60mg magnesium**)
- **Image 4 is a standout** — it's a full informational graphic containing:
  - Complete Nutrition Facts panel (5 calories, macros, % daily values)
  - Per-flavour ingredient lists for all 4 varieties
  - Certification badges: **No Sugar, No Gluten, Vegan Friendly, Paleo-Keto Friendly, Made in USA**
- **Image 2** cleverly shows powder spilling from a stick pack, adding tactile visual interest

---

## ❌ What's Missing

### 1. 🏃 No Lifestyle Shots (0 out of 4)
This is the single biggest gap. **Zero** images show the product in use — no athlete mid-workout, no one mixing a sachet into water, no outdoor/gym context. For an electrolyte brand competing in the active wellness space, this is a meaningful missed opportunity to create emotional connection and communicate *when* and *why* you'd use LMNT.

### 2. 🎨 No Individual Flavour Shots
The pack includes 4 distinct flavours (Watermelon Salt, Citrus Salt, Lemonade, Raspberry Salt), yet no image isolates or hero-shots individual sachets in a way that showcases each flavour's personality (e.g. a watermelon slice, citrus fruit, raspberry). This would help shoppers connect with the variety appeal.

### 3. 💧 No "Prepared Drink" Shot
No image shows the product mixed into a glass of water — a very common conversion-driving image for drink supplements (especially important for sparkling water mocktail positioning mentioned in the description).

---

## 💡 Recommendation Priority

| Fix | Impact | Effort |
|-----|--------|--------|
| Add 1–2 lifestyle/in-use shots | 🔴 High | Medium |
| Add a prepared-drink "beauty shot" | 🟠 Medium | Low |
| Add individual flavour hero shots | 🟡 Medium | Medium |

The informational content is excellent — it's the *context and emotion* that's absent. Adding even one lifestyle shot of someone active with an LMNT sachet would meaningfully improve the listing's conversion appeal.

## Run metadata

- Iterations: 2
- Total latency: 20,172 ms
- Tokens: 3,556 input / 937 output (cache_read: 2,754)
- Model: claude-sonnet-4-6

---
*Tools used: `score_images` · Surface: Streamlit chat*
