"""Navigate capability: fetch a Healf PDP, with Playwright fallback."""
from __future__ import annotations

import os
from urllib.parse import urlparse, urlunparse

import httpx

DEFAULT_UA = os.getenv(
    "HEALF_USER_AGENT",
    "HealfProductIntelligenceAgent/0.1 (https://github.com/Danez-AI/healf-product-intelligence-agent)",
)


class FetchError(RuntimeError):
    pass


def normalise_url(url: str) -> str:
    parts = urlparse(url)
    path = parts.path
    if path.startswith("/products/"):
        path = "/en-uk" + path
    return urlunparse(parts._replace(path=path))


def fetch_product_page(url: str, *, timeout: float = 30.0) -> str:
    """Fetch a Healf product page. Falls back to Playwright if HTTPS GET fails."""
    target = normalise_url(url)
    try:
        r = httpx.get(target, timeout=timeout, headers={"User-Agent": DEFAULT_UA})
    except httpx.HTTPError as e:
        return _playwright_fetch(target) or _fail(f"http error: {e}")
    if r.status_code != 200:
        return _playwright_fetch(target) or _fail(f"status {r.status_code}")
    return r.text


def _playwright_fetch(url: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=DEFAULT_UA)
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            html = page.content()
            browser.close()
            return html
    except Exception:
        return None


def _fail(msg: str) -> str:
    raise FetchError(msg)
