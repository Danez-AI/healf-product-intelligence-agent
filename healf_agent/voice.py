"""Healf-voice prompt scaffolding. API-call-free — pure templates."""
from __future__ import annotations

from healf_agent.models import Product

HEALF_VOICE = (
    "Healf voice: confident, evidence-led, warm but not preachy. "
    "British English. No hype. Concrete benefits over adjectives. "
    "Premium but approachable."
)

REWRITE_SYSTEM = (
    "You are a senior copywriter for Healf, a UK premium health & "
    "wellness marketplace. " + HEALF_VOICE
)


def build_rewrite_prompt(product: Product, gap_summary: str) -> str:
    """Return the user-message prompt for draft_rewrite. No API call."""
    return (
        f"Rewrite the product description for '{product.title}' by "
        f"{product.brand}.\n\n"
        f"Current description: {product.description}\n\n"
        f"Identified gaps to address:\n{gap_summary}\n\n"
        "Requirements: 150–250 words. Address each gap concretely. "
        "Do not invent ingredients or claims not in the source. "
        "Return only the rewritten description body."
    )
