"""Healf Product Intelligence Agent — HITL Review Queue (Streamlit page)."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from healf_agent.storage import Storage

st.set_page_config(page_title="HITL Review Queue", layout="wide")

storage = Storage(Path("healf.sqlite"))
storage.init_schema()

# ── Sidebar: status filter ─────────────────────────────────────────────────

with st.sidebar:
    st.subheader("HITL Review Queue")
    status_filter = st.radio(
        "Show entries",
        options=["pending", "all"],
        index=0,
    )

# ── Load entries ────────────────────────────────────────────────────────────

filter_arg = "pending" if status_filter == "pending" else None
entries = storage.list_hitl(status=filter_arg)

pending_count = len(storage.list_hitl(status="pending"))
with st.sidebar:
    st.markdown(f"**Pending:** {pending_count}")

st.title("HITL Review Queue")

if not entries:
    st.info("No pending drafts. Run an audit in the chat first.")
    st.stop()

# ── Entry selector ──────────────────────────────────────────────────────────

entry_labels = [
    f"#{e.id} — {e.product_handle} ({e.gap_summary[:60]}…)"
    for e in entries
]
selected_label = st.selectbox("Select draft to review", options=entry_labels)
selected_index = entry_labels.index(selected_label)
entry = entries[selected_index]

st.divider()

# ── Two-column view ─────────────────────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Original Description")
    st.text_area(
        label="original",
        value=entry.original_description or "",
        height=300,
        disabled=True,
        label_visibility="collapsed",
    )

with col_right:
    st.subheader("Drafted Description")
    draft_value = st.text_area(
        label="draft",
        value=entry.drafted_description or "",
        height=300,
        key=f"draft_{entry.id}",
        label_visibility="collapsed",
    )

# ── Gap summary expander ────────────────────────────────────────────────────

with st.expander("Gap summary", expanded=False):
    st.write(entry.gap_summary or "_No gap summary recorded._")

# ── Reviewer note ───────────────────────────────────────────────────────────

reviewer_note = st.text_input(
    "Reviewer note (optional)",
    value="",
    key=f"note_{entry.id}",
)

# ── Status badge ────────────────────────────────────────────────────────────

status_colours = {
    "pending": "orange",
    "approved": "green",
    "edited": "blue",
    "rejected": "red",
}
colour = status_colours.get(entry.status, "grey")
st.markdown(
    f"Current status: :{colour}[**{entry.status.upper()}**]"
)

# ── Action buttons ──────────────────────────────────────────────────────────

btn_col1, btn_col2, btn_col3 = st.columns(3)

with btn_col1:
    if st.button("✅ Approve", use_container_width=True):
        storage.update_hitl(
            entry.id,
            status="approved",
            reviewer_note=reviewer_note or None,
        )
        st.success(f"Entry #{entry.id} approved.")
        st.rerun()

with btn_col2:
    if st.button("✏️ Save as edited", use_container_width=True):
        storage.update_hitl(
            entry.id,
            status="edited",
            drafted_description=draft_value,
            reviewer_note=reviewer_note or None,
        )
        st.success(f"Entry #{entry.id} saved as edited.")
        st.rerun()

with btn_col3:
    if st.button("❌ Reject", use_container_width=True):
        storage.update_hitl(
            entry.id,
            status="rejected",
            reviewer_note=reviewer_note or None,
        )
        st.success(f"Entry #{entry.id} rejected.")
        st.rerun()
