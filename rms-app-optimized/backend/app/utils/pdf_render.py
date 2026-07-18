"""Offer letter rendering: Jinja2 fill of the FIXED template, then WeasyPrint -> PDF.

Risk R3 (LLD): WeasyPrint needs libpango/cairo. If those aren't present (e.g. local Windows dev),
we fall back to storing the rendered HTML so the feature still works; Docker/Linux produces PDF.
"""
from __future__ import annotations

from jinja2 import Template


def render_offer_letter(template_html: str, variables: dict) -> tuple[bytes, str, str]:
    """Return (data, content_type, ext). Attempts PDF; falls back to HTML."""
    html = Template(template_html).render(**variables)
    try:
        from weasyprint import HTML  # heavy import; may raise OSError without system libs

        pdf = HTML(string=html).write_pdf()
        return pdf, "application/pdf", "pdf"
    except Exception:  # noqa: BLE001 — missing system deps -> HTML fallback (R3)
        return html.encode("utf-8"), "text/html", "html"
