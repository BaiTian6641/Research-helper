"""Streamlit application — main entry point.

Run with:  streamlit run src/ui/app.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st

from src.storage.cache import UIResultCache
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

    # ── Restore last session from disk on first load ────────────────────────
    # Streamlit session_state is in-memory per browser session, but the
    # UIResultCache persists to .cache/ui_last_result.json so results survive
    # page refreshes, computer sleep, and Streamlit restarts.
    if "last_search" not in st.session_state:
        cached = UIResultCache.load()
        if cached and cached.get("result"):
            st.session_state["last_search"] = cached["result"]
            st.session_state["_cache_restored_at"] = cached.get("saved_at", "")
            st.session_state["_cache_restored_query"] = cached.get("query", "")
            # Pre-fill query inputs so both pages show the right query
            if "dashboard_query" not in st.session_state:
                st.session_state["dashboard_query"] = cached.get("query", "")
            if "sq_query" not in st.session_state:
                st.session_state["sq_query"] = cached.get("query", "")

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

    # Restore-from-cache indicator
    if st.session_state.get("_cache_restored_at"):
        _ts = st.session_state["_cache_restored_at"]
        try:
            _dt = datetime.fromisoformat(_ts)
            _ts_str = _dt.strftime("%b %d %H:%M")
        except Exception:
            _ts_str = str(_ts)[:16]
        _q = str(st.session_state.get("_cache_restored_query", ""))[:22]
        st.sidebar.divider()
        st.sidebar.caption(f"⚡ Restored: **{_q}** ({_ts_str})")
        if st.sidebar.button("🗑️ Clear cache", key="clear_ui_cache"):
            UIResultCache.clear()
            for _k in ("last_search", "_cache_restored_at", "_cache_restored_query",
                       "dashboard_stats", "dashboard_query"):
                st.session_state.pop(_k, None)
            st.rerun()

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
