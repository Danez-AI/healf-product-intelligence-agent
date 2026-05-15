"""cluster_review_themes: embed → cluster → Claude-label review themes."""
from __future__ import annotations

import json
import re
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
    openai_client: Any,
    anthropic_client: Any,
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
        labels = list(clusterer.fit_predict(arr))
    except Exception:
        labels = None

    # If clustering failed or all points are noise (-1), fall back to single cluster
    if labels is None or all(l == -1 for l in labels):
        labels = [0] * len(reviews)

    # Group reviews by cluster label (-1 = noise, skip)
    clusters: dict[int, list[Review]] = {}
    for review, label in zip(reviews, labels):
        if label == -1:
            continue
        clusters.setdefault(int(label), []).append(review)

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
