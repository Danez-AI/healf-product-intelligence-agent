"""Tool registry + dispatcher for the Healf agent."""
from __future__ import annotations

from typing import Any

from healf_agent.models import Product
from healf_agent.tools.field import check_field
from healf_agent.tools.ingest import parse_product, extract_metafields
from healf_agent.tools.navigate import fetch_product_page


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "fetch_product",
        "description": "Fetch a Healf product page by URL. Returns parsed product JSON.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "check_field",
        "description": "Look up an exact factual field on the current product (ingredient, claim, brand, rating).",
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "enum": ["ingredient", "claim", "brand", "rating"]},
                "value": {"type": "string"},
            },
            "required": ["field"],
        },
    },
]


def dispatch_tool(*, name: str, arguments: dict[str, Any], product: Product | None) -> Any:
    if name == "fetch_product":
        html = fetch_product_page(arguments["url"])
        p = parse_product(html, url=arguments["url"])
        meta = extract_metafields(html)
        if meta.get("ingredient"):
            ings = meta["ingredient"]
            if isinstance(ings, str):
                ings = [ings]
            p = p.model_copy(update={"ingredients": list(ings)})
        return p.model_dump(mode="json")
    if name == "check_field":
        if product is None:
            raise ValueError("check_field requires a current product")
        return check_field(product, field=arguments["field"], value=arguments.get("value", ""))
    raise ValueError(f"unknown tool: {name}")
