"""Anthropic tool-use loop."""
from __future__ import annotations

import json
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
"""


def run_agent_turn(
    *,
    client,
    model: str,
    user_message: str,
    product: Product | None,
    system: str = SYSTEM_PROMPT,
    max_iters: int = 8,
) -> tuple[str, list[dict[str, Any]]]:
    """Run a single agent turn (tool-use loop) and return (final_text, tool_trace)."""
    trace: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    for _ in range(max_iters):
        resp = client.messages.create(
            model=model,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=TOOL_SCHEMAS,
            messages=messages,
            max_tokens=2048,
        )
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
        return text, trace
    return "Iteration cap reached without final answer.", trace
