"""Venue / Author table component."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_top_venues(top_venues: list, title: str = "Top Venues") -> None:
    """Render a table of top venues."""
    if not top_venues:
        st.info("No venue data available.")
        return
    df = pd.DataFrame(top_venues, columns=["Venue", "Papers"])
    st.subheader(title)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_top_authors(top_authors: list, title: str = "Top Authors") -> None:
    """Render a table of top authors."""
    if not top_authors:
        st.info("No author data available.")
        return
    df = pd.DataFrame(top_authors, columns=["Author", "Papers"])
    st.subheader(title)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_themes(themes: list[str] | None) -> None:
    """Render research themes as tags."""
    if not themes:
        st.info("No themes extracted (LLM may not be available).")
        return
    st.subheader("Research Themes")
    cols = st.columns(min(len(themes), 5))
    for i, theme in enumerate(themes):
        with cols[i % len(cols)]:
            st.markdown(f"<span style='background-color:#e8f0fe;padding:4px 10px;border-radius:10px;font-size:0.9em'>{theme}</span>", unsafe_allow_html=True)
