"""HTML report exporter — builds a standalone HTML report."""

from __future__ import annotations

import base64
from datetime import datetime
from io import BytesIO

from src.reports.charts import (
    build_papers_per_year,
    build_score_radar,
    build_top_cited_bar,
    build_top_venues_bar,
)


def export_html(stats: dict, papers: list[dict] | None = None) -> str:
    """Generate a self-contained HTML report from FieldStats dict."""
    query = stats.get("query", "Unknown")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build chart images as base64
    chart_ppy = _fig_to_base64(build_papers_per_year(stats.get("papers_per_year", {}), query))
    chart_radar = _fig_to_base64(build_score_radar(
        stats.get("interest_score", 0),
        stats.get("motivation_score", 0),
        stats.get("confidence_score", 0),
        stats.get("market_score", 0),
    ))
    chart_venues = _fig_to_base64(build_top_venues_bar(stats.get("top_venues", [])))
    chart_cited = _fig_to_base64(build_top_cited_bar(stats.get("top_cited_papers", [])))

    # Themes
    themes = stats.get("top_themes") or []
    themes_html = " ".join(
        f'<span class="tag">{t}</span>' for t in themes
    )

    # Narrative
    narrative = stats.get("field_narrative") or "N/A"
    maturity = stats.get("maturity_label") or "N/A"

    # Papers table rows
    paper_rows = ""
    if papers:
        for p in papers[:200]:
            authors = ", ".join(p.get("authors", [])[:3])
            paper_rows += (
                f"<tr><td>{p.get('title','')}</td><td>{authors}</td>"
                f"<td>{p.get('year','')}</td><td>{p.get('citations','')}</td>"
                f"<td>{p.get('venue','')}</td></tr>\n"
            )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Research Field Report — {query}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2em; color: #333; }}
h1 {{ color: #1a1a2e; }}
.scores {{ display: flex; gap: 1em; margin: 1em 0; }}
.score-card {{ background: #f0f4ff; padding: 1em; border-radius: 8px; text-align: center; flex: 1; }}
.score-card .value {{ font-size: 2em; font-weight: bold; color: #4C78A8; }}
.tag {{ background: #e8f0fe; padding: 4px 10px; border-radius: 12px; margin: 2px; display: inline-block; font-size: 0.9em; }}
img.chart {{ max-width: 100%; border: 1px solid #eee; border-radius: 8px; margin: 1em 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 0.85em; }}
th {{ background: #f0f4ff; }}
.meta {{ color: #666; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>🔬 Research Field Report: {query}</h1>
<p class="meta">Generated: {now} | Total Papers: {stats.get('total_papers', 0)} | Maturity: {maturity}</p>

<h2>Dimension Scores</h2>
<div class="scores">
  <div class="score-card"><div class="value">{stats.get('interest_score',0):.0f}</div><div>Interest</div></div>
  <div class="score-card"><div class="value">{stats.get('motivation_score',0):.0f}</div><div>Motivation</div></div>
  <div class="score-card"><div class="value">{stats.get('confidence_score',0):.0f}</div><div>Confidence</div></div>
  <div class="score-card"><div class="value">{stats.get('market_score',0):.0f}</div><div>Market</div></div>
</div>

<img class="chart" src="data:image/png;base64,{chart_radar}" alt="Score Radar">

<h2>Publication Trends</h2>
<img class="chart" src="data:image/png;base64,{chart_ppy}" alt="Papers per Year">

<h2>Key Metrics</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Total Papers</td><td>{stats.get('total_papers',0)}</td></tr>
<tr><td>Review Papers</td><td>{stats.get('review_papers',0)}</td></tr>
<tr><td>H-index (estimate)</td><td>{stats.get('h_index_estimate',0)}</td></tr>
<tr><td>Growth Rate</td><td>{stats.get('growth_rate_pct',0):.1f}%</td></tr>
<tr><td>CAGR</td><td>{stats.get('cagr_pct',0):.1f}%</td></tr>
<tr><td>Median Citations</td><td>{stats.get('median_citations',0):.0f}</td></tr>
<tr><td>Industry Ratio</td><td>{stats.get('industry_ratio',0):.1%}</td></tr>
</table>

<h2>Research Themes</h2>
<div>{themes_html if themes_html else 'N/A'}</div>

<h2>Top Venues</h2>
<img class="chart" src="data:image/png;base64,{chart_venues}" alt="Top Venues">

<h2>Top Cited Papers</h2>
<img class="chart" src="data:image/png;base64,{chart_cited}" alt="Top Cited">

<h2>Field Narrative</h2>
<div>{narrative}</div>

{"<h2>Papers</h2><table><tr><th>Title</th><th>Authors</th><th>Year</th><th>Citations</th><th>Venue</th></tr>" + paper_rows + "</table>" if paper_rows else ""}

</body>
</html>"""

    return html


def _fig_to_base64(fig) -> str:
    """Convert a Plotly figure to a base64-encoded PNG string."""
    try:
        buf = BytesIO()
        fig.write_image(buf, format="png", width=800, height=400)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    except Exception:
        # kaleido not installed — return empty placeholder
        return ""
