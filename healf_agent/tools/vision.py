"""score_images: Gemini Vision rubric for product images."""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from healf_agent.models import Product

MAX_SCORED_IMAGES = 8

_VISION_PROMPT = """\
Score these {n} product images for a health ecommerce listing.
For each image (in the order provided), return a JSON array of objects with:
  "url", "clarity" (1-5), "lifestyle" (bool — is it a lifestyle/in-use shot?),
  "label_legible" (bool — can ingredient/nutrition label be read?),
  "overall" (1-5), "notes" (1 sentence)

Return ONLY valid JSON array."""


def _fetch_image_bytes(url: str, timeout: float = 10.0) -> bytes | None:
    """Fetch image bytes from URL. Returns None on failure."""
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            return resp.content
    except Exception:
        return None


def score_images(
    *,
    product: Product,
    gemini_client,
    model: str = "gemini-2.5-flash",
) -> dict[str, Any]:
    if not product.images:
        return {"image_scores": [], "note": "no images found"}

    from google.genai import types

    urls = [str(img.url) for img in product.images[:MAX_SCORED_IMAGES]]

    # Build multimodal content: text prompt + image parts
    image_parts = []
    fetched_urls = []
    for url in urls:
        data = _fetch_image_bytes(url)
        if data is None:
            continue
        # Detect mime type from URL extension; default to jpeg
        mime = "image/jpeg"
        if url.lower().endswith(".png"):
            mime = "image/png"
        elif url.lower().endswith(".webp"):
            mime = "image/webp"
        image_parts.append(types.Part.from_bytes(data=data, mime_type=mime))
        fetched_urls.append(url)

    if not image_parts:
        return {"image_scores": [], "note": "could not fetch any images"}

    prompt_text = _VISION_PROMPT.format(n=len(image_parts))
    contents = [types.Part.from_text(text=prompt_text)] + image_parts

    resp = gemini_client.models.generate_content(
        model=model,
        contents=contents,
    )
    raw = resp.text or "[]"

    try:
        scores = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        scores = json.loads(m.group(0)) if m else []

    # Backfill urls if Gemini omitted them
    for i, score in enumerate(scores):
        if "url" not in score and i < len(fetched_urls):
            score["url"] = fetched_urls[i]

    return {
        "image_scores": scores,
        "image_count": len(image_parts),
        "has_lifestyle": any(s.get("lifestyle") for s in scores),
        "avg_clarity": (
            sum(s.get("clarity", 0) for s in scores) / len(scores) if scores else 0
        ),
    }
