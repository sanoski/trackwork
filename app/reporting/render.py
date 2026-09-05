"""Render the report view-model to HTML (preview) and PDF (WeasyPrint).

ONE Jinja template (`templates/report.html` + `report.css`) is the single source of truth for
both the in-browser preview and the emailed PDF. weasyprint is imported lazily inside `build_pdf`
so uvicorn/MCP startup never pays the Pango load cost. The bundled Oswald `@font-face` resolves
against `base_url` (the templates dir) for the PDF; the preview overrides `font_base` with a
served path (see the /report-assets mount).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import ReportOptions
from . import data
from .. import app_settings

_TEMPLATES = Path(__file__).parent / "templates"
FONTS_DIR = _TEMPLATES / "fonts"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(["html", "xml"]),
)
_env.filters["comma"] = lambda v: f"{int(v):,}" if isinstance(v, (int, float)) and v is not None else v


def build_html(projects: list, period: data.Period, options: ReportOptions,
               *, scope_label: Optional[str] = None, location: Optional[str] = None,
               font_base: str = "fonts") -> str:
    """Render the report to a self-contained HTML string. `period` is the time slice
    (week/range/full), it drives the header labels and the section wording. `font_base` is the URL
    prefix the `@font-face` rules use for the bundled Oswald TTFs, `"fonts"` (relative, resolved by
    the PDF base_url) for WeasyPrint, or a served path (e.g. `/report-assets/fonts`) for the preview."""
    views = [
        data.assemble(p, period, options, location=location, scope_label=scope_label)
        for p in projects
    ]
    org = app_settings.get_settings()
    return _env.get_template("report.html").render(
        views=views,
        org_name=org.org_name or "Vermont Rail System",
        app_name=org.app_name or "MOW Tracker",
        period_kind=period.kind,
        period_kind_label=period.kind_label,
        period_date_label=period.date_label,
        period_heading=period.heading,
        period_word=period.inline,
        scope_label=scope_label,
        generated=date.today().strftime("%B %d, %Y"),
        font_base=font_base,
        empty=not projects,
    )


def build_pdf(projects: list, period: data.Period, options: ReportOptions,
              *, scope_label: Optional[str] = None, location: Optional[str] = None) -> bytes:
    """Render the report to PDF bytes via WeasyPrint (lazy import). base_url = templates dir so the
    relative `fonts/Oswald-*.ttf` `@font-face` URLs resolve to the bundled, OFL-licensed files."""
    from weasyprint import HTML  # lazy: pulls Pango; keep it out of app startup

    html = build_html(projects, period, options,
                      scope_label=scope_label, location=location, font_base="fonts")
    return HTML(string=html, base_url=str(_TEMPLATES)).write_pdf()
