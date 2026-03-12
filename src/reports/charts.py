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


# ---------------------------------------------------------------------------
# Sentiment charts
# ---------------------------------------------------------------------------

def sentiment_donut_chart(
    positive_count: int,
    negative_count: int,
    neutral_count: int,
    title: str = "Sentiment Distribution",
) -> go.Figure:
    """Donut chart showing positive / neutral / negative sentence distribution."""
    labels, values, colors = [], [], []
    for label, count, color in [
        ("Positive", positive_count, "#2ECC71"),
        ("Neutral",  neutral_count,  "#95A5A6"),
        ("Negative", negative_count, "#E74C3C"),
    ]:
        if count > 0:
            labels.append(label)
            values.append(count)
            colors.append(color)
    if not values:
        return go.Figure()
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.45,
        marker=dict(colors=colors),
        textinfo="label+percent",
        hovertemplate="%{label}: %{value}<extra></extra>",
    )])
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=380,
        legend=dict(orientation="h", y=-0.1),
    )
    return fig


def sentiment_by_source_chart(academic: dict, news: dict) -> go.Figure:
    """Grouped bar chart: academic vs news/web sentiment proportions (%)."""
    labels = ["Academic Papers", "News / Web"]
    fig = go.Figure(data=[
        go.Bar(
            name="Positive",
            x=labels,
            y=[academic.get("positive_ratio", 0) * 100, news.get("positive_ratio", 0) * 100],
            marker_color="#2ECC71",
        ),
        go.Bar(
            name="Neutral",
            x=labels,
            y=[academic.get("neutral_ratio", 0) * 100, news.get("neutral_ratio", 0) * 100],
            marker_color="#95A5A6",
        ),
        go.Bar(
            name="Negative",
            x=labels,
            y=[academic.get("negative_ratio", 0) * 100, news.get("negative_ratio", 0) * 100],
            marker_color="#E74C3C",
        ),
    ])
    fig.update_layout(
        title="Sentiment by Source Type",
        yaxis_title="Proportion (%)",
        barmode="group",
        template="plotly_white",
        height=380,
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


def sentiment_by_year_chart(sentiment_by_year: dict) -> go.Figure:
    """Stacked bar chart: positive / neutral / negative counts per publication year."""
    if not sentiment_by_year:
        return go.Figure()
    years = sorted(sentiment_by_year.keys())
    pos = [sentiment_by_year[y].get("positive_count", 0) for y in years]
    neu = [sentiment_by_year[y].get("neutral_count",  0) for y in years]
    neg = [sentiment_by_year[y].get("negative_count", 0) for y in years]
    fig = go.Figure(data=[
        go.Bar(name="Positive", x=years, y=pos, marker_color="#2ECC71"),
        go.Bar(name="Neutral",  x=years, y=neu, marker_color="#95A5A6"),
        go.Bar(name="Negative", x=years, y=neg, marker_color="#E74C3C"),
    ])
    fig.update_layout(
        title="Sentiment Trend by Year",
        xaxis_title="Year",
        yaxis_title="Sentence Count",
        barmode="stack",
        template="plotly_white",
        height=420,
        legend=dict(orientation="h", y=-0.15),
    )
    return fig

