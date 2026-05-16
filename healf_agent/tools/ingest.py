"""Ingest capability: parse PDP HTML into a Product."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Any
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


_VARIANT_BASE_IMAGES_RE = re.compile(
    r'"key"\s*:\s*"variant_base_images"\s*,\s*"value"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"'
)
_CDN_IMG_DIRECT_RE = re.compile(
    r'https://cdn\.shopify\.com/s/files/[^"\\]+\.(?:png|jpe?g|webp)',
    re.IGNORECASE,
)
_SHOPIFY_IMG_RE = re.compile(
    r'https://(?:cdn\.shopify\.com/s/files|f\d+\.backblazeb2\.com)/[^\s"\\]+\.(?:png|jpe?g|webp)',
    re.IGNORECASE,
)


def _extract_variant_base_image_urls(flight_text: str) -> list[str]:
    """Extract image URLs from the variant_base_images metafield in the RSC flight payload.

    The metafield value is a JSON-encoded string containing an array of objects
    with a ``src`` key, e.g.::

        {"key":"variant_base_images","value":"[{\\"src\\":\\"https://cdn.shopify.com/...\\"}]"}

    Returns a deduplicated list of URLs (first-seen order).  Never raises.
    """
    seen: set[str] = set()
    out: list[str] = []

    if "variant_base_images" not in flight_text:
        return out

    for m in _VARIANT_BASE_IMAGES_RE.finditer(flight_text):
        raw_value = m.group(1)
        try:
            # The captured string is JSON-escaped; decode it to get the inner JSON array.
            decoded = json.loads(f'"{raw_value}"')
            arr = json.loads(decoded)
            if isinstance(arr, list):
                for obj in arr:
                    if isinstance(obj, dict):
                        src = obj.get("src")
                        if isinstance(src, str) and src and src not in seen:
                            seen.add(src)
                            out.append(src)
        except Exception:
            pass

    # Fallback: if JSON parsing found nothing, scan for CDN URLs near the anchor
    if not out:
        try:
            anchor = flight_text.find('"variant_base_images"')
            if anchor != -1:
                region = flight_text[anchor: anchor + 4096]
                for url in _CDN_IMG_DIRECT_RE.findall(region):
                    if url not in seen:
                        seen.add(url)
                        out.append(url)
        except Exception:
            pass

    return out


def _fallback_shopify_image_urls(flight_text: str) -> list[str]:
    """Scan the full RSC flight text for any Shopify/Backblaze CDN image URLs.

    Used as a last-resort catch-all when variant_base_images yields < 2 images.
    Never raises.
    """
    seen: set[str] = set()
    out: list[str] = []
    try:
        for url in _SHOPIFY_IMG_RE.findall(flight_text):
            if url not in seen:
                seen.add(url)
                out.append(url)
    except Exception:
        pass
    return out


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


_METAFIELD_ANCHOR = '"metafields":['
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_FLAVOUR_HEADER_RE = re.compile(r"^[A-Z][A-Za-z0-9 &\-/]{1,40}:\s*$")
# RSC Flight pointers look like "$24" or "$1e" — they are unresolved React server component refs.
# Indices may be decimal or hex (e.g. $1e uses the hex digit 'e').
_RSC_PTR_RE = re.compile(r"^\$[0-9a-f]+$", re.IGNORECASE)


def _extract_descriptive_text(html: str, meta: dict[str, str]) -> str:
    """Combine page-body prose from HTML + already-extracted metafields.

    Sources (in order):
      - <div class="old-description"> — EFSA-style benefit bullets + paragraphs.
        On Healf Next.js pages this div lives inside the RSC Flight payload as
        escaped HTML, so we parse the decoded flight text rather than the raw DOM.
      - meta["why_its_healf"]  — brand origin / curation reason.
      - meta["suggested_use"]  — usage instructions.

    RSC Flight pointer values (e.g. "$24") are skipped — they are unresolved
    server-component references that contain no useful text.

    Returns a markdown-ish string with ## section headers, or "" if nothing found.
    """
    sections: list[str] = []

    # The old-description div is embedded as escaped HTML inside __next_f.push()
    # strings in the RSC payload. Decode the flight text and parse that instead
    # of the raw page DOM, where the div is invisible to selectolax.
    flight = extract_rsc_flight(html)
    parse_source = flight if flight else html
    tree = HTMLParser(parse_source)
    desc_node = tree.css_first("div.old-description")
    if desc_node:
        lines: list[str] = []
        for li in desc_node.css("li"):
            text = (li.text() or "").strip()
            if text:
                lines.append(f"- {text}")
        for p in desc_node.css("p"):
            text = (p.text() or "").strip()
            if text:
                lines.append(text)
        if lines:
            sections.append("## Description\n" + "\n".join(lines))

    why = (meta.get("why_its_healf") or "").strip()
    if why and not _RSC_PTR_RE.match(why):
        sections.append("## Why It's Healf\n" + why)

    use = (meta.get("suggested_use") or "").strip()
    if use and not _RSC_PTR_RE.match(use):
        sections.append("## Suggested Use\n" + use)

    return "\n\n".join(sections)


def _claims_from_old_description(html: str) -> list[str]:
    """Extract claim bullets from <div class='old-description'> in the RSC flight.

    Returns up to 10 non-empty <li> texts that are not RSC pointers.
    Returns [] if the div is not found or has no valid <li> items.
    """
    flight = extract_rsc_flight(html)
    parse_source = flight if flight else html
    tree = HTMLParser(parse_source)
    desc_node = tree.css_first("div.old-description")
    if not desc_node:
        return []
    claims: list[str] = []
    for li in desc_node.css("li"):
        text = (li.text() or "").strip()
        # Strip leading bullet characters
        text = text.lstrip("•–-· ").strip()
        if text and not _RSC_PTR_RE.match(text):
            claims.append(text)
    return claims[:10]


def _clean_metafield_text(raw: str) -> str:
    """Convert <br> to newlines, strip HTML tags, unescape entities."""
    if not raw:
        return ""
    s = _BR_RE.sub("\n", raw)
    s = _TAG_RE.sub("", s)
    s = _html.unescape(s)
    return s.strip()


def _slice_balanced_array(text: str, start_bracket: int) -> str | None:
    """Return text[start_bracket : matching_close+1], tracking string boundaries."""
    depth = 0
    i = start_bracket
    in_string = False
    escape = False
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return text[start_bracket : i + 1]
        i += 1
    return None


def _split_ingredient_blob_by_flavour(blob: str) -> dict[str, list[str]]:
    """Parse a multi-flavour ingredient blob into {flavour_name: [ingredient, ...]}.

    Returns empty dict for single-flavour blobs (no headers detected).
    Preserves per-flavour duplication and order — do NOT dedupe across flavours.
    """
    if not blob:
        return {}
    by_flavour: dict[str, list[str]] = {}
    current: str | None = None
    for line in blob.splitlines():
        line = line.strip()
        if not line:
            continue
        if _FLAVOUR_HEADER_RE.match(line):
            current = line.rstrip(":").strip()
            by_flavour.setdefault(current, [])
            continue
        if current is None:
            continue
        for raw_ing in line.split(","):
            ing = raw_ing.strip().rstrip(".")
            if ing:
                by_flavour[current].append(ing)
    return by_flavour


def _split_ingredient_blob(blob: str) -> list[str]:
    """Split a multi-flavour ingredient blob into a flat, deduplicated ingredient list."""
    if not blob:
        return []
    items: list[str] = []
    seen: set[str] = set()
    for line in blob.splitlines():
        line = line.strip()
        if not line or _FLAVOUR_HEADER_RE.match(line):
            continue
        for raw_ing in line.split(","):
            ing = raw_ing.strip().rstrip(".")
            if not ing:
                continue
            key = ing.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(ing)
    return items


def extract_metafields(html: str) -> dict[str, str]:
    """Extract all Shopify metafields from the RSC flight payload.

    Shopify embeds metafields as ``{"key": ..., "value": ...}`` objects inside a
    ``"metafields":[...]`` array in the Next.js RSC flight payload.  Bracket-walking
    is used instead of regex because metafield values routinely contain commas,
    brackets, and HTML — all of which break naive ``[^\\]]*`` patterns.
    """
    flight = extract_rsc_flight(html)
    if not flight:
        return {}
    out: dict[str, str] = {}
    search_from = 0
    while True:
        anchor = flight.find(_METAFIELD_ANCHOR, search_from)
        if anchor == -1:
            break
        start_bracket = anchor + len(_METAFIELD_ANCHOR) - 1  # the '['
        raw = _slice_balanced_array(flight, start_bracket)
        if raw is None:
            break
        try:
            arr = json.loads(raw)
        except json.JSONDecodeError:
            search_from = start_bracket + 1
            continue
        for entry in arr:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key")
            value = entry.get("value")
            if isinstance(key, str) and isinstance(value, str):
                cleaned = _clean_metafield_text(value)
                if cleaned and (key not in out or len(cleaned) > len(out[key])):
                    out[key] = cleaned
        search_from = start_bracket + len(raw)
    return out


def load_full_product(url: str) -> Product:
    """Fetch a Healf PDP and return a fully-populated Product.

    Single source of truth for product loading — called by both app.py
    (Streamlit Fetch button) and dispatch_tool('fetch_product'). Populates
    ingredients, claims, and raw_metafields from the RSC metafield array.
    """
    from healf_agent.tools.navigate import fetch_product_page  # local import avoids circular dep

    html_text = fetch_product_page(url)
    p = parse_product(html_text, url=url)

    # Merge image sources: JSON-LD hero + variant_base_images + CDN fallback
    flight_text = extract_rsc_flight(html_text)
    merged_urls: list[str] = [str(img.url) for img in p.images]
    seen_urls: set[str] = set(merged_urls)

    variant_urls = _extract_variant_base_image_urls(flight_text)
    for u in variant_urls:
        if u not in seen_urls:
            seen_urls.add(u)
            merged_urls.append(u)

    if len(merged_urls) < 2:
        for u in _fallback_shopify_image_urls(flight_text):
            if u not in seen_urls:
                seen_urls.add(u)
                merged_urls.append(u)

    meta = extract_metafields(html_text)
    updates: dict[str, Any] = {"raw_metafields": meta or None}

    if len(merged_urls) > len(p.images):
        valid_images = []
        for u in merged_urls:
            try:
                valid_images.append(Image(url=u))
            except Exception:
                pass
        updates["images"] = valid_images
    if not p.ingredients:
        blob = meta.get("ingredients") or meta.get("ingredient")
        if blob:
            by_flav = _split_ingredient_blob_by_flavour(blob)
            if by_flav:
                updates["ingredients_by_flavour"] = by_flav
            updates["ingredients"] = _split_ingredient_blob(blob)
    page_text = _extract_descriptive_text(html_text, meta)
    if page_text:
        updates["page_text"] = page_text
    if not p.claims:
        claims_primary = _claims_from_old_description(html_text)
        if claims_primary:
            updates["claims"] = claims_primary
        else:
            claims_blob = meta.get("claims") or meta.get("why_its_healf")
            if claims_blob and not _RSC_PTR_RE.match(claims_blob.strip()):
                candidates = [c.strip() for c in claims_blob.split("\n") if c.strip()]
                updates["claims"] = [c for c in candidates if not _RSC_PTR_RE.match(c)][:10]
    return p.model_copy(update=updates)
