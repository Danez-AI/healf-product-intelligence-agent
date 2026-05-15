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
