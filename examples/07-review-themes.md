# Example 7 — Review Themes

**Product loaded:** LMNT Recharge Electrolytes Variety Pack
**URL:** `https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack`

**Prompt:** "What do customers love and hate about this product?"

## Tool trace

1. → `fetch_reviews_full(product_id=..., max_pages=5)` → Yotpo API paginated; 445 reviews fetched across 5 pages; average rating: 4.9
2. → `cluster_review_themes(product_id=..., n_clusters=6)` → k-means clustering on review embeddings (text-embedding-3-small); 6 themes identified with sentiment labels and representative quotes

## Agent response

Based on 445 reviews, here's what customers consistently love and flag:

### What customers love

**1. Taste variety (38% of reviews) — strongly positive**
> *"Tried all the flavours in the variety pack — mango chilli is my favourite but honestly they're all good. No weird aftertaste like most electrolyte drinks."*

The variety pack format is a major driver of first purchases. Many reviewers mention trying LMNT for the first time via this pack before committing to a single flavour.

**2. Hydration effectiveness (29% of reviews) — strongly positive**
> *"I used to get afternoon headaches every day. Since adding LMNT after my morning run they've gone. The sodium content is much higher than competitors and I think that's why it works."*

Functional outcomes dominate this cluster. Reviewers describe performance, headache relief, and sustained energy rather than taste.

**3. Zero sugar / clean formula (18% of reviews) — strongly positive**
> *"Finally an electrolyte drink that doesn't taste like a children's candy. No sweeteners, no junk — you can actually feel the difference."*

### What customers flag

**4. Price perception (9% of reviews) — mixed**
> *"Works brilliantly but at £1 per stick it's hard to justify daily use. I ration it to workout days only."*

Price concern is real but not a dealbreaker — reviewers who flag it still rate 4–5 stars. The perception issue is value-per-use rather than absolute price.

**5. Flavour preference mismatch (4% of reviews) — mildly negative**
> *"The citrus salt is too salty even for me and I love savoury. Raspberry and mango are much better. Wish you could pick your own variety."*

A small subset of buyers find specific flavours too intense. No single flavour is universally disliked.

**6. Packaging / dissolution (2% of reviews) — mildly negative**
> *"The stick packs don't always mix well in cold water — need to shake hard or use warm water first."*

Minor usability note; not a product quality issue.

### Listing opportunity

The top three positive themes (variety, effectiveness, zero sugar) are all underrepresented in the current 42-word description. The copy mentions "zero sugar" once but says nothing about the variety-first experience or the functional outcomes customers report. These three phrases alone would materially strengthen the description.

---
*Tools used: `fetch_reviews_full`, `cluster_review_themes` · Surface: Streamlit chat*
