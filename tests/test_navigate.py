import httpx
import pytest
import respx
from unittest.mock import patch

from healf_agent.tools.navigate import FetchError, fetch_product_page, normalise_url


@respx.mock
def test_fetch_returns_html_on_200() -> None:
    url = "https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack"
    respx.get(url).mock(return_value=httpx.Response(200, text="<html><body>ok</body></html>"))
    html = fetch_product_page(url)
    assert "<body>ok</body>" in html


@respx.mock
def test_fetch_raises_on_404() -> None:
    url = "https://healf.com/en-uk/products/does-not-exist"
    respx.get(url).mock(return_value=httpx.Response(404, text="missing"))
    # Mock _playwright_fetch to return None to force the FetchError
    with patch("healf_agent.tools.navigate._playwright_fetch", return_value=None):
        with pytest.raises(FetchError):
            fetch_product_page(url)


def test_fetch_normalises_locale_prefix() -> None:
    assert normalise_url("https://healf.com/products/x") == "https://healf.com/en-uk/products/x"
    assert normalise_url("https://healf.com/en-uk/products/x") == "https://healf.com/en-uk/products/x"
