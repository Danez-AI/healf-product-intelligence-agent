"""Anthropic tool-use loop."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from healf_agent.models import Product
from healf_agent.tools import TOOL_SCHEMAS, dispatch_tool


SYSTEM_PROMPT = """You are the Healf Product Intelligence Agent, a colleague for the
Healf AI Transformation Team. You answer questions about Healf product pages
(https://healf.com) and the broader Healf catalogue.

Rules:
- Ground every claim in tool output. If you don't have evidence, say you don't.
- Prefer concrete, citable facts (ingredient lists, review counts, image counts) over generalities.
- For "what should I improve?" type questions, cite specific other Healf products from the corpus.
- Refuse politely if the user asks about anything outside the Healf catalogue.
- When check_field returns present: null with extraction_status "no_metafields", do NOT claim the field is absent — say the structured data extraction failed and suggest a manual check on the live page.
- When check_field returns per_flavour: [...] and all_flavours: [...], surface those flavours by name. Say e.g. "malic acid is only in Watermelon" — do NOT say "all flavours contain X" unless per_flavour == all_flavours.
- The user message may include a "--- Page description text ---" block containing prose from the product page (benefits bullets, "Why It's Healf" curation reason, suggested use). When the user asks about benefits, what the product does, claims it makes, or how to use it, read this block before answering. Do NOT say "the claims field is empty" or "I'd recommend a manual check" if the page description text contains the answer — quote it directly.
- Nutrition panels, serving sizes, electrolyte mg quantities, and ingredient lists printed on product labels are visible only in product images. When the user asks about them and the structured ingredients / claims / page_text fields are insufficient, call score_images — its aggregated_on_pack_text field contains label text transcribed via OCR. Treat OCR output as advisory (it may be partial or noisy).
"""


def run_agent_turn(
    *,
    client,
    model: str,
    user_message: str,
    product: Product | None,
    system: str = SYSTEM_PROMPT,
    max_iters: int = 8,
    injected_product_context: str = "",
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Run a single agent turn (tool-use loop) and return (final_text, tool_trace, debug)."""
    trace: list[dict[str, Any]] = []
    debug_iterations: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    for _ in range(max_iters):
        t0 = time.perf_counter()
        resp = client.messages.create(
            model=model,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=TOOL_SCHEMAS,
            messages=messages,
            max_tokens=2048,
        )
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        iter_record = {
            "iter": len(debug_iterations),
            "ts": datetime.now(timezone.utc).isoformat(),
            "messages_snapshot": json.loads(json.dumps(messages, default=str)),
            "response_content": [
                {"type": getattr(b, "type", "unknown"), "text": getattr(b, "text", None),
                 "name": getattr(b, "name", None), "input": getattr(b, "input", None)}
                for b in resp.content
            ],
            "usage": {
                "input_tokens": getattr(getattr(resp, "usage", None), "input_tokens", 0),
                "output_tokens": getattr(getattr(resp, "usage", None), "output_tokens", 0),
                "cache_read_input_tokens": getattr(getattr(resp, "usage", None), "cache_read_input_tokens", 0),
                "cache_creation_input_tokens": getattr(getattr(resp, "usage", None), "cache_creation_input_tokens", 0),
            },
            "stop_reason": resp.stop_reason,
            "model": getattr(resp, "model", model),
            "latency_ms": latency_ms,
            "request_id": getattr(resp, "_request_id", None),
        }
        debug_iterations.append(iter_record)
        if resp.stop_reason == "tool_use":
            tool_results: list[dict[str, Any]] = []
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                try:
                    result = dispatch_tool(name=block.name, arguments=block.input, product=product)
                    serialised = json.dumps(result, default=str)
                    trace.append({"tool": block.name, "input": block.input, "output": result})
                except Exception as e:
                    serialised = json.dumps({"error": str(e)})
                    trace.append({"tool": block.name, "input": block.input, "error": str(e)})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": serialised,
                    }
                )
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": tool_results})
            continue
        # end_turn or anything else final
        text = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text += block.text
        debug: dict[str, Any] = {
            "system": system,
            "injected_context": injected_product_context,
            "iterations": debug_iterations,
        }
        return text, trace, debug
    debug = {
        "system": system,
        "injected_context": injected_product_context,
        "iterations": debug_iterations,
    }
    return "Iteration cap reached without final answer.", trace, debug
