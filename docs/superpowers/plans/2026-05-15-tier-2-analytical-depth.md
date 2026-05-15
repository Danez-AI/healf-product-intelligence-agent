# Healf Product Intelligence Agent — Plan 2: Tier 2 Analytical Depth

> **For agentic workers:** Use `superpowers:subagent-driven-development` to implement task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add analytical depth to the agent — review-theme clustering, category benchmarking, listing quality evaluation, image scoring, cross-field consistency checking, comparison, copy drafting, and HITL enqueueing. All new tools wired into `TOOL_SCHEMAS` and `dispatch_tool`.

**Tier 2 gate:** All 9 tools wired, `pytest` green, agent answers "what should I improve?" with corpus-grounded evidence and a draft rewrite.

**Prerequisite:** Tier 1 complete (25 tests passing, `tier-1-complete` tag set).

---

## Context — What Tier 1 Built

| File | Status |
|------|--------|
| `healf_agent/models.py` | Product, Review, ReviewTheme, EvalReport, RubricScore, ConsistencyFinding, ConsistencyReport, HITLEntry, Comparison |
| `healf_agent/storage.py` | 6 tables: products, reviews, corpus, review_themes, hitl_queue, eval_runs |
| `healf_agent/corpus.py` | parse_sitemap_index, parse_product_sitemap, stratified_sample, build_corpus_text, embed_texts |
| `healf_agent/agent.py` | run_agent_turn, SYSTEM_PROMPT |
| `healf_agent/tools/__init__.py` | TOOL_SCHEMAS (fetch_product, check_field) + dispatch_tool |
| `healf_agent/tools/field.py` | check_field |
| `corpus.sqlite` | 150 products — **all product_type "Unknown"** (see Gotcha G-04) |

**Known issue to fix in Wave 7:** `corpus.sqlite` has all entries as `product_type: Unknown` because Healf JSON-LD has no `category` field. The `knn()` filter must be updated to work without type filtering, or product types must be inferred from URL handles.

---

## Wave 6 — Review-Theme Clustering

**Files:**
- Create: `healf_agent/tools/review_themes.py`
- Create: `tests/test_review_themes.py`
- Modify: `healf_agent/tools/__init__.py` (add schema + dispatch)

### Task 6.1: `cluster_review_themes`

**What it does:** Takes all reviews for a product, embeds them (OpenAI), clusters with HDBSCAN, asks Claude to label each cluster as a theme (positive/negative/neutral), persists to `review_themes` table.

**Spec:**

- [ ] **Step 1: Write `tests/test_review_themes.py`**

```python
from unittest.mock import MagicMock, patch
from datetime import datetime

from healf_agent.models import Review, ReviewTheme
from healf_agent.tools.review_themes import cluster_review_themes


def _make_reviews(n: int, rating: int = 5) -> list[Review]:
    return [
        Review(
            review_id=f"r{i}",
            product_gid="gid://shopify/Product/1",
            author=f"User{i}",
            rating=rating,
            body=f"This product is great sample review number {i}",
            verified=True,
        )
        for i in range(n)
    ]


def test_cluster_review_themes_returns_themes_list(monkeypatch) -> None:
    reviews = _make_reviews(10, rating=5)

    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1] * 128) for _ in range(10)]
    )

    fake_anthropic = MagicMock()
    fake_anthropic.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text='[{"label": "Great taste", "summary": "Users love the taste", "polarity": "positive"}]')]
    )

    themes = cluster_review_themes(
        reviews=reviews,
        product_gid="gid://shopify/Product/1",
        openai_client=fake_openai,
        anthropic_client=fake_anthropic,
        min_cluster_size=2,
    )
    assert isinstance(themes, list)
    assert len(themes) >= 1
    assert all(isinstance(t, ReviewTheme) for t in themes)


def test_cluster_review_themes_returns_empty_for_few_reviews() -> None:
    reviews = _make_reviews(2)
    fake_openai = MagicMock()
    fake_anthropic = MagicMock()
    themes = cluster_review_themes(
        reviews=reviews,
        product_gid="gid://shopify/Product/1",
        openai_client=fake_openai,
        anthropic_client=fake_anthropic,
        min_reviews=5,
    )
    assert themes == []
```

