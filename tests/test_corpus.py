import httpx
import respx

from healf_agent.corpus import (
    parse_sitemap_index,
    parse_product_sitemap,
    stratified_sample,
)


SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://healf.com/sitemap-products.xml</loc></sitemap>
  <sitemap><loc>https://healf.com/sitemap-collections.xml</loc></sitemap>
</sitemapindex>"""

PRODUCT_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://healf.com/en-uk/products/a</loc></url>
  <url><loc>https://healf.com/en-uk/products/b</loc></url>
  <url><loc>https://healf.com/en-uk/products/c</loc></url>
</urlset>"""


def test_parse_sitemap_index_returns_sub_sitemaps() -> None:
    subs = parse_sitemap_index(SITEMAP_INDEX)
    assert "https://healf.com/sitemap-products.xml" in subs


def test_parse_product_sitemap_returns_urls() -> None:
    urls = parse_product_sitemap(PRODUCT_SITEMAP)
    assert urls == [
        "https://healf.com/en-uk/products/a",
        "https://healf.com/en-uk/products/b",
        "https://healf.com/en-uk/products/c",
    ]


def test_stratified_sample_returns_balanced_buckets() -> None:
    pool = {
        "Electrolytes": [f"https://x/{i}" for i in range(20)],
        "Supplements": [f"https://y/{i}" for i in range(50)],
        "Skincare": [f"https://z/{i}" for i in range(5)],
    }
    sample = stratified_sample(pool, target_total=30, min_per_bucket=3, seed=0)
    assert sum(len(v) for v in sample.values()) <= 30
    assert len(sample["Skincare"]) >= 3
    assert len(sample["Electrolytes"]) >= 3
    assert len(sample["Supplements"]) >= 3
