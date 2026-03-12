"""Streamlit application — main entry point.

Run with:  streamlit run src/ui/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from src.ui.api_client import APIClient

# Page config
st.set_page_config(
    page_title="Research Field Intelligence Tool",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    client = APIClient()

    # Sidebar navigation
    st.sidebar.title("🔬 Research Intelligence")
    st.sidebar.caption("Analyse academic fields, search databases, and evaluate proposals.")

    page = st.sidebar.radio(
        "Navigate",
        [
            "🔍 Search",
            "📊 Dashboard",
            "📚 Library",
            "📝 Proposal",
            "⚙️ Settings",
        ],
        label_visibility="collapsed",
    )

    # Status indicator in sidebar
    try:
        status = client.get_status()
        llm_ok = status.get("llm_available", False)
        st.sidebar.divider()
        st.sidebar.caption(
            f"LLM: {'🟢' if llm_ok else '🔴'} "
            f"{'Online' if llm_ok else 'Offline'} | "
            f"Papers: {status.get('paper_count', 0)}"
        )
    except Exception:
        st.sidebar.caption("⚠️ Backend not connected")

    # Route to page
    if page == "🔍 Search":
        from src.ui.pages.search_page import render
        render(client)
    elif page == "📊 Dashboard":
        from src.ui.pages.dashboard_page import render
        render(client)
    elif page == "📚 Library":
        from src.ui.pages.library_page import render
        render(client)
    elif page == "📝 Proposal":
        from src.ui.pages.proposal_page import render
        render(client)
    elif page == "⚙️ Settings":
        from src.ui.pages.settings_page import render
        render(client)


if __name__ == "__main__":
    main()
