"""Healf Product Intelligence Agent — Streamlit entry point + navigation."""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

from healf_agent import theme
from healf_agent.agent import run_agent_turn
from healf_agent.models import Product
from healf_agent.storage import Storage
from healf_agent.tools.ingest import load_full_product

from pages.hitl import run as hitl_run

load_dotenv()

st.set_page_config(
    page_title="Healf Product Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)

_WELCOME_CHIPS = [
    "What claims does this product actually support?",
    "Are the ingredients consistent with the label?",
    "How does this compare to similar products?",
    "Draft a stronger product description.",
]

_DEFAULT_URL = "https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack"


def _relative_time(ts: float) -> str:
    import time
    diff = time.time() - ts
    if diff < 60:
        return "just now"
    if diff < 3600:
        return f"{int(diff // 60)}m ago"
    if diff < 86400:
        return f"{int(diff // 3600)}h ago"
    return f"{int(diff // 86400)}d ago"


def _load_session(storage: Storage, session_id: int) -> None:
    messages = storage.get_session_messages(session_id)
    st.session_state["session_id"] = session_id
    st.session_state["messages"] = messages
    # Restore product from session's product_handle if any
    rows = storage.conn.execute(
        "SELECT product_handle FROM chat_sessions WHERE id=?", (session_id,)
    ).fetchone()
    handle = rows["product_handle"] if rows else None
    if handle:
        prod = storage.get_product(handle)
        st.session_state["product"] = prod.model_dump(mode="json") if prod else None
    else:
        st.session_state["product"] = None


def chat_page() -> None:
    theme.inject(st)

    storage = Storage(Path(os.environ.get("HEALF_DB", "healf.sqlite")))
    storage.init_schema()

    # ── Session bootstrap ────────────────────────────────────────────────────
    if "session_id" not in st.session_state:
        sid = storage.create_chat_session("New conversation")
        st.session_state["session_id"] = sid
        st.session_state["messages"] = []

    session_id: int = st.session_state["session_id"]

    # ── SIDEBAR ──────────────────────────────────────────────────────────────
    with st.sidebar:
        # Brand block
        st.markdown(
            """
            <div style="padding: 24px 20px 16px; border-bottom: 1px solid #D9D2C0;">
              <div style="font-family:'Fraunces',Georgia,serif; font-size:22px;
                          font-weight:600; letter-spacing:-0.02em; color:#1A1F1A;">
                HEALF
              </div>
              <div style="font-family:'Manrope',sans-serif; font-size:11px;
                          font-weight:600; letter-spacing:0.14em; text-transform:uppercase;
                          color:#8A8478; margin-top:2px;">
                Product Intelligence
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # New conversation button
        st.markdown('<div style="padding: 8px 12px 4px;">', unsafe_allow_html=True)
        if st.button("＋  New conversation", use_container_width=True, type="secondary"):
            sid = storage.create_chat_session("New conversation")
            st.session_state["session_id"] = sid
            st.session_state["messages"] = []
            st.session_state["product"] = None
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # Recent sessions — only show conversations that have at least one message
        sessions = [s for s in storage.list_recent_sessions(20) if s["message_count"] > 0][:5]
        if sessions:
            st.markdown(
                """
                <div style="padding: 12px 16px 4px; font-family:'Manrope',sans-serif;
                            font-size:11px; font-weight:700; letter-spacing:0.14em;
                            text-transform:uppercase; color:#8A8478;">
                  Recent
                </div>
                """,
                unsafe_allow_html=True,
            )
            for s in sessions:
                is_active = s["id"] == session_id
                css_class = "session-active" if is_active else "session-inactive"
                st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
                label = s["title"][:34] + "…" if len(s["title"]) > 34 else s["title"]
                n_msgs = s["message_count"]
                rel = _relative_time(s["updated_at"])
                btn_label = f"{label}\n{rel} · {n_msgs} msg{'s' if n_msgs != 1 else ''}"
                if st.button(btn_label, key=f"sess_{s['id']}", use_container_width=True):
                    _load_session(storage, s["id"])
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        # Divider + product section
        st.markdown(
            """
            <div style="border-top: 1px solid #D9D2C0; margin: 12px 0 8px;"></div>
            <div style="padding: 4px 16px 4px; font-family:'Manrope',sans-serif;
                        font-size:11px; font-weight:700; letter-spacing:0.14em;
                        text-transform:uppercase; color:#8A8478;">
              Product
            </div>
            """,
            unsafe_allow_html=True,
        )
        url = st.text_input("Product URL", value=_DEFAULT_URL, label_visibility="collapsed")
        fetch = st.button("Fetch product", use_container_width=True, type="primary")

    # Handle fetch
    if fetch and url:
        with st.spinner("Fetching product…"):
            try:
                product = load_full_product(url)
                storage.upsert_product(product)
                storage.update_session_product(session_id, product.handle)
                st.session_state["product"] = product.model_dump(mode="json")
                st.toast(f"Loaded {product.title}", icon="✅")
            except Exception as exc:
                st.error(f"Could not load product: {exc}")

    product_dict = st.session_state.get("product")
    product: Product | None = Product.model_validate(product_dict) if product_dict else None

    # ── MAIN PANE ────────────────────────────────────────────────────────────

    # Product card
    if product is not None:
        rating_val = product.rating_value or 0.0
        rating_count = product.rating_count or 0
        stars = "★" * round(rating_val) + "☆" * (5 - round(rating_val))
        rating_str = f"{rating_val} ({rating_count:,} reviews)" if rating_count else "No reviews yet"
        st.markdown(
            f"""
            <div style="background:#fff; border:1px solid #D9D2C0; border-radius:16px;
                        padding:20px 24px; margin-bottom:24px;">
              <div style="font-family:'Manrope',sans-serif; font-size:11px; font-weight:700;
                          letter-spacing:0.14em; text-transform:uppercase; color:#8A8478;
                          margin-bottom:6px;">
                Product &nbsp;·&nbsp;
                <span style="color:#5B6F4A;">loaded</span>
              </div>
              <div style="font-family:'Fraunces',Georgia,serif; font-size:26px;
                          font-weight:600; color:#1A1F1A; line-height:1.15; margin-bottom:6px;">
                {product.title}
              </div>
              <div style="font-family:'Manrope',sans-serif; font-size:14px; color:#4A4F47;
                          margin-bottom:10px;">
                {product.brand} &nbsp;·&nbsp; {product.product_type}
              </div>
              <div style="font-family:'Geist Mono','JetBrains Mono',monospace; font-size:13px;
                          color:#1A1F1A; display:flex; gap:20px; flex-wrap:wrap;">
                <span style="color:#D4593C;">{stars}</span>
                <span>{rating_str}</span>
                <span>£{product.price_gbp:.2f}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    messages = st.session_state.get("messages", [])

    # Welcome state
    if not messages:
        st.markdown(
            """
            <div style="text-align:center; padding: 48px 0 32px;">
              <div style="font-family:'Fraunces',Georgia,serif; font-size:28px;
                          font-weight:500; color:#1A1F1A; letter-spacing:-0.01em;
                          margin-bottom:8px;">
                Ask anything about the product.
              </div>
              <div style="font-family:'Manrope',sans-serif; font-size:15px;
                          color:#8A8478; margin-bottom:32px;">
                Claims · ingredients · listing quality · evidence gaps
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns(2)
        for i, (chip, col) in enumerate(zip(_WELCOME_CHIPS, [col1, col2, col1, col2])):
            with col:
                st.markdown('<div class="chip-btn">', unsafe_allow_html=True)
                if st.button(chip, key=f"chip_{i}", use_container_width=True):
                    st.session_state["pending_question"] = chip
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    # Render existing messages
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["text"])

    # Input — check for a pending chip question first
    pending = st.session_state.pop("pending_question", None)
    user_input = st.chat_input("Ask the agent…") or pending

    if user_input:
        # Build product context prefix
        product_ctx = ""
        if product:
            product_ctx = (
                f"Currently loaded product: '{product.title}' by {product.brand} "
                f"(URL: {product.url}, rating: {product.rating_value}/5 from "
                f"{product.rating_count} reviews). "
                f"Ingredients: {', '.join(product.ingredients) or 'not extracted'}. "
                f"Claims: {', '.join(product.claims) or 'not extracted'}.\n\n"
            )
            if product.page_text:
                product_ctx += (
                    "--- Page description text (use this for benefit/use questions) ---\n"
                    f"{product.page_text}\n"
                    "--- end page description ---\n\n"
                )

        # Update session title from first user message
        existing = st.session_state.get("messages", [])
        if not any(m["role"] == "user" for m in existing):
            storage.update_session_title(session_id, user_input[:32])

        # Append user message
        storage.append_chat_message(session_id, "user", user_input)
        st.session_state["messages"].append({"role": "user", "text": user_input})

        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
                agent_message = product_ctx + user_input if product_ctx else user_input
                answer, trace, debug = run_agent_turn(
                    client=client,
                    model="claude-sonnet-4-6",
                    user_message=agent_message,
                    product=product,
                    injected_product_context=product_ctx,
                )
            st.markdown(answer)

        storage.append_chat_message(session_id, "assistant", answer, trace, debug)
        st.session_state["messages"].append(
            {"role": "assistant", "text": answer, "trace": trace, "debug": debug}
        )


pg = st.navigation(
    [
        st.Page(chat_page, title="Chat", icon="💬", default=True),
        st.Page(hitl_run, title="HITL Review", icon="📋"),
    ],
    position="sidebar",
    expanded=True,
)
pg.run()
