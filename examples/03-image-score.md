# Example 3 — Image Quality Score

**Product loaded:** LMNT Recharge Electrolytes Variety Pack
**URL:** `https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack`

**Prompt:** "How good are the product images?"

## Tool trace

1. → `fetch_product(url="https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack")` → 3 images found; URLs extracted from JSON-LD `image` array
2. → `score_images(product_id=..., image_urls=[...])` → Gemini 2.5 Flash vision scoring; 3 images evaluated across 5 dimensions; scores returned per image

## Agent response

**Image quality score: 72 / 100** — Strong hero shot; lifestyle context and detail shots are missing.

### Per-image breakdown

| Image | Score | Notes |
|-------|-------|-------|
| Hero — variety pack flat lay on white | 84/100 | Clean background, all flavours visible, good colour contrast |
| Single stick pack close-up | 71/100 | Good label legibility; slight overexposure on top edge |
| Lifestyle — hand holding stick pack | 62/100 | Low ambient light; background is distracting; no usage context |

### Dimension scores (averaged across 3 images)

| Dimension | Score | Assessment |
|-----------|-------|------------|
| Clarity & resolution | 81/100 | All images are sharp at product level |
| Background & composition | 76/100 | Hero is clean; lifestyle shot needs work |
| Label legibility | 79/100 | Text readable on hero and close-up |
| Lifestyle / usage context | 55/100 | Only one lifestyle image, poorly lit |
| Brand consistency | 68/100 | Colour palette consistent; logo not always visible |

### Recommendations

1. **Replace the lifestyle image** — shoot in natural light with the stick pack being added to a water bottle or glass. This scores consistently higher on Healf's category pages.
2. **Add a nutritional panel close-up** — competitors in the corpus with this image type score ~12 points higher on average.
3. **Add a pack-contents shot** — showing individual flavour packets laid out helps justify the "variety" naming.

---
*Tools used: `fetch_product`, `score_images` · Surface: Streamlit chat*