- [ ] **Step 2: Run tests — expect FAIL**

```
python -m uv run pytest tests/test_review_themes.py -v
```

- [ ] **Step 3: Implement `healf_agent/tools/review_themes.py`**

```python
"""cluster_review_themes: embed → cluster → Claude-label review themes."""
from __future__ import annotations

import json
from typing import Any

from healf_agent.corpus import embed_texts
from healf_agent.models import Review, ReviewTheme

_LABEL_PROMPT = """\
You are analysing customer reviews for a health product. Below are review clusters.
For each cluster, return a JSON array of objects with keys:
  "label" (2-5 word theme name),
  "summary" (1 sentence),
  "polarity" ("positive"|"negative"|"neutral")

Clusters:
{clusters}

Return ONLY valid JSON array, no commentary."""


def cluster_review_themes(
    *,
    reviews: list[Review],
    product_gid: str,
    openai_client,
    anthropic_client,
    min_reviews: int = 5,
    min_cluster_size: int = 2,
    model: str = "claude-haiku-4-5-20251001",
) -> list[ReviewTheme]:
    """Embed reviews, cluster with HDBSCAN, label clusters with Claude."""
    if len(reviews) < min_reviews:
        return []

    texts = [f"{r.title or ''} {r.body}".strip() for r in reviews]
    vecs = embed_texts(texts, client=openai_client)

    try:
        import numpy as np
        import hdbscan as hdbscan_lib

        arr = np.array(vecs, dtype="float32")
        clusterer = hdbscan_lib.HDBSCAN(
            min_cluster_size=min_cluster_size,
            metric="euclidean",
        )
        labels = clusterer.fit_predict(arr)
    except Exception:
        # Fallback: single cluster containing all reviews
        labels = [0] * len(reviews)

    # Group reviews by cluster label (-1 = noise, skip)
    clusters: dict[int, list[Review]] = {}
    for review, label in zip(reviews, labels):
        if label == -1:
            continue
        clusters.setdefault(label, []).append(review)

    if not clusters:
        return []

    # Build cluster text for Claude
    cluster_text = "\n\n".join(
        f"Cluster {cid} ({len(revs)} reviews):\n"
        + "\n".join(f"- [{r.rating}★] {r.body[:200]}" for r in revs[:10])
        for cid, revs in clusters.items()
    )

    resp = anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": _LABEL_PROMPT.format(clusters=cluster_text)}],
    )
    raw = resp.content[0].text if resp.content else "[]"

    # Parse Claude's JSON response
    try:
        labelled = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON array from response
        import re
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        labelled = json.loads(m.group(0)) if m else []

    themes: list[ReviewTheme] = []
    for i, (cid, revs) in enumerate(clusters.items()):
        meta = labelled[i] if i < len(labelled) else {}
        total = len(reviews)
        themes.append(ReviewTheme(
            product_gid=product_gid,
            polarity=meta.get("polarity", "neutral"),
            label=meta.get("label", f"Theme {cid}"),
            summary=meta.get("summary", ""),
            review_ids=[r.review_id for r in revs],
            weight=len(revs) / total if total else 0.0,
        ))
    return themes
```

- [ ] **Step 4: Run tests — expect PASS**

