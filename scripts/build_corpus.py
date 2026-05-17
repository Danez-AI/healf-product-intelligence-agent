"""Build corpus.sqlite by ingesting Healf's full product catalog.

Run:
    python -m uv run python scripts/build_corpus.py --out corpus.sqlite

Default target is 1500 (covers the full catalog; stratified sampling is a safety net).
Full build takes ~20-30 min depending on network speed. Use --max-concurrency to tune.
"""
from __future__ import annotations

import argparse
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


def _classify(url: str) -> tuple[str, str, list[str]] | None:
    """Return (product_type, url, collections) or None on failure."""
    try:
        html = fetch_product_page(url)
        p = parse_product(html, url=url)
        return (p.product_type, url, p.collections)
    except Exception as exc:
        print(f"  skip {url}: {exc}")
        return None


def _fetch_full(url: str) -> tuple[str, object] | None:
    """Return (url, Product) or None on failure."""
    try:
        html = fetch_product_page(url)
        p = parse_product(html, url=url)
        return (url, p)
    except Exception as exc:
        print(f"  skip {url}: {exc}")
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1500,
                    help="Max products in corpus. Default 1500 covers the full catalog.")
    ap.add_argument("--out", default="corpus.sqlite")
    ap.add_argument("--max-concurrency", type=int, default=4,
                    help="Parallel fetch workers. Keep ≤4 to stay polite.")
    args = ap.parse_args()

    storage = Storage(args.out)
    storage.init_schema()

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

    # Classify all URLs (no sample cap) to build type buckets with collection info
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
    sample = stratified_sample(buckets, target_total=args.target)
    sampled_total = sum(len(v) for v in sample.values())
    print(f"Sampled {sampled_total} products across {len(sample)} types")

    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Second pass: full product fetch for sampled URLs
    print(f"Fetching full product data for {sampled_total} sampled products...")
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


if __name__ == "__main__":
    main()
