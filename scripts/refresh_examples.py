"""Regenerate examples/01..07.md by running each prompt through run_agent_turn."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when run as a script
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

LMNT_URL = "https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack"
HUMANTRA_URL = "https://healf.com/en-uk/products/humantra-hydration-electrolytes"

EXAMPLES = [
    (
        "01-ingredient-check",
        "Example 1 — Ingredient Check",
        "Does this have sodium?",
        LMNT_URL,
        None,
    ),
    (
        "02-full-evaluation",
        "Example 2 — Full Listing Evaluation",
        "Evaluate this product listing against the Healf catalogue. What score would you give it and why?",
        LMNT_URL,
        None,
    ),
    (
        "03-image-score",
        "Example 3 — Image Scoring",
        "How good are the product images? Score them and explain what's missing.",
        LMNT_URL,
        None,
    ),
    (
        "04-rewrite",
        "Example 4 — Copy Rewrite",
        "Draft a better product description for this listing.",
        LMNT_URL,
        None,
    ),
    (
        "05-compare",
        "Example 5 — Cross-Product Compare",
        (
            f"Compare LMNT vs Humantra electrolytes — which listing is stronger? "
            f"The Humantra URL is {HUMANTRA_URL}"
        ),
        LMNT_URL,
        HUMANTRA_URL,
    ),
    (
        "06-consistency",
        "Example 6 — Claims Consistency",
        "Are the claims consistent across this listing? Flag any contradictions.",
        LMNT_URL,
        None,
    ),
    (
        "07-review-themes",
        "Example 7 — Review Theme Clustering",
        "What do customers love and hate? Cluster the review themes.",
        LMNT_URL,
        None,
    ),
]

REQUIRED_KEYS = {
    "ANTHROPIC_API_KEY": "all examples",
    "OPENAI_API_KEY": "examples 02, 05 (corpus embeddings)",
    "GEMINI_API_KEY": "example 03 (image scoring)",
    "YOTPO_APP_KEY": "example 07 (reviews)",
}


def _check_keys() -> set[str]:
    missing = {k for k in REQUIRED_KEYS if not os.environ.get(k)}
    if missing:
        for k in missing:
            print(f"  WARNING: {k} not set — affects {REQUIRED_KEYS[k]}")
    return missing


def _build_product_ctx(product) -> str:
    ctx = (
        f"Currently loaded product: '{product.title}' by {product.brand} "
        f"(URL: {product.url}, rating: {product.rating_value}/5 from "
        f"{product.rating_count} reviews). "
        f"Ingredients: {', '.join(product.ingredients) or 'not extracted'}. "
        f"Claims: {', '.join(product.claims) or 'not extracted'}.\n\n"
    )
    if product.page_text:
        ctx += (
            "--- Page description text (use this for benefit/use questions) ---\n"
            f"{product.page_text}\n"
            "--- end page description ---\n\n"
        )
    return ctx


def _render_trace(trace: list) -> str:
    if not trace:
        return "_No tools called._"
    lines = []
    for i, step in enumerate(trace, 1):
        tool = step.get("tool", "?")
        inp = step.get("input", {})
        # Compact single-line input summary
        inp_parts = ", ".join(f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}" for k, v in inp.items())
        if step.get("error"):
            lines.append(f"{i}. → `{tool}({inp_parts})` → **ERROR:** {step['error']}")
        else:
            lines.append(f"{i}. → `{tool}({inp_parts})`")
    return "\n".join(lines)


def _render_metadata(debug: dict) -> tuple[int, float, int, int, int, str]:
    iters = debug.get("iterations", [])
    n = len(iters)
    total_latency = sum(it.get("latency_ms", 0) for it in iters)
    total_input = sum(it.get("usage", {}).get("input_tokens", 0) for it in iters)
    total_output = sum(it.get("usage", {}).get("output_tokens", 0) for it in iters)
    total_cache = sum(it.get("usage", {}).get("cache_read_input_tokens", 0) for it in iters)
    model = iters[-1].get("model", "unknown") if iters else "unknown"
    return n, total_latency, total_input, total_output, total_cache, model


def _write_example(
    slug: str,
    title: str,
    prompt: str,
    primary_url: str,
    secondary_url: str | None,
    product,
    answer: str,
    trace: list,
    debug: dict,
) -> None:
    n_iters, latency, inp_tok, out_tok, cache_tok, model = _render_metadata(debug)
    used_tools = ", ".join(dict.fromkeys(f"`{s['tool']}`" for s in trace)) if trace else "_none_"

    url_block = f"**URL:** `{primary_url}`"
    if secondary_url:
        url_block = (
            f"**URLs:**\n"
            f"- `{primary_url}`\n"
            f"- `{secondary_url}`"
        )

    md = f"""# {title}

**Product loaded:** {product.title}
{url_block}

**Prompt:** "{prompt}"

## Tool trace

{_render_trace(trace)}

## Agent response

{answer}

## Run metadata

- Iterations: {n_iters}
- Total latency: {latency:,.0f} ms
- Tokens: {inp_tok:,} input / {out_tok:,} output (cache_read: {cache_tok:,})
- Model: {model}

---
*Tools used: {used_tools} · Surface: Streamlit chat*
"""
    out_path = ROOT / "examples" / f"{slug}.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"  wrote {out_path.relative_to(ROOT)}")


def main() -> None:
    print("refresh_examples.py — regenerating all 7 examples from live agent\n")

    missing_keys = _check_keys()
    if "ANTHROPIC_API_KEY" in missing_keys:
        print("\nFATAL: ANTHROPIC_API_KEY is required. Aborting.")
        sys.exit(1)
    print()

    from anthropic import Anthropic
    from healf_agent.tools.ingest import load_full_product

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Cache loaded products to avoid re-fetching the same URL
    product_cache: dict[str, object] = {}

    def _get_product(url: str):
        if url not in product_cache:
            print(f"    fetching {url} …")
            product_cache[url] = load_full_product(url)
        return product_cache[url]

    from healf_agent.agent import run_agent_turn

    for slug, title, prompt, primary_url, secondary_url in EXAMPLES:
        print(f"[{slug}] {title}")
        try:
            product = _get_product(primary_url)
            product_ctx = _build_product_ctx(product)
            agent_message = product_ctx + prompt

            answer, trace, debug = run_agent_turn(
                client=client,
                model="claude-sonnet-4-6",
                user_message=agent_message,
                product=product,
                injected_product_context=product_ctx,
            )

            _write_example(
                slug=slug,
                title=title,
                prompt=prompt,
                primary_url=primary_url,
                secondary_url=secondary_url,
                product=product,
                answer=answer,
                trace=trace,
                debug=debug,
            )
            n_iters, latency, inp_tok, out_tok, _, _ = _render_metadata(debug)
            print(f"    done — {n_iters} iter(s), {latency:,.0f} ms, {inp_tok+out_tok:,} tokens total\n")

        except Exception as exc:
            print(f"    ERROR: {exc}\n")
            import traceback
            traceback.print_exc()
            print()

    print("Done. Check examples/ for regenerated files.")


if __name__ == "__main__":
    main()