```
python -m uv run pytest tests/test_review_themes.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Wire into dispatcher — APPEND to `healf_agent/tools/__init__.py`**

Add to `TOOL_SCHEMAS`:
```python
{
    "name": "cluster_review_themes",
    "description": "Cluster all reviews for the current product into labelled themes (positive/negative/neutral) using embeddings + HDBSCAN + Claude.",
    "input_schema": {
        "type": "object",
        "properties": {
            "polarity_filter": {
                "type": "string",
                "enum": ["positive", "negative", "neutral", "all"],
                "description": "Filter themes by polarity. Default: all.",
            }
        },
        "required": [],
    },
},
```

Add to `dispatch_tool`:
```python
if name == "cluster_review_themes":
    from healf_agent.tools.review_themes import cluster_review_themes
    from healf_agent.storage import Storage
    from pathlib import Path
    import os
    from anthropic import Anthropic
    from openai import OpenAI

    if product is None:
        raise ValueError("cluster_review_themes requires a current product")
    storage = Storage(Path("healf.sqlite"))
    storage.init_schema()
    reviews = storage.get_reviews(product.gid)
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    themes = cluster_review_themes(
        reviews=reviews,
        product_gid=product.gid,
        openai_client=openai_client,
        anthropic_client=anthropic_client,
    )
    storage.upsert_reviews([])  # no-op to keep storage open
    # Persist themes
    for t in themes:
        storage.conn.execute(
            "INSERT INTO review_themes(product_gid, polarity, label, summary, review_ids, weight) VALUES(?,?,?,?,?,?)",
            (t.product_gid, t.polarity, t.label, t.summary,
             ",".join(t.review_ids), t.weight),
        )
    storage.conn.commit()
    polarity_filter = arguments.get("polarity_filter", "all")
    result = [t.model_dump() for t in themes
              if polarity_filter == "all" or t.polarity == polarity_filter]
    return {"themes": result, "total_reviews": len(reviews)}
```

- [ ] **Step 6: Run full suite — expect 27 passed (25 + 2 new)**

```
python -m uv run pytest -v
```

- [ ] **Step 7: Commit**

```
git add healf_agent/tools/review_themes.py tests/test_review_themes.py healf_agent/tools/__init__.py
git commit -m "feat(tools): cluster_review_themes — embed + HDBSCAN + Claude labelling"
```

---

## Wave 7 — Benchmark + Evaluate

**Files:**
- Create: `healf_agent/tools/benchmark.py`
- Create: `healf_agent/tools/evaluate.py`
- Modify: `healf_agent/tools/__init__.py`
- Modify: `tests/test_agent.py` (append)

**Known issue to fix here:** `corpus.sqlite` product_type is all "Unknown". Fix `benchmark_against_category` to fall back to global kNN when type-filtered results are empty.

### Task 7.1: `benchmark_against_category`

**What it does:** kNN over corpus to find 5 similar products; returns their titles + descriptive text as context for Claude to compare against.

- [ ] **Step 1: Append to `tests/test_agent.py`**

```python
from healf_agent.tools.benchmark import benchmark_against_category


def test_benchmark_returns_neighbours(monkeypatch) -> None:
    from healf_agent.storage import Storage
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp()) / "c.sqlite"
    s = Storage(tmp)
    s.init_schema()
    for i in range(3):
        s.upsert_corpus_entry(
            handle=f"prod-{i}",
            product_type="Unknown",
            title=f"Product {i}",
            text=f"Description of product {i}",
            embedding=[0.1 + i * 0.01] * 8,
        )

    fake_openai = MagicMock()
    fake_openai.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1] * 8)]
    )

    result = benchmark_against_category(
        product=_p(),
        storage=s,
        openai_client=fake_openai,
        k=3,
    )
    assert "neighbours" in result
    assert len(result["neighbours"]) <= 3
```

- [ ] **Step 2: Implement `healf_agent/tools/benchmark.py`**

```python
"""benchmark_against_category: kNN corpus retrieval for comparative context."""
from __future__ import annotations

from typing import Any

from healf_agent.corpus import build_corpus_text, embed_texts
from healf_agent.models import Product
from healf_agent.storage import Storage


def benchmark_against_category(
    *,
    product: Product,
    storage: Storage,
    openai_client,
    k: int = 5,
    embed_model: str = "text-embedding-3-small",
) -> dict[str, Any]:
    """Return k nearest corpus neighbours to the given product."""
    query_text = build_corpus_text(
        title=product.title,
        description=product.description,
        claims=product.claims,
    )
    resp = openai_client.embeddings.create(model=embed_model, input=[query_text])
    query_vec = resp.data[0].embedding

    # Try type-filtered first; fall back to global if empty (Gotcha G-04)
    neighbours = storage.knn(product_type=product.product_type, query_vec=query_vec, k=k)
    if not neighbours:
        neighbours = storage.knn(product_type="Unknown", query_vec=query_vec, k=k)

    return {
        "product_handle": product.handle,
        "neighbours": [
            {"handle": n["handle"], "title": n["title"], "excerpt": n["text"][:300]}
            for n in neighbours
            if n["handle"] != product.handle
        ][:k],
    }
