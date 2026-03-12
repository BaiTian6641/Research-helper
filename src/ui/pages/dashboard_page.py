"""Page 2: Dashboard — visual analytics overview."""

from __future__ import annotations

import streamlit as st

from src.ui.api_client import APIClient
from src.ui.components.score_card import render_score_cards
from src.ui.components.trend_chart import (
    citation_distribution_chart,
    growth_rate_chart,
    papers_per_year_chart,
)
from src.ui.components.venue_table import (
    render_themes,
    render_top_authors,
    render_top_venues,
)


def render(client: APIClient) -> None:
    st.header("📊 Analytics Dashboard")

    # Re-analyse from DB
    with st.form("analyze_form"):
        query = st.text_input(
            "Query filter (leave blank for all papers)",
            value=st.session_state.get("dashboard_query", ""),
        )
        submitted = st.form_submit_button("🔄 Re-analyse", use_container_width=True)

    if submitted:
        with st.spinner("Running analytics pipeline..."):
            try:
                result = client.analyze(query=query)
                st.session_state["dashboard_stats"] = result
                st.session_state["dashboard_query"] = query
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                return

    # Try last search stats as fallback
    stats = st.session_state.get("dashboard_stats")
    if stats is None:
        last_search = st.session_state.get("last_search")
        if last_search:
            stats = last_search.get("stats")

    if stats is None:
        st.info("Run a search first or click Re-analyse to generate a dashboard.")
        return

    # Score cards
    render_score_cards(stats)
    st.divider()

    # Charts row 1
    ppy = stats.get("papers_per_year", {})
    if ppy:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(
                papers_per_year_chart(ppy, stats.get("query", "")),
                use_container_width=True,
            )
        with col2:
            st.plotly_chart(
                growth_rate_chart(ppy),
                use_container_width=True,
            )

    # Summary metrics
    st.subheader("Key Metrics")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Total Papers", stats.get("total_papers", 0))
    m2.metric("Review Papers", stats.get("review_papers", 0))
    m3.metric("H-index", stats.get("h_index_estimate", 0))
    m4.metric("CAGR", f"{stats.get('cagr_pct', 0):.1f}%")
    m5.metric("Median Citations", f"{stats.get('median_citations', 0):.0f}")
    m6.metric("Industry Ratio", f"{stats.get('industry_ratio', 0):.1%}")

    st.divider()

    # Themes
    render_themes(stats.get("top_themes"))
    st.divider()

    # Venues & Authors
    col_v, col_a = st.columns(2)
    with col_v:
        render_top_venues(stats.get("top_venues", []))
    with col_a:
        render_top_authors(stats.get("top_authors", []))

    st.divider()

    # Top cited
    top_cited = stats.get("top_cited_papers", [])
    if top_cited:
        st.plotly_chart(
            citation_distribution_chart(top_cited),
            use_container_width=True,
        )

    # Maturity & narrative
    maturity = stats.get("maturity_label")
    narrative = stats.get("field_narrative")
    if maturity or narrative:
        st.divider()
        if maturity:
            st.markdown(f"**Field Maturity:** {maturity}")
        if narrative:
            st.markdown(narrative)

    # Funders
    funders = stats.get("top_funders")
    if funders:
        st.subheader("Top Funders")
        for name, count in funders[:10]:
            st.write(f"- **{name}**: {count} mentions")
