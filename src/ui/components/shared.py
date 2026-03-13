"""Shared UI components used across multiple pages."""

from __future__ import annotations

import csv
import io
import json as _json

import pandas as pd
import streamlit as st


def render_security_alerts(alerts: list[dict]) -> None:
    """Render a colour-coded prompt-injection alert table.

    Confidence levels:
    * **Confirmed** (Tier 1) — red row  : unambiguously adversarial pattern
    * **High**      (Tier 2) — orange row: very suspicious, near-certain attack
    * **Medium**    (Tier 3) — amber row : heuristic / encoding anomaly
    * **Low**                — grey row  : operational (control chars, etc.)
    """
    if not alerts:
        return

    _COLOURS = {
        "Confirmed": ("#c0392b", "white"),   # red
        "High":      ("#d35400", "white"),   # orange
        "Medium":    ("#d4a017", "black"),   # amber
        "Low":       ("#7f8c8d", "white"),   # grey
    }

    confirmed = sum(1 for a in alerts if a.get("confidence") == "Confirmed")
    high      = sum(1 for a in alerts if a.get("confidence") == "High")

    # Header banner
    if confirmed > 0:
        st.error(
            f"⛔ **{confirmed} confirmed** prompt-injection pattern(s) detected and redacted. "
            "Analysis continued on sanitised text — results may be incomplete."
        )
    elif high > 0:
        st.warning(
            f"⚠️ **{high} high-confidence** suspicious pattern(s) detected and redacted."
        )
    else:
        st.info("🛡️ Suspicious input patterns detected (low/medium confidence). Details below.")

    with st.expander(
        f"🛡️ Suspicious Input Table ({len(alerts)} alert{'s' if len(alerts) != 1 else ''})",
        expanded=confirmed > 0,
    ):
        rows = [
            {
                "Confidence":     a.get("confidence", "?"),
                "Context":        a.get("context", "?").title(),
                "Detection Type": a.get("detection_type", a.get("pattern", "?")),
                "Tier":           a.get("tier", "?"),
                "Matched Text":   a.get("snippet", "")[:100],
            }
            for a in alerts
        ]
        df = pd.DataFrame(rows)

        def _style_row(row: pd.Series) -> list[str]:
            bg, fg = _COLOURS.get(str(row["Confidence"]), ("#ecf0f1", "black"))
            return [f"background-color:{bg};color:{fg}"] * len(row)

        styled = df.style.apply(_style_row, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)
        st.caption(
            "⚠️ All flagged patterns were **redacted** before reaching the LLM. "
            "The analysis above is based on the sanitised text."
        )


def render_export_buttons(stats: dict, papers: list[dict]) -> None:
    """Render CSV / JSON / HTML download buttons for analysis results."""
    query_slug = (stats.get("query") or "report")[:40].replace(" ", "_")
    col1, col2, col3 = st.columns(3)

    with col1:
        data = _json.dumps(stats, indent=2, ensure_ascii=False).encode("utf-8")
        st.download_button(
            label="⬇️ Stats (JSON)",
            data=data,
            file_name=f"stats_{query_slug}.json",
            mime="application/json",
        )

    with col2:
        if papers:
            buf = io.StringIO()
            fields = ["title", "authors", "year", "venue", "citations", "doi", "url"]
            writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for p in papers:
                row = {k: p.get(k, "") for k in fields}
                if isinstance(row.get("authors"), list):
                    row["authors"] = "; ".join(str(a) for a in row["authors"])
                writer.writerow(row)
            st.download_button(
                label="⬇️ Papers (CSV)",
                data=buf.getvalue().encode("utf-8"),
                file_name=f"papers_{query_slug}.csv",
                mime="text/csv",
            )
        else:
            st.caption("No papers list available.")

    with col3:
        try:
            from src.reports.html_exporter import export_html
            html_bytes = export_html(stats, papers).encode("utf-8")
            st.download_button(
                label="⬇️ Report (HTML)",
                data=html_bytes,
                file_name=f"report_{query_slug}.html",
                mime="text/html",
            )
        except Exception as _e:
            st.caption(f"HTML export unavailable: {_e}")
