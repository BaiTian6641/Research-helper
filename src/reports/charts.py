"""Shared Plotly chart builders for reports and UI."""

from __future__ import annotations

import plotly.graph_objects as go


def build_papers_per_year(papers_per_year: dict, query: str = "") -> go.Figure:
    """Bar chart of papers per year."""
    years = sorted(papers_per_year.keys(), key=str)
    counts = [papers_per_year[y] for y in years]
    fig = go.Figure(data=[go.Bar(x=years, y=counts, marker_color="#4C78A8")])
    fig.update_layout(
        title=f"Publications per Year — {query}" if query else "Publications per Year",
        xaxis_title="Year",
        yaxis_title="Papers",
        template="plotly_white",
    )
    return fig


def build_score_radar(
    interest: float, motivation: float, confidence: float, market: float
) -> go.Figure:
    """Radar chart of the 4 dimension scores."""
    categories = ["Interest", "Motivation", "Confidence", "Market"]
    values = [interest, motivation, confidence, market]
    values.append(values[0])  # close the polygon
    categories.append(categories[0])

    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=values,
                theta=categories,
                fill="toself",
                marker_color="#4C78A8",
            )
        ]
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="Dimension Scores",
        template="plotly_white",
    )
    return fig


def build_top_venues_bar(top_venues: list) -> go.Figure:
    """Horizontal bar chart of top venues."""
    if not top_venues:
        return go.Figure()
    names = [v[0][:40] for v in top_venues[:10]]
    counts = [v[1] for v in top_venues[:10]]
    fig = go.Figure(
        data=[go.Bar(y=names[::-1], x=counts[::-1], orientation="h", marker_color="#72B7B2")]
    )
    fig.update_layout(
        title="Top Venues",
        template="plotly_white",
        margin=dict(l=250),
    )
    return fig


def build_top_cited_bar(top_cited: list) -> go.Figure:
    """Horizontal bar chart of top cited papers."""
    if not top_cited:
        return go.Figure()
    titles = [str(p[0])[:50] for p in top_cited[:10]]
    cites = [p[1] for p in top_cited[:10]]
    fig = go.Figure(
        data=[go.Bar(y=titles[::-1], x=cites[::-1], orientation="h", marker_color="#E45756")]
    )
    fig.update_layout(
        title="Top Cited Papers",
        template="plotly_white",
        margin=dict(l=300),
    )
    return fig