```

- [ ] **Step 3: Run new test — expect PASS**

```
python -m uv run pytest tests/test_agent.py::test_benchmark_returns_neighbours -v
```

### Task 7.2: `evaluate_listing_quality`

**What it does:** Claude rubric (5 axes: completeness, differentiation, trust signals, ingredient transparency, image quality hint) grounded in the benchmark neighbours and review themes.

- [ ] **Step 1: Append test to `tests/test_agent.py`**

```python
from healf_agent.tools.evaluate import evaluate_listing_quality


def test_evaluate_listing_quality_returns_eval_report(monkeypatch) -> None:
    fake_anthropic = MagicMock()
    fake_anthropic.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text='''{
  "scores": [
    {"axis": "completeness", "score": 3, "rationale": "Missing serving size"},
    {"axis": "differentiation", "score": 4, "rationale": "Good brand story"}
  ],
  "gaps": ["Add serving size info", "Add ingredient amounts"]
}''')]
    )
    p = _p()
    report = evaluate_listing_quality(
        product=p,
        neighbours=[{"handle": "x", "title": "X", "excerpt": "Great product."}],
        themes=[],
        anthropic_client=fake_anthropic,
    )
    from healf_agent.models import EvalReport
    assert isinstance(report, EvalReport)
    assert report.average() > 0
    assert len(report.gaps) >= 1
```

- [ ] **Step 2: Implement `healf_agent/tools/evaluate.py`**

```python
"""evaluate_listing_quality: Claude rubric grounded in corpus + review themes."""
from __future__ import annotations

import json
import re
from typing import Any

from healf_agent.models import EvalReport, Product, ReviewTheme, RubricScore

_EVAL_PROMPT = """\
You are a product listing quality evaluator for Healf, a UK health & wellness marketplace.

Score this product listing on 5 axes (1=poor, 5=excellent):
1. completeness — ingredients, claims, serving size, usage directions present?
2. differentiation — does it explain why this product vs alternatives?
3. trust_signals — reviews count, rating, certifications mentioned?
4. ingredient_transparency — specific amounts, forms (e.g. "500mg magnesium citrate")?
5. copy_quality — clear, compelling, Healf-voice (premium but approachable)?

PRODUCT:
Title: {title}
Brand: {brand}
Description: {description}
Ingredients: {ingredients}
Claims: {claims}
Rating: {rating_value}/5 ({rating_count} reviews)

COMPARABLE PRODUCTS FROM CORPUS:
{neighbours}

REVIEW THEMES:
{themes}

Return ONLY this JSON (no commentary):
{{
  "scores": [
    {{"axis": "completeness", "score": N, "rationale": "..."}},
    {{"axis": "differentiation", "score": N, "rationale": "..."}},
    {{"axis": "trust_signals", "score": N, "rationale": "..."}},
    {{"axis": "ingredient_transparency", "score": N, "rationale": "..."}},
    {{"axis": "copy_quality", "score": N, "rationale": "..."}}
  ],
  "gaps": ["gap 1", "gap 2", ...]
}}"""


def evaluate_listing_quality(
    *,
    product: Product,
    neighbours: list[dict[str, Any]],
    themes: list[ReviewTheme] | list[dict],
    anthropic_client,
    model: str = "claude-sonnet-4-6",
) -> EvalReport:
    neighbours_text = "\n".join(
        f"- {n['title']}: {n['excerpt']}" for n in neighbours
    ) or "No comparable products found."

    themes_text = "\n".join(
        f"- [{t['polarity'] if isinstance(t, dict) else t.polarity}] "
        f"{t['label'] if isinstance(t, dict) else t.label}: "
        f"{t['summary'] if isinstance(t, dict) else t.summary}"
        for t in themes
    ) or "No review themes available."

    prompt = _EVAL_PROMPT.format(
        title=product.title,
        brand=product.brand,
        description=product.description[:500],
        ingredients=", ".join(product.ingredients) or "not listed",
        claims=", ".join(product.claims) or "not listed",
        rating_value=product.rating_value,
        rating_count=product.rating_count,
        neighbours=neighbours_text,
        themes=themes_text,
    )

    resp = anthropic_client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text if resp.content else "{}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group(0)) if m else {}

    scores = [RubricScore(**s) for s in data.get("scores", [])]
    return EvalReport(
        product_handle=product.handle,
        scores=scores,
        gaps=data.get("gaps", []),
        corpus_references=[],
    )
