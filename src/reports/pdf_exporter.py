"""PDF exporter — wraps the HTML exporter and converts to PDF via WeasyPrint."""

from __future__ import annotations

from src.reports.html_exporter import export_html


def export_pdf(stats: dict, papers: list[dict] | None = None) -> bytes:
    """Generate a PDF report. Returns raw PDF bytes.

    Requires weasyprint to be installed (pip install weasyprint).
    Falls back to returning the HTML as UTF-8 bytes if weasyprint is unavailable.
    """
    html = export_html(stats, papers)

    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except ImportError:
        # WeasyPrint not installed — return HTML bytes as fallback
        return html.encode("utf-8")
