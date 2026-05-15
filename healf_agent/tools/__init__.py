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
    {
        "name": "benchmark_against_category",
        "description": "Find similar products in the Healf corpus and return comparative context.",
        "input_schema": {"type": "object", "properties": {"k": {"type": "integer", "default": 5}}, "required": []},
    },
    {
        "name": "evaluate_listing_quality",
        "description": "Score the current product listing on 5 quality axes using Claude, grounded in corpus neighbours and review themes.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "score_images",
        "description": "Score product images using Gemini Vision rubric (clarity, lifestyle shots, label legibility).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "check_consistency",
        "description": "Cross-validate the product's ingredients, claims, description, and review themes for inconsistencies.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
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
        storage = Storage(Path(os.environ.get("HEALF_DB", "healf.sqlite")))
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
        # Persist themes (clear existing first to prevent duplicate rows)
        storage.conn.execute("DELETE FROM review_themes WHERE product_gid=?", (product.gid,))
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
    if name == "benchmark_against_category":
        from healf_agent.tools.benchmark import benchmark_against_category
        from healf_agent.storage import Storage
        from pathlib import Path
        import os
        from openai import OpenAI

        if product is None:
            raise ValueError("benchmark_against_category requires a current product")
        storage = Storage(Path(os.environ.get("HEALF_DB", "healf.sqlite")))
        storage.init_schema()
        openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        k = int(arguments.get("k", 5))
        return benchmark_against_category(
            product=product,
            storage=storage,
            openai_client=openai_client,
            k=k,
        )
    if name == "evaluate_listing_quality":
        from healf_agent.tools.evaluate import evaluate_listing_quality
        from healf_agent.tools.benchmark import benchmark_against_category
        from healf_agent.storage import Storage
        from pathlib import Path
        import os
        from openai import OpenAI
        from anthropic import Anthropic

        if product is None:
            raise ValueError("evaluate_listing_quality requires a current product")
        storage = Storage(Path(os.environ.get("HEALF_DB", "healf.sqlite")))
        storage.init_schema()
        openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        neighbours_result = benchmark_against_category(
            product=product, storage=storage, openai_client=openai_client
        )
        neighbours = neighbours_result["neighbours"]
        # Load stored review themes for this product
        theme_rows = storage.conn.execute(
            "SELECT polarity, label, summary FROM review_themes WHERE product_gid=?",
            (product.gid,)
        ).fetchall()
        themes = [{"polarity": r["polarity"], "label": r["label"], "summary": r["summary"]} for r in theme_rows]
        report = evaluate_listing_quality(
            product=product,
            neighbours=neighbours,
            themes=themes,
            anthropic_client=anthropic_client,
        )
        return report.model_dump(mode="json")
    if name == "score_images":
        from healf_agent.tools.vision import score_images
        from google import genai
        import os

        if product is None:
            raise ValueError("score_images requires a current product")
        gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        return score_images(product=product, gemini_client=gemini_client)
    if name == "check_consistency":
        from healf_agent.tools.consistency import check_consistency
        from healf_agent.storage import Storage
        from pathlib import Path
        import os
        from anthropic import Anthropic

        if product is None:
            raise ValueError("check_consistency requires a current product")
        anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        storage = Storage(Path(os.environ.get("HEALF_DB", "healf.sqlite")))
        storage.init_schema()
        theme_rows = storage.conn.execute(
            "SELECT polarity, label, summary FROM review_themes WHERE product_gid=?",
            (product.gid,)
        ).fetchall()
        themes = [{"polarity": r["polarity"], "label": r["label"], "summary": r["summary"]} for r in theme_rows]
        report = check_consistency(product=product, themes=themes, anthropic_client=anthropic_client)
        return report.model_dump(mode="json")
    raise ValueError(f"unknown tool: {name}")