```

- [ ] **Step 3: Wire both into dispatcher** — add schemas and dispatch cases for `benchmark_against_category` and `evaluate_listing_quality` to `healf_agent/tools/__init__.py`

For `benchmark_against_category` schema:
```python
{
    "name": "benchmark_against_category",
    "description": "Find similar products in the Healf corpus and return comparative context.",
    "input_schema": {"type": "object", "properties": {"k": {"type": "integer", "default": 5}}, "required": []},
},
```

For `evaluate_listing_quality` schema:
```python
{
    "name": "evaluate_listing_quality",
    "description": "Score the current product listing on 5 quality axes using Claude, grounded in corpus neighbours and review themes.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
},
```

Dispatch cases use `Storage("healf.sqlite")`, call `benchmark_against_category` then `evaluate_listing_quality`, return `report.model_dump(mode="json")`.

- [ ] **Step 4: Run full suite — expect 29 passed**

```
python -m uv run pytest -v
```

- [ ] **Step 5: Commit**

```
git add healf_agent/tools/benchmark.py healf_agent/tools/evaluate.py healf_agent/tools/__init__.py tests/test_agent.py
git commit -m "feat(tools): benchmark_against_category + evaluate_listing_quality"
```

---

## Wave 8 — Vision + Consistency

**Files:**
- Create: `healf_agent/tools/vision.py`
- Create: `healf_agent/tools/consistency.py`
- Modify: `healf_agent/tools/__init__.py`
- Modify: `tests/test_agent.py`

### Task 8.1: `score_images`

**What it does:** Sends product images to Gemini 2.5 Flash with a rubric (clarity, lifestyle vs pack-shot ratio, label legibility, alt-text match). Returns scores per image.

- [ ] **Step 1: Append test to `tests/test_agent.py`**

```python
from healf_agent.tools.vision import score_images


def test_score_images_returns_scores(monkeypatch) -> None:
    fake_gemini = MagicMock()
    fake_gemini.models.generate_content.return_value = MagicMock(
        text='[{"url": "https://cdn.shopify.com/x.jpg", "clarity": 4, "lifestyle": false, "label_legible": true, "overall": 4, "notes": "Clean pack shot"}]'
    )
    p = _p()
    result = score_images(product=p, gemini_client=fake_gemini)
    assert "image_scores" in result
```

- [ ] **Step 2: Implement `healf_agent/tools/vision.py`**

```python
"""score_images: Gemini Vision rubric for product images."""
from __future__ import annotations

import json
import re
from typing import Any

from healf_agent.models import Product

_VISION_PROMPT = """\
Score these product images for a health ecommerce listing.
For each image URL, return a JSON array of objects with:
  "url", "clarity" (1-5), "lifestyle" (bool — is it a lifestyle/in-use shot?),
  "label_legible" (bool — can ingredient/nutrition label be read?),
  "overall" (1-5), "notes" (1 sentence)

Image URLs:
{urls}

Return ONLY valid JSON array."""


def score_images(
    *,
    product: Product,
    gemini_client,
    model: str = "gemini-2.5-flash",
) -> dict[str, Any]:
    if not product.images:
        return {"image_scores": [], "note": "no images found"}

    urls = [str(img.url) for img in product.images[:8]]
    prompt = _VISION_PROMPT.format(urls="\n".join(urls))

    resp = gemini_client.models.generate_content(
        model=model,
        contents=prompt,
    )
    raw = resp.text or "[]"

    try:
        scores = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        scores = json.loads(m.group(0)) if m else []

    return {
        "image_scores": scores,
        "image_count": len(urls),
        "has_lifestyle": any(s.get("lifestyle") for s in scores),
        "avg_clarity": (
            sum(s.get("clarity", 0) for s in scores) / len(scores) if scores else 0
        ),
    }
