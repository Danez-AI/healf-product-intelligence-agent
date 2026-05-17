"""Corpus: site-wide standards retrieval layer."""
from __future__ import annotations

import math
import random
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from typing import Iterable

NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def parse_sitemap_index(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [el.text.strip() for el in root.iterfind(f".//{NS}sitemap/{NS}loc") if el.text]


def parse_product_sitemap(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    return [el.text.strip() for el in root.iterfind(f".//{NS}url/{NS}loc") if el.text]


def stratified_sample(
    pool: Mapping[str, list[str]],
    *,
    target_total: int,
    min_per_bucket: int = 3,
    seed: int = 0,
) -> dict[str, list[str]]:
    """Sample roughly `target_total` items across buckets, with a floor per bucket."""
    rng = random.Random(seed)
    result: dict[str, list[str]] = {}
    remaining_budget = target_total
    for bucket, items in pool.items():
        take = min(min_per_bucket, len(items))
        picked = rng.sample(items, take) if take < len(items) else list(items)
        result[bucket] = picked
        remaining_budget -= take
    if remaining_budget <= 0:
        return result
    total_remaining = sum(max(0, len(items) - len(result[b])) for b, items in pool.items())
    if total_remaining == 0:
        return result
    for bucket, items in pool.items():
        already = result[bucket]
        leftover = [u for u in items if u not in already]
        if not leftover:
            continue
        share = math.floor(remaining_budget * (len(leftover) / total_remaining))
        if share <= 0:
            continue
        take = min(share, len(leftover))
        result[bucket].extend(rng.sample(leftover, take))
    return result


def build_corpus_text(*, title: str, description: str, claims: Iterable[str]) -> str:
    """Concatenate product title, description, and claims into a single corpus text."""
    parts = [title, description, "; ".join(claims)]
    return "\n".join(p for p in parts if p)


def embed_texts(
    texts: list[str],
    *,
    client,
    model: str = "text-embedding-3-small",
    batch_size: int = 2000,
) -> list[list[float]]:
    """Embed a list of texts using OpenAI embeddings API.

    Chunks into batches of `batch_size` (OpenAI limit is 2048 per call).
    """
    if not texts:
        return []
    results: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        resp = client.embeddings.create(model=model, input=chunk)
        results.extend(d.embedding for d in resp.data)
    return results
