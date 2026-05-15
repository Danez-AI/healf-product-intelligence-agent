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
    {
        "name": "cluster_review_themes",
        "description": "Cluster all reviews for the current product into labelled themes (positive/negative/neutral) using embeddings + HDBSCAN + Claude.",
        "input_schema": {
            "type": "object",
            "properties": {
                "polarity_filter": {
                    "type": "string",
                    "enum": ["positive", "negative", "neutral", "all"],
                    "description": "Filter themes by polarity. Default: all.",
                }
            },
            "required": [],
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
    if name == "cluster_review_themes":
        from healf_agent.tools.review_themes import cluster_review_themes
        from healf_agent.storage import Storage
        from pathlib import Path
        import os
        from anthropic import Anthropic
        from openai import OpenAI

        if product is None:
            raise ValueError("cluster_review_themes requires a current product")
        storage = Storage(Path("healf.sqlite"))
        storage.init_schema()
        reviews = storage.get_reviews(product.gid)
        openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        themes = cluster_review_themes(
            reviews=reviews,
            product_gid=product.gid,
            openai_client=openai_client,
            anthropic_client=anthropic_client,
        )
        # Persist themes
        for t in themes:
            storage.conn.execute(
                "INSERT INTO review_themes(product_gid, polarity, label, summary, review_ids, weight)"
                " VALUES(?,?,?,?,?,?)",
                (t.product_gid, t.polarity, t.label, t.summary,
                 ",".join(t.review_ids), t.weight),
            )
        storage.conn.commit()
        polarity_filter = arguments.get("polarity_filter", "all")
        result = [t.model_dump() for t in themes
                  if polarity_filter == "all" or t.polarity == polarity_filter]
        return {"themes": result, "total_reviews": len(reviews)}
    raise ValueError(f"unknown tool: {name}")