```

### Task 8.2: `check_consistency`

**What it does:** Cross-validates ingredients vs description vs claims vs review themes. Flags mismatches as `ConsistencyFinding` objects.

- [ ] **Step 1: Append test to `tests/test_agent.py`**

```python
from healf_agent.tools.consistency import check_consistency


def test_check_consistency_flags_unsupported_claim(monkeypatch) -> None:
    fake_anthropic = MagicMock()
    fake_anthropic.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text='[{"kind": "claim_unsupported", "detail": "zero sugar claim not in ingredients", "evidence": "sugar-free not listed"}]')]
    )
    p = _p(claims=["zero sugar", "keto friendly"])
    from healf_agent.models import ConsistencyReport
    report = check_consistency(product=p, themes=[], anthropic_client=fake_anthropic)
    assert isinstance(report, ConsistencyReport)
```

- [ ] **Step 2: Implement `healf_agent/tools/consistency.py`**

```python
"""check_consistency: cross-validate ingredients, claims, description, review themes."""
from __future__ import annotations

import json
import re
from typing import Any

from healf_agent.models import ConsistencyFinding, ConsistencyReport, Product, ReviewTheme

_CONSISTENCY_PROMPT = """\
You are auditing a health product listing for internal consistency.

PRODUCT:
Title: {title}
Description: {description}
Ingredients: {ingredients}
Claims: {claims}

REVIEW THEMES (what customers actually say):
{themes}

Find inconsistencies. For each, return a JSON array of objects with:
  "kind": one of ["ingredient_mismatch", "claim_unsupported", "image_underrepresented", "label_ocr_conflict"]
  "detail": what the inconsistency is
  "evidence": the specific text that conflicts

Return [] if no inconsistencies. Return ONLY valid JSON array."""


def check_consistency(
    *,
    product: Product,
    themes: list[ReviewTheme] | list[dict],
    anthropic_client,
    model: str = "claude-sonnet-4-6",
) -> ConsistencyReport:
    themes_text = "\n".join(
        f"- [{t['polarity'] if isinstance(t, dict) else t.polarity}] "
        f"{t['label'] if isinstance(t, dict) else t.label}: "
        f"{t['summary'] if isinstance(t, dict) else t.summary}"
        for t in themes
    ) or "No review themes available."

    prompt = _CONSISTENCY_PROMPT.format(
        title=product.title,
        description=product.description[:500],
        ingredients=", ".join(product.ingredients) or "not listed",
        claims=", ".join(product.claims) or "not listed",
        themes=themes_text,
    )

    resp = anthropic_client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.content[0].text if resp.content else "[]"

    try:
        findings_raw = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        findings_raw = json.loads(m.group(0)) if m else []

    findings = [ConsistencyFinding(**f) for f in findings_raw if isinstance(f, dict)]
    return ConsistencyReport(product_handle=product.handle, findings=findings)
```

- [ ] **Step 3: Wire both into dispatcher + add schemas**

For `score_images`:
```python
{
    "name": "score_images",
    "description": "Score product images using Gemini Vision rubric (clarity, lifestyle shots, label legibility).",
    "input_schema": {"type": "object", "properties": {}, "required": []},
},
```

For `check_consistency`:
```python
{
    "name": "check_consistency",
    "description": "Cross-validate the product's ingredients, claims, description, and review themes for inconsistencies.",
    "input_schema": {"type": "object", "properties": {}, "required": []},
},
```

- [ ] **Step 4: Run full suite — expect 31 passed**

```
python -m uv run pytest -v
```

- [ ] **Step 5: Commit**

```
git add healf_agent/tools/vision.py healf_agent/tools/consistency.py healf_agent/tools/__init__.py tests/test_agent.py
git commit -m "feat(tools): score_images (Gemini Vision) + check_consistency"
```

---

## Wave 9 — Compare + Act

**Files:**
- Create: `healf_agent/tools/compare.py`
- Create: `healf_agent/tools/act.py`
- Modify: `healf_agent/tools/__init__.py`
- Modify: `tests/test_agent.py`

### Task 9.1: `compare_products`

**What it does:** Takes 2–4 Healf product URLs, fetches + parses each, returns a side-by-side comparison table (price, rating, ingredients count, claims count, image count, description length).

- [ ] **Step 1: Append test to `tests/test_agent.py`**

```python
from healf_agent.tools.compare import compare_products


