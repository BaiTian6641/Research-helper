"""Trend chart component — Plotly figures for publication trends."""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go


def papers_per_year_chart(papers_per_year: dict[str, int], query: str = "") -> go.Figure:
    """Bar chart of papers per year."""
    years = sorted(papers_per_year.keys())
    counts = [papers_per_year[y] for y in years]

    fig = go.Figure(
        data=[
            go.Bar(
                x=years,
                y=counts,
                marker_color="#4C78A8",
            )
        ]
    )
    fig.update_layout(
        title=f"Publications per Year — {query}" if query else "Publications per Year",
        xaxis_title="Year",
        yaxis_title="Papers",
        template="plotly_white",
        height=400,
    )
    return fig


def growth_rate_chart(papers_per_year: dict[str, int]) -> go.Figure:
    """Line chart of year-over-year growth rate."""
    years = sorted(papers_per_year.keys())
    counts = [papers_per_year[y] for y in years]
    rates = []
    for i in range(1, len(counts)):
        if counts[i - 1] > 0:
            rates.append((counts[i] - counts[i - 1]) / counts[i - 1] * 100)
        else:
            rates.append(0)

    fig = go.Figure(
        data=[
            go.Scatter(
                x=years[1:],
                y=rates,
                mode="lines+markers",
                line=dict(color="#E45756"),
            )
        ]
    )
    fig.update_layout(
        title="Year-over-Year Growth Rate",
        xaxis_title="Year",
        yaxis_title="Growth (%)",
        template="plotly_white",
        height=350,
    )
    return fig


def citation_distribution_chart(top_cited: list) -> go.Figure:
    """Horizontal bar chart of top-cited papers."""
    if not top_cited:
        return go.Figure()

    titles = [str(item[0])[:50] for item in top_cited[:15]]
    cites = [item[1] for item in top_cited[:15]]

    fig = go.Figure(
        data=[
            go.Bar(
                y=titles[::-1],
                x=cites[::-1],
                orientation="h",
                marker_color="#72B7B2",
            )
        ]
    )
    fig.update_layout(
        title="Top Cited Papers",
        xaxis_title="Citations",
        template="plotly_white",
        height=max(300, len(titles) * 25),
        margin=dict(l=300),
    )
    return fig


def export_chart_buttons(fig: go.Figure, filename_base: str = "chart") -> None:
    """Render download buttons for a Plotly chart.

    Always provides interactive HTML export.
    Provides PNG export when the ``kaleido`` package is installed.
    """
    col1, col2 = st.columns(2)
    html_bytes = fig.to_html(include_plotlyjs="cdn").encode("utf-8")
    with col1:
        st.download_button(
            label="⬇ Export HTML",
            data=html_bytes,
            file_name=f"{filename_base}.html",
            mime="text/html",
            use_container_width=True,
        )
    with col2:
        try:
            png_bytes = fig.to_image(format="png", width=1200, height=600, scale=2)
            st.download_button(
                label="⬇ Export PNG",
                data=png_bytes,
                file_name=f"{filename_base}.png",
                mime="image/png",
                use_container_width=True,
            )
        except Exception:
            st.caption("PNG export: `pip install kaleido`")
