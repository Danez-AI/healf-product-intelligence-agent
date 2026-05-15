"""Build corpus.sqlite by sampling Healf's product sitemap.

Run: `python -m uv run python scripts/build_corpus.py --target 150 --out corpus.sqlite`
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=150)
    ap.add_argument("--out", default="corpus.sqlite")
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
    print(f"Found {len(product_urls)} product URLs")

    # Bucket by product_type
    print("Bucketing products by type (sampling up to 3x target to classify)...")
    buckets: dict[str, list[str]] = defaultdict(list)
    sample_pool = product_urls[: args.target * 3]
    for i, url in enumerate(sample_pool):
        try:
            html = fetch_product_page(url)
            p = parse_product(html, url=url)
            buckets[p.product_type].append(url)
            if i % 10 == 0:
                print(f"  classified {i}/{len(sample_pool)} ...")
        except Exception as exc:
            print(f"  skip {url}: {exc}")
        time.sleep(0.2)  # politeness

    print(f"Buckets: { {k: len(v) for k, v in buckets.items()} }")
    sample = stratified_sample(buckets, target_total=args.target)
    print(f"Sampled {sum(len(v) for v in sample.values())} products across {len(sample)} types")

    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    texts: list[str] = []
    rows: list[tuple[str, str, str, str]] = []
    for product_type, urls in sample.items():
        for url in urls:
            try:
                html = fetch_product_page(url)
                p = parse_product(html, url=url)
            except Exception as exc:
                print(f"  skip {url}: {exc}")
                continue
            text = build_corpus_text(
                title=p.title, description=p.description, claims=p.claims
            )
            rows.append((p.handle, product_type, p.title, text))
            texts.append(text)
            time.sleep(0.2)

    print(f"Embedding {len(texts)} texts via OpenAI...")
    vecs = embed_texts(texts, client=openai_client)
    for (handle, product_type, title, text), vec in zip(rows, vecs):
        storage.upsert_corpus_entry(
            handle=handle,
            product_type=product_type,
            title=title,
            text=text,
            embedding=vec,
        )
    print(f"corpus built: {len(rows)} entries across {len(sample)} buckets -> {args.out}")


if __name__ == "__main__":
    main()
