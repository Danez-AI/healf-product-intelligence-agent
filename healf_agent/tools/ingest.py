"""Ingest capability: parse PDP HTML into a Product."""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from selectolax.parser import HTMLParser

from healf_agent.models import Image, Product

_GID_RE = re.compile(r"gid://shopify/Product/\d+")
_HANDLE_RE = re.compile(r"/products/([^/?#]+)")
_KNOWN_CURRENCIES = {"GBP", "USD", "EUR"}


def extract_json_ld(html: str) -> list[dict]:
    """Return all JSON-LD blocks parsed as dicts."""
    tree = HTMLParser(html)
    blocks: list[dict] = []
    for node in tree.css('script[type="application/ld+json"]'):
        text = node.text() or ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            blocks.extend(d for d in data if isinstance(d, dict))
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                blocks.extend(d for d in data["@graph"] if isinstance(d, dict))
            else:
                blocks.append(data)
    return blocks


def extract_rsc_flight(html: str) -> str:
    """Return concatenated text of all RSC flight chunks."""
    parts = re.findall(r'self\.__next_f\.push\(\[\d+,\s*"((?:[^"\\]|\\.)*)"\]\)', html)
    return "".join(parts).encode("utf-8", "ignore").decode("unicode_escape", "ignore")


def _first_product_block(blocks: list[dict]) -> dict:
    for b in blocks:
        if b.get("@type") == "Product":
            return b
    raise ValueError("no Product JSON-LD found")


def _handle_from_url(url: str) -> str:
    m = _HANDLE_RE.search(urlparse(url).path)
    if not m:
        raise ValueError(f"cannot parse handle from {url}")
    return m.group(1)


def _gid_from_html(html: str, fallback: str) -> str:
    m = _GID_RE.search(html)
    return m.group(0) if m else fallback


def _images_from_block(block: dict) -> list[Image]:
    raw = block.get("image") or []
    if isinstance(raw, str):
        raw = [raw]
    return [Image(url=u) for u in raw if isinstance(u, str)]


def parse_product(html: str, *, url: str) -> Product:
    blocks = extract_json_ld(html)
    pblock = _first_product_block(blocks)
    handle = _handle_from_url(url)
    offers = pblock.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    rating = pblock.get("aggregateRating") or {}
    price_raw = offers.get("price")
    try:
        price_gbp = float(price_raw) if price_raw is not None else 0.0
    except (TypeError, ValueError):
        price_gbp = 0.0
    brand_raw = pblock.get("brand")
    brand = brand_raw.get("name") if isinstance(brand_raw, dict) else (brand_raw or "Unknown")
    currency_raw = (offers.get("priceCurrency") or "GBP").upper()
    currency = currency_raw if currency_raw in _KNOWN_CURRENCIES else "GBP"
    return Product(
        url=url,
        handle=handle,
        title=pblock.get("name") or handle,
        brand=brand,
        product_type=pblock.get("category") or "Unknown",
        description=pblock.get("description") or "",
        price_gbp=price_gbp,
        currency=currency,
        sku=pblock.get("sku") or pblock.get("mpn") or handle,
        gid=_gid_from_html(html, fallback=f"gid://shopify/Product/{pblock.get('productID', '0')}"),
        images=_images_from_block(pblock),
        ingredients=[],
        claims=[],
        rating_value=float(rating["ratingValue"]) if rating.get("ratingValue") else None,
        rating_count=int(rating["reviewCount"]) if rating.get("reviewCount") else None,
        raw_jsonld=pblock,
    )


_METAFIELD_RE = re.compile(
    r'"(?P<key>(?:ingredients?|claims?|benefits?|how_to_use|directions?|metafield))"\s*:\s*(?P<val>"(?:[^"\\]|\\.)*"|\[[^\]]*\])',
    re.IGNORECASE,
)


def extract_metafields(html: str) -> dict[str, object]:
    """Pull ingredient/claim-like metafields from the RSC flight payload."""
    flight = extract_rsc_flight(html)
    if not flight:
        return {}
    out: dict[str, object] = {}
    for m in _METAFIELD_RE.finditer(flight):
        key = m.group("key").lower().rstrip("s")
        raw = m.group("val")
        try:
            val = json.loads(raw)
        except json.JSONDecodeError:
            continue
        out.setdefault(key, val)
    return out