def test_compare_products_returns_rows(monkeypatch) -> None:
    p1 = _p(handle="a", title="Product A", price_gbp=10.0, rating_value=4.5, rating_count=50)
    p2 = _p(handle="b", title="Product B", price_gbp=15.0, rating_value=4.0, rating_count=20)
    result = compare_products(products=[p1, p2])
    from healf_agent.models import Comparison
    assert isinstance(result, Comparison)
    assert len(result.rows) >= 1
    assert len(result.handles) == 2
```

- [ ] **Step 2: Implement `healf_agent/tools/compare.py`**

```python
"""compare_products: side-by-side comparison of multiple Healf products."""
from __future__ import annotations

from healf_agent.models import Comparison, Product


def compare_products(products: list[Product]) -> Comparison:
    """Return a structured side-by-side comparison."""
    if len(products) < 2:
        raise ValueError("need at least 2 products to compare")

    axes = [
        ("price_gbp", lambda p: f"£{p.price_gbp:.2f}"),
        ("rating", lambda p: f"{p.rating_value}/5 ({p.rating_count} reviews)" if p.rating_value else "N/A"),
        ("ingredients_count", lambda p: str(len(p.ingredients))),
        ("claims_count", lambda p: str(len(p.claims))),
        ("image_count", lambda p: str(len(p.images))),
        ("description_length", lambda p: str(len(p.description))),
    ]

    rows = [
        {"axis": axis, **{p.handle: fn(p) for p in products}}
        for axis, fn in axes
    ]

    winner_price = min(products, key=lambda p: p.price_gbp).handle
    winner_rating = max(products, key=lambda p: p.rating_value or 0).handle
    summary = (
        f"Compared {len(products)} products. "
        f"Best price: {winner_price}. Best rating: {winner_rating}."
    )

    return Comparison(
        handles=[p.handle for p in products],
        rows=rows,
        summary=summary,
    )
```

### Task 9.2: `draft_rewrite` + `enqueue_hitl`

**What it does:** `draft_rewrite` — Claude writes improved description in Healf voice, using the eval gaps as guidance. `enqueue_hitl` — persists the draft to `hitl_queue` table.

- [ ] **Step 1: Append tests to `tests/test_agent.py`**

```python
from healf_agent.tools.act import draft_rewrite, enqueue_hitl


def test_draft_rewrite_returns_string(monkeypatch) -> None:
    fake_anthropic = MagicMock()
    fake_anthropic.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text="Improved product description here.")]
    )
    p = _p()
    result = draft_rewrite(
        product=p,
        gaps=["add serving size", "mention electrolyte amounts"],
        anthropic_client=fake_anthropic,
    )
    assert isinstance(result, str)
    assert len(result) > 0


def test_enqueue_hitl_persists_to_storage(monkeypatch) -> None:
    import tempfile
    from pathlib import Path
    from healf_agent.storage import Storage

    tmp = Path(tempfile.mkdtemp()) / "test.sqlite"
    s = Storage(tmp)
    s.init_schema()
    p = _p()
    entry_id = enqueue_hitl(
        product=p,
        drafted_description="Better description.",
        gap_summary="Missing serving size.",
        storage=s,
    )
    assert isinstance(entry_id, int)
    row = s.conn.execute("SELECT * FROM hitl_queue WHERE id=?", (entry_id,)).fetchone()
    assert row is not None
```

- [ ] **Step 2: Implement `healf_agent/tools/act.py`**

```python
"""act.py: draft_rewrite and enqueue_hitl action tools."""
from __future__ import annotations

