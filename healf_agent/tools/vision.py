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
