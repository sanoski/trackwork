"""Report generation for the VRS MOW Tracker.

One domain: turn a project (optionally scoped to a worksite) into a weekly report, HTML for the
portal preview, PDF for email. The CLI (`scripts/generate_report.py`) and the HTTP layer
(`app/routes/api.py`) are thin callers of this package; nothing here imports `app.routes`.

Dependency direction: reporting → {storage, structures, models, config}. Acyclic.
"""
from ..models import ReportOptions
from .data import (
    Period,
    assemble,
    build_summary,
    full_period,
    get_report_week,
    range_period,
    resolve_period,
    resolve_report_week,
    scope_projects,
    week_activity,
    week_of,
    week_period,
)
from .email import send_email
from .options import default_options
from .render import build_html, build_pdf
from .run import RunResult, run_report

__all__ = [
    "ReportOptions",
    "default_options",
    "assemble",
    "build_summary",
    "scope_projects",
    "week_activity",
    "get_report_week",
    "week_of",
    "resolve_report_week",
    "Period",
    "resolve_period",
    "week_period",
    "full_period",
    "range_period",
    "build_html",
    "build_pdf",
    "send_email",
    "RunResult",
    "run_report",
]