import time
from typing import Any

from healf_agent.models import HITLEntry, Product
from healf_agent.storage import Storage

_REWRITE_PROMPT = """\
You are a copywriter for Healf, a UK premium health & wellness marketplace.
Healf voice: confident, evidence-led, warm but not preachy. British English. No hype.

Rewrite the product description for:
Product: {title} by {brand}
Current description: {description}

Gaps to address:
{gaps}

Write a new description (150-250 words). Return ONLY the description text."""


def draft_rewrite(
    *,
    product: Product,
    gaps: list[str],
    anthropic_client,
    model: str = "claude-sonnet-4-6",
) -> str:
    prompt = _REWRITE_PROMPT.format(
        title=product.title,
        brand=product.brand,
        description=product.description[:600],
        gaps="\n".join(f"- {g}" for g in gaps),
    )
    resp = anthropic_client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip() if resp.content else ""


def enqueue_hitl(
    *,
    product: Product,
    drafted_description: str,
    gap_summary: str,
    storage: Storage,
) -> int:
    """Persist a drafted rewrite to the HITL queue. Returns the new row id."""
    cursor = storage.conn.execute(
        "INSERT INTO hitl_queue(product_handle, original_description, drafted_description, gap_summary, status, created_at) "
        "VALUES(?,?,?,?,?,?)",
        (product.handle, product.description, drafted_description, gap_summary, "pending", time.time()),
    )
    storage.conn.commit()
    return cursor.lastrowid
```

- [ ] **Step 3: Wire all Wave 9 tools into dispatcher + add schemas**

```python
# compare_products schema
{
    "name": "compare_products",
    "description": "Compare 2-4 Healf product URLs side-by-side on price, rating, ingredients, images.",
    "input_schema": {
        "type": "object",
        "properties": {"urls": {"type": "array", "items": {"type": "string"}}},
        "required": ["urls"],
    },
},
# draft_rewrite schema
{
    "name": "draft_rewrite",
    "description": "Draft an improved product description in Healf voice, addressing identified gaps.",
    "input_schema": {
        "type": "object",
        "properties": {"gaps": {"type": "array", "items": {"type": "string"}}},
        "required": ["gaps"],
    },
},
# enqueue_hitl schema
{
    "name": "enqueue_hitl",
    "description": "Send a drafted rewrite to the human-in-the-loop approval queue.",
    "input_schema": {
        "type": "object",
        "properties": {
            "drafted_description": {"type": "string"},
            "gap_summary": {"type": "string"},
        },
        "required": ["drafted_description", "gap_summary"],
    },
},
```

- [ ] **Step 4: Run full suite — expect 35 passed**

```
python -m uv run pytest -v
```

- [ ] **Step 5: Commit**

```
git add healf_agent/tools/compare.py healf_agent/tools/act.py healf_agent/tools/__init__.py tests/test_agent.py
git commit -m "feat(tools): compare_products + draft_rewrite + enqueue_hitl"
```

---

## Wave 9.5 — Tier 2 Gate

- [ ] **Step 1: Full test sweep**

```
python -m uv run pytest -v
```
Expected: 35 passed (all Tier 1 + all Tier 2 tools).

- [ ] **Step 2: Manual verification — ask the agent "what should I improve about this product?"**

Launch Streamlit, fetch LMNT, ask the question. Expected tool trace:
1. `benchmark_against_category` — finds corpus neighbours
2. `evaluate_listing_quality` — returns scores + gaps
3. `draft_rewrite` — returns improved copy

- [ ] **Step 3: Tag**

```
git tag tier-2-complete
```

---

## Known Issues / Deferred Fixes

| Issue | When to fix | File |
|-------|------------|------|
| All corpus entries product_type "Unknown" | Wave 7 kNN fallback (done above) | benchmark.py |
| Ingredients not extracted for LMNT | Wave 8 OCR via Gemini or manual entry | vision.py |
| Streamlit doesn't persist review themes across reruns | Tier 3 HITL page | pages/hitl.py |
| `fetch_reviews_full` not called by agent for new products | Wave 6 dispatcher | tools/__init__.py |
