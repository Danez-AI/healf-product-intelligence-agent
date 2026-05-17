"""Build corpus.sqlite by ingesting Healf's full product catalog.

Run:
    python -m uv run python scripts/build_corpus.py --out corpus.sqlite

Default target 10000 embeds the full classifiable catalog (~6078 of 6716 sitemap URLs).
Full build takes ~50-70 min depending on network speed. Use --max-concurrency to tune.
Use --target <N> (e.g. 150) for a quick test build using stratified sampling.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from healf_agent.corpus import (
    build_corpus_text,
    embed_texts,
    parse_product_sitemap,
    parse_sitemap_index,
    stratified_sample,
)
from healf_agent.storage import Storage
from healf_agent.tools.ingest import parse_product
from healf_agent.tools.navigate import fetch_product_page

# Accumulates every dropped URL for the sidecar audit log.
_skipped: list[dict] = []


def _classify(url: str) -> tuple[str, str, list[str]] | None:
    """Return (product_type, url, collections) or None on failure (logged to _skipped)."""
    try:
        html = fetch_product_page(url)
        p = parse_product(html, url=url)
        return (p.product_type, url, p.collections)
    except Exception as exc:
        print(f"  skip {url}: {exc}")
        _skipped.append({"url": url, "phase": "classify", "reason": str(exc)})
        return None


def _fetch_full(url: str) -> tuple[str, object] | None:
    """Return (url, Product) or None on failure (logged to _skipped)."""
    try:
        html = fetch_product_page(url)
        p = parse_product(html, url=url)
        return (url, p)
    except Exception as exc:
        print(f"  skip {url}: {exc}")
        _skipped.append({"url": url, "phase": "fetch", "reason": str(exc)})
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=10000,
                    help="Max products in corpus. Default 10000 embeds the full catalog. "
                         "Use a small value (e.g. 150) for a fast test run with stratified sampling.")
    ap.add_argument("--out", default="corpus.sqlite")
    ap.add_argument("--max-concurrency", type=int, default=4,
                    help="Parallel fetch workers. Keep ≤4 to stay polite.")
    args = ap.parse_args()

    storage = Storage(args.out)
    storage.init_schema()

    # Always start from a clean slate so stale rows never persist (G-40, G-44).
    deleted = storage.conn.execute("DELETE FROM corpus").rowcount
    storage.conn.commit()
    print(f"Cleared {deleted} stale corpus rows")

    print("Fetching sitemap index...")
    with httpx.Client(timeout=30) as client:
        idx = client.get("https://healf.com/sitemap.xml").text
        products_sitemap_url = next(
            (u for u in parse_sitemap_index(idx) if "sitemap-products" in u), None
        )
        if not products_sitemap_url:
            raise SystemExit("could not find products sitemap")
        print(f"Products sitemap: {products_sitemap_url}")
        product_urls = parse_product_sitemap(client.get(products_sitemap_url).text)
    print(f"Found {len(product_urls)} product URLs in sitemap")

    # Classify all URLs to build type buckets with collection info.
    print(f"Classifying all {len(product_urls)} products (concurrency={args.max_concurrency})...")
    buckets: dict[str, list[str]] = defaultdict(list)
    url_collections: dict[str, list[str]] = {}

    with ThreadPoolExecutor(max_workers=args.max_concurrency) as pool:
        futures = {pool.submit(_classify, url): url for url in product_urls}
        done = 0
        for fut in as_completed(futures):
            done += 1
            result = fut.result()
            if result is not None:
                product_type, url, collections = result
                buckets[product_type].append(url)
                url_collections[url] = collections
            if done % 50 == 0:
                print(f"  classified {done}/{len(product_urls)} ...")
            time.sleep(0.05)  # gentle inter-task delay

    print(f"Buckets: { {k: len(v) for k, v in buckets.items()} }")

    # Use the full classified set when target covers it; fall back to stratified
    # sampling only for small explicit targets (test runs, quota-constrained rebuilds).
    total_classified = sum(len(v) for v in buckets.values())
    if args.target >= total_classified:
        sample = dict(buckets)
        print(f"Target ({args.target}) >= classified ({total_classified}) — embedding full catalog")
    else:
        sample = stratified_sample(buckets, target_total=args.target)
        sampled_handles = {u for urls in sample.values() for u in urls}
        for bucket, urls in buckets.items():
            for url in urls:
                if url not in sampled_handles:
                    _skipped.append({"url": url, "phase": "sample", "reason": f"sampling: bucket {bucket}"})

    sampled_total = sum(len(v) for v in sample.values())
    print(f"Embedding {sampled_total} products across {len(sample)} types")

    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Second pass: full product fetch for selected URLs.
    print(f"Fetching full product data for {sampled_total} products...")
    all_urls = [url for urls in sample.values() for url in urls]

    texts: list[str] = []
    rows: list[tuple[str, str, str, str, list[str]]] = []

    with ThreadPoolExecutor(max_workers=args.max_concurrency) as pool:
        futures = {pool.submit(_fetch_full, url): url for url in all_urls}
        done = 0
        for fut in as_completed(futures):
            done += 1
            result = fut.result()
            if result is not None:
                url, p = result
                text = build_corpus_text(
                    title=p.title, description=p.description, claims=p.claims
                )
                rows.append((p.handle, p.product_type, p.title, text, p.collections))
                texts.append(text)
            if done % 50 == 0:
                print(f"  fetched {done}/{sampled_total} ...")
            time.sleep(0.05)

    print(f"Embedding {len(texts)} texts via OpenAI...")
    vecs = embed_texts(texts, client=openai_client)
    for (handle, product_type, title, text, collections), vec in zip(rows, vecs):
        storage.upsert_corpus_entry(
            handle=handle,
            product_type=product_type,
            title=title,
            text=text,
            embedding=vec,
            collections=collections,
        )
    print(f"corpus built: {len(rows)} entries across {len(sample)} buckets -> {args.out}")

    # Write audit log of every URL that didn't make it into the corpus.
    skipped_path = Path(args.out).with_name("corpus_skipped.jsonl")
    with skipped_path.open("w", encoding="utf-8") as fh:
        for entry in _skipped:
            fh.write(json.dumps(entry) + "\n")
    print(f"Audit log: {len(_skipped)} skipped URLs -> {skipped_path}")


if __name__ == "__main__":
    main()
