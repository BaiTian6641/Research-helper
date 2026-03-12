"""Page 1: Search — run a new academic database search."""

from __future__ import annotations

from datetime import datetime

import re

import pandas as pd
import streamlit as st

from src.ui.api_client import APIClient
from src.ui.components.score_card import render_score_cards, render_sentiment_details
from src.ui.components.trend_chart import (
    citation_distribution_chart,
    papers_per_year_chart,
)
from src.ui.components.venue_table import (
    render_themes,
    render_top_authors,
    render_top_venues,
)

ALL_SOURCES = [
    "arxiv",
    "semantic_scholar",
    "openalex",
    "pubmed",
    "crossref",
    "ieee",
    "springer",
]

ALL_WEB_SOURCES = [
    "google_news",
    "bing_news",
]


def render(client: APIClient) -> None:
    st.header("🔍 Search Academic Databases")

    with st.form("search_form"):
        query = st.text_input(
            "Research query",
            placeholder="e.g. transformer architecture, neural networks; attention mechanism",
            help="Separate multiple keywords with commas or semicolons.",
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            year_start = st.number_input("From year", 2000, datetime.now().year, 2015)
        with col2:
            year_end = st.number_input("To year", 2000, datetime.now().year + 1, datetime.now().year)
        with col3:
            max_results = st.number_input("Max per source", 50, 1000, 200, step=50)

        sources = st.multiselect(
            "Academic Sources",
            ALL_SOURCES,
            default=["arxiv", "semantic_scholar", "openalex", "pubmed", "crossref"],
        )

        web_sources = st.multiselect(
            "News / Web Sources",
            ALL_WEB_SOURCES,
            default=ALL_WEB_SOURCES,
            help="Include public news and web articles for sentiment & comprehensive scoring.",
        )

        submitted = st.form_submit_button("🚀 Search & Analyse", use_container_width=True)

    if submitted and query:
        # Normalize keywords: split on , or ; and rejoin with spaces
        keywords = [kw.strip() for kw in re.split(r"[;,]", query) if kw.strip()]
        normalized_query = " ".join(keywords)

        with st.spinner("Searching databases and running analytics... This may take a few minutes."):
            try:
                result = client.search(
                    query=normalized_query,
                    year_start=year_start,
                    year_end=year_end,
                    max_results=max_results,
                    sources=sources,
                    web_sources=web_sources,
                )
                st.session_state["last_search"] = result
                st.success(
                    f"Found {len(result['papers'])} papers "
                    f"(session: {result['session_id']})"
                )
            except Exception as e:
                st.error(f"Search failed: {e}")
                return

    # Display results if available
    result = st.session_state.get("last_search")
    if result is None:
        st.info("Enter a query above and click Search to begin.")
        return

    stats = result["stats"]

    # Scores
    render_score_cards(stats)
    st.divider()

    # Sentiment details
    if stats.get("sentiment_positive_ratio") is not None:
        render_sentiment_details(stats)
        st.divider()

    # Trend chart
    ppy = stats.get("papers_per_year", {})
    if ppy:
        st.plotly_chart(
            papers_per_year_chart(ppy, stats.get("query", "")),
            use_container_width=True,
        )

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Papers", stats.get("total_papers", 0))
    col2.metric("H-index (est.)", stats.get("h_index_estimate", 0))
    col3.metric("Growth Rate", f"{stats.get('growth_rate_pct', 0):.1f}%")
    col4.metric("Industry Ratio", f"{stats.get('industry_ratio', 0):.1%}")

    # Maturity & narrative
    maturity = stats.get("maturity_label")
    narrative = stats.get("field_narrative")
    if maturity:
        st.markdown(f"**Field Maturity:** {maturity}")
    if narrative:
        with st.expander("📖 Field Narrative", expanded=False):
            st.markdown(narrative)

    # Themes
    render_themes(stats.get("top_themes"))
    st.divider()

    # Venues and authors
    col_v, col_a = st.columns(2)
    with col_v:
        render_top_venues(stats.get("top_venues", []))
    with col_a:
        render_top_authors(stats.get("top_authors", []))

    # Top cited
    top_cited = stats.get("top_cited_papers", [])
    if top_cited:
        st.plotly_chart(
            citation_distribution_chart(top_cited),
            use_container_width=True,
        )

    # Papers table
    st.subheader("📄 Papers")
    papers = result.get("papers", [])
    if papers:
        df = pd.DataFrame(papers)
        display_cols = ["title", "authors", "year", "venue", "citations", "doi"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available], use_container_width=True, hide_index=True)

        # CSV download
        csv_data = df[available].to_csv(index=False)
        st.download_button(
            "📥 Download CSV",
            csv_data,
            file_name=f"papers_{stats.get('query', 'export')}.csv",
            mime="text/csv",
        )
