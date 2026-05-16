"""Healf Product Intelligence Agent — Streamlit entry point + navigation."""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

from healf_agent.agent import run_agent_turn
from healf_agent.models import Product
from healf_agent.storage import Storage
from healf_agent.tools.ingest import load_full_product

from pages.hitl import run as hitl_run

load_dotenv()

st.set_page_config(page_title="Healf Product Intelligence Agent", layout="wide")


def chat_page() -> None:
    st.title("Healf Product Intelligence Agent")

    storage = Storage(Path(os.environ.get("HEALF_DB", "healf.sqlite")))
    storage.init_schema()

    with st.sidebar:
        st.subheader("Current product")
        url = st.text_input(
            "Product URL",
            value="https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack",
        )
        fetch = st.button("Fetch")

    if fetch and url:
        with st.spinner("Fetching..."):
            product = load_full_product(url)
            storage.upsert_product(product)
            st.session_state["product"] = product.model_dump(mode="json")
            st.success(f"Loaded {product.title}")

    product_dict = st.session_state.get("product")
    product = Product.model_validate(product_dict) if product_dict else None
    if product is not None:
        st.sidebar.markdown(f"**{product.title}**  \n{product.brand} · {product.product_type}")
        st.sidebar.markdown(f"⭐ {product.rating_value} ({product.rating_count} reviews)")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["text"])
            if msg.get("trace"):
                with st.expander("tool trace"):
                    st.json(msg["trace"])

    user_input = st.chat_input("Ask the agent...")
    if user_input:
        st.session_state["messages"].append({"role": "user", "text": user_input})
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
                if product:
                    product_ctx = (
                        f"Currently loaded product: '{product.title}' by {product.brand} "
                        f"(URL: {product.url}, rating: {product.rating_value}/5 from "
                        f"{product.rating_count} reviews). "
                        f"Ingredients: {', '.join(product.ingredients) or 'not extracted'}. "
                        f"Claims: {', '.join(product.claims) or 'not extracted'}.\n\n"
                    )
                    user_message = product_ctx + user_input
                else:
                    user_message = user_input
                answer, trace = run_agent_turn(
                    client=client,
                    model="claude-sonnet-4-6",
                    user_message=user_message,
                    product=product,
                )
                st.markdown(answer)
                with st.expander("tool trace"):
                    st.json(trace)
        st.session_state["messages"].append({"role": "assistant", "text": answer, "trace": trace})


pg = st.navigation(
    [
        st.Page(chat_page, title="Chat", icon="💬", default=True),
        st.Page(hitl_run, title="HITL Review", icon="📋"),
    ],
    position="sidebar",
    expanded=True,
)
pg.run()
