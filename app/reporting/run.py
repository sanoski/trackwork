"""One entry point that turns a request into a finished report.

Resolves scope and period, applies the activity gate (no work logged means no report and no
email, so a quiet week stays quiet), composes the options, renders the PDF, and optionally
saves and emails it. The CLI, the in-process scheduler, and the admin "run now" action all
call run_report; it knows nothing about who triggered it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from ..structures import resolve_location
from . import data as _data
from .email import send_email
from .options import default_options
from .render import build_pdf


@dataclass
class RunResult:
    generated: bool
    reason: str = ""                      # why nothing was generated, when generated is False
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    period_label: str = ""
    projects: list[str] = field(default_factory=list)
    scope_label: Optional[str] = None
    pdf: Optional[bytes] = None
    saved_to: Optional[str] = None
    emailed_to: list[str] = field(default_factory=list)


def run_report(project_id: Optional[str] = None, location: Optional[str] = None, *,
               week: Optional[date] = None, full: bool = False,
               start: Optional[date] = None, end: Optional[date] = None,
               ties: Optional[str] = None, detail: Optional[str] = None,
               switches: bool = True, derails: bool = True,
               downtime: bool = True, charts: bool = True,
               email: bool = True, recipients: Optional[list[str]] = None,
               output: Optional[str] = None) -> RunResult:
    """Build (and optionally save and email) a report.

    Scope: `project_id` (default: the active project) narrowed by `location` (a worksite).
    Period: `start`/`end` for an explicit range (open ends default to the project span), else
    `full` for the whole project, else `week` (any date in the target week), else the most
    recently completed Sunday-to-Saturday week. Content toggles mirror the CLI flags.
    Mail problems raise RuntimeError; an unknown worksite or project returns generated=False.
    """
    try:
        projects = _data.scope_projects(project_id, location)
    except ValueError as e:
        return RunResult(False, str(e))
    if not projects:
        reason = f"project '{project_id}' not found" if project_id else "no active project"
        return RunResult(False, reason)

    if start or end:
        span = _data.full_period(projects)
        period = _data.range_period(start or span.start, end or span.end)
    elif full:
        period = _data.full_period(projects)
    elif week:
        period = _data.week_period(week)
    else:
        period = _data.week_period()

    names = [p.project.name for p in projects]
    scope = f"project '{project_id}'" if project_id else "the active project"
    if location:
        scope += f" at '{location}'"
    if _data.week_activity(projects, period.start, period.end) == 0:
        return RunResult(False, f"no work logged for {period.start} to {period.end} ({scope})",
                         period.start, period.end, period.date_label, names)

    opts = default_options(projects[0], location)
    if ties:
        opts.ties_mode = ties
    if detail:
        opts.entity_detail = detail
    if not switches:
        opts.switches = False
    if not derails:
        opts.derails = False
    if not downtime:
        opts.downtime = False
    if not charts:
        opts.charts = False

    scope_label = None
    if location:
        lid = resolve_location(projects[0], location)
        scope_label = next((loc.name for loc in projects[0].locations if loc.id == lid), None)

    pdf = build_pdf(projects, period, opts, scope_label=scope_label, location=location)
    result = RunResult(True, "", period.start, period.end, period.date_label, names,
                       scope_label, pdf)
    if output:
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(pdf)
        result.saved_to = str(out)
    if email:
        result.emailed_to = send_email(pdf, period.start, period.end,
                                       recipients=recipients, scope_label=scope_label)
    return result
