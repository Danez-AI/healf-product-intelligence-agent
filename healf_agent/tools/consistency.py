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
