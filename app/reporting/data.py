"""Report data layer, week math, project scoping, and the view-model.

PURE with respect to business logic: the only I/O is `scope_projects`, which loads from storage
(the report's single entry into the data store). Everything else operates on a passed-in Project.
This module centralizes logic that used to live in `scripts/generate_report.py` and
`app/routes/api.py` (the `_build_summary` back-reference + importlib hack are deleted as a result).
`assemble` returns a plain dict view-model, including pre-built chart/diagram SVG strings, that
the Jinja template in `render.py` renders verbatim.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from .. import storage
from ..models import Project, ReportOptions
from ..structures import entity_totals, resolve_location, scope_to_location
from . import charts, diagrams


# ── Week helpers ────────────────────────────────────────────────────────────────

def get_report_week(ref_date: Optional[date] = None) -> tuple[date, date]:
    """(week_start, week_end) for the most recently completed Sun–Sat week."""
    if ref_date is None:
        ref_date = date.today()
    days_since_sat = (ref_date.weekday() - 5) % 7
    week_end = ref_date - timedelta(days=days_since_sat)
    return week_end - timedelta(days=6), week_end


def week_of(d: date) -> tuple[date, date]:
    """The Sun–Sat week that contains `d` (used to snap a CLI --week value)."""
    start = d - timedelta(days=(d.weekday() + 1) % 7)
    return start, start + timedelta(days=6)


def _sunday(d: date) -> date:
    return d - timedelta(days=(d.weekday() + 1) % 7)


# ── Project scoping + activity (moved from generate_report.py / api.py) ───────────

def scope_projects(project_id: Optional[str], location: Optional[str] = None) -> list[Project]:
    """Projects a report run covers: one specific project (any status) when project_id is given,
    else all active projects. A `location` (worksite id or name) narrows each to that worksite via
    scope_to_location. Raises ValueError if `location` matches no worksite on a scoped project."""
    if project_id:
        one = storage.load_project(project_id)
        projects = [one] if one else []
    else:
        projects = [p for p in storage.list_projects() if p.project.status == "active"]
    if location and projects:
        projects = [scope_to_location(p, resolve_location(p, location)) for p in projects]
    return projects


def week_activity(projects: list, week_start: date, week_end: date) -> int:
    """Work logged in the week across projects: ties + switch + derail timbers installed.
    Option-AGNOSTIC on purpose, it gates whether there is anything to report at all, so toggling
    sections off in the wizard can never produce an empty email."""
    total = 0
    for p in projects:
        total += sum(e.ties for e in p.daily_log if week_start <= e.date <= week_end)
        total += sum(t.actual for s in p.switches if week_start <= s.date <= week_end
                     for t in s.timbers)
        total += sum(t.actual for d in p.derails if week_start <= d.date <= week_end
                     for t in d.timbers)
    return total


def resolve_report_week(projects: list) -> tuple[date, date]:
    """Portal behavior: the most recently completed week, but if it has no work for these projects,
    fall back to the week of their latest activity, so an on-demand report always reflects real
    data. (The cron/CLI use get_report_week / week_of directly and stay silent on empty weeks.)"""
    week_start, week_end = get_report_week()
    if week_activity(projects, week_start, week_end) > 0:
        return week_start, week_end
    dates: list[date] = []
    for p in projects:
        dates += [e.date for e in p.daily_log]
        dates += [s.date for s in p.switches]
        dates += [d.date for d in p.derails]
    return get_report_week(max(dates)) if dates else (week_start, week_end)


# ── Time scope (Period) ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Period:
    """The time slice a report covers. `start`/`end` drive the date filter (everything in the
    view-model is filtered to `[start, end]`); `kind` drives the wording. `week` = one Sun–Sat week
    (the default, what the cron sends), `range` = an explicit date range, `full` = a project's whole
    span. Generalizing the old single (week_start, week_end) pair is what lets a completed job show
    a full-project view instead of one sparse week."""
    start: date
    end: date
    kind: str = "week"  # "week" | "range" | "full"

    @property
    def summary_prefix(self) -> str:  # leads the "<prefix>: 163 switch timbers…" summary line
        return {"week": "This week", "range": "This period", "full": "Project to date"}[self.kind]

    @property
    def heading(self) -> str:  # Title Case suffix on section headers ("Switches: <heading>")
        return {"week": "This Week", "range": "Selected Period", "full": "Project to Date"}[self.kind]

    @property
    def inline(self) -> str:  # lowercase, mid-sentence ("7 switches <inline>")
        return {"week": "this week", "range": "this period", "full": "to date"}[self.kind]

    @property
    def kind_label(self) -> str:  # report-header kind line
        return {"week": "Weekly Progress Report", "range": "Progress Report",
                "full": "Full Project Report"}[self.kind]

    @property
    def date_label(self) -> str:  # report-header date line
        if self.kind == "full":
            return f"Project to date · through {self.end.strftime('%B %d, %Y')}"
        if self.start == self.end:
            return self.start.strftime("%B %d, %Y")
        if self.start.year == self.end.year:
            return f"{self.start.strftime('%B %d')} – {self.end.strftime('%B %d, %Y')}"
        return f"{self.start.strftime('%B %d, %Y')} – {self.end.strftime('%B %d, %Y')}"


def _project_span(projects: list) -> tuple[Optional[date], Optional[date]]:
    """(earliest, latest) dated record across ties/switches/derails for these projects."""
    dates: list[date] = []
    for p in projects:
        dates += [e.date for e in p.daily_log]
        dates += [s.date for s in p.switches]
        dates += [d.date for d in p.derails]
    return (min(dates), max(dates)) if dates else (None, None)


def week_period(ref: Optional[date] = None) -> Period:
    """A single Sun–Sat week: the one containing `ref`, or the most recent completed week."""
    ws, we = (week_of(ref) if ref else get_report_week())
    return Period(ws, we, "week")


def full_period(projects: list) -> Period:
    """The project's whole span (earliest → latest activity); falls back to the recent week if
    there is no activity at all."""
    lo, hi = _project_span(projects)
    if lo is None:
        ws, we = get_report_week()
        return Period(ws, we, "week")
    return Period(lo, hi, "full")


def range_period(start: date, end: date) -> Period:
    return Period(start, end, "range") if start <= end else Period(end, start, "range")


def resolve_period(projects: list, spec=None) -> Period:
    """Turn an optional `ReportPeriod` (the wizard/API wire format) into a concrete `Period`.
    Omitted or `mode=week` with no date → the portal default (most recent completed week, else the
    week of latest activity, via `resolve_report_week`). `mode=week`+date → that week; `mode=full`
    → whole span; `mode=range` → the given start/end (open ends default to the project span)."""
    if spec is None or spec.mode == "week":
        ref = getattr(spec, "week", None) if spec else None
        if ref:
            return week_period(ref)
        ws, we = resolve_report_week(projects)
        return Period(ws, we, "week")
    if spec.mode == "full":
        return full_period(projects)
    lo, hi = _project_span(projects)
    start = spec.start or lo or get_report_week()[0]
    end = spec.end or hi or get_report_week()[1]
    return range_period(start, end)


# ── Summary stats (moved verbatim from api.py _build_summary) ─────────────────────

def build_summary(project: Project) -> dict:
    log = project.daily_log
    meta = project.project
    total_ties = sum(e.ties for e in log)
    days_worked = len(log)
    avg_daily = total_ties / days_worked if days_worked > 0 else 0.0
    goal = meta.goal_ties
    remaining = (goal - total_ties) if goal is not None else None
    vs_schedule = total_ties - (days_worked * meta.daily_target)
    today = date.today()
    days_remaining = (meta.deadline - today).days if meta.deadline else None
    percent_complete = round(total_ties / goal * 100, 1) if goal else None

    projected_finish: Optional[date] = None
    if avg_daily > 0 and remaining is not None and remaining > 0:
        current = today
        left = float(remaining)
        while left > 0:
            current += timedelta(days=1)
            if current.weekday() < 5:  # Mon–Fri
                left -= avg_daily
        projected_finish = current

    return {
        "id": meta.id, "name": meta.name, "kind": meta.kind, "status": meta.status,
        "total_ties": total_ties, "remaining": remaining, "vs_schedule": vs_schedule,
        "projected_finish": projected_finish, "daily_target": meta.daily_target,
        "avg_daily_output": round(avg_daily, 1), "percent_complete": percent_complete,
        "deadline": meta.deadline, "days_remaining": days_remaining,
    }


# ── View-model assembly ───────────────────────────────────────────────────────────

def _tie_section(entries: list, ties_mode: str) -> Optional[dict]:
    entries = sorted([e for e in entries], key=lambda e: e.date)
    if not entries:
        return None
    show_relay = ties_mode == "both" and any(getattr(e, "relay_ties", 0) for e in entries)
    rows = []
    for e in entries:
        relay = getattr(e, "relay_ties", 0)
        tracks = getattr(e, "tracks", []) or []
        if tracks:
            note = (tracks[0].track if len(tracks) == 1
                    else " · ".join(f"{t.track}: {t.ties:,}" for t in tracks))
        else:
            note = None
        rows.append({
            "date": e.date.strftime("%b %d"), "day": e.day, "track_note": note,
            "new": e.ties - relay, "relay": relay, "total": e.ties,
            "vs_target": e.vs_target, "vs_pos": e.vs_target >= 0,
            "running_total": e.running_total, "remaining": e.remaining,
        })
    return {"ties_mode": ties_mode, "show_relay": show_relay, "rows": rows}


def _entity_block(entity, svg_fn) -> dict:
    planned, actual = entity_totals(entity)
    var = actual - planned
    var_str = ("on plan" if var == 0
               else (f"+{var} vs planned" if var > 0 else f"{var} vs planned"))
    rows = [{"length": t.length, "head_block": t.head_block,
             "planned": t.planned, "actual": t.actual}
            for t in sorted(entity.timbers, key=lambda t: t.length)]
    return {
        "name": entity.name, "date": entity.date.strftime("%b %d, %Y"),
        "planned": planned, "actual": actual, "var_str": var_str, "var_pos": var >= 0,
        "svg": svg_fn(entity), "rows": rows,
        "derail_type": getattr(entity, "derail_type", None),
    }


def _consolidated_block(entities: list, bar_color: str) -> dict:
    """ONE block standing in for every switch (or every derail) in scope: timber counts summed by
    (length, head_block) into a single by-length bar chart plus a combined Planned/Actual table.
    This is the `entity_detail="summary"` default, it keeps the report to one block per type
    instead of one diagram+table per entity (which ran to pages when an area had many switches)."""
    agg: dict = {}  # (length, head_block) -> [planned, actual]
    for e in entities:
        for t in e.timbers:
            cell = agg.setdefault((t.length, bool(t.head_block)), [0, 0])
            cell[0] += t.planned
            cell[1] += t.actual
    rows = [{"length": length, "head_block": hb, "planned": p, "actual": a}
            for (length, hb), (p, a) in sorted(agg.items())]
    planned = sum(r["planned"] for r in rows)
    actual = sum(r["actual"] for r in rows)
    var = actual - planned
    var_str = ("on plan" if var == 0
               else (f"+{var} vs planned" if var > 0 else f"{var} vs planned"))
    installed = [r for r in rows if r["actual"] > 0]
    labels = [f"{r['length']}'" + (" HB" if r["head_block"] else "") for r in installed]
    vals = [r["actual"] for r in installed]
    return {
        "count": len(entities), "planned": planned, "actual": actual,
        "var_str": var_str, "var_pos": var >= 0,
        "chart": charts.bar_chart(labels, vals, color=bar_color) if vals else None,
        "rows": rows, "names": [e.name for e in entities],
    }


def _entity_view(entities: list, svg_fn, bar_color: str, options: ReportOptions) -> Optional[dict]:
    """Switch/derail section view-model. `summary` (default) → one consolidated block; `itemized`
    (verbose) → one block per entity. None when nothing in scope (section self-suppresses)."""
    if not entities:
        return None
    if options.entity_detail == "itemized":
        return {"mode": "itemized", "entities": [_entity_block(e, svg_fn) for e in entities]}
    return {"mode": "summary", "block": _consolidated_block(entities, bar_color)}


def _downtime_row(e) -> dict:
    return {
        "date": e.date.strftime("%b %d"), "machine": e.machine,
        "down_at": e.down_at or "—", "resumed": e.resumed or "—",
        "duration": f"{e.duration_minutes} min" if e.duration_minutes is not None else "—",
        "notes": e.notes or "",
    }


def _company_cards(project: Project) -> dict:
    log = project.daily_log
    total = sum(e.ties for e in log)
    relay = sum(getattr(e, "relay_ties", 0) for e in log)
    sw_a = sum(t.actual for s in project.switches for t in s.timbers)
    dr_a = sum(t.actual for d in project.derails for t in d.timbers)
    dates = ({e.date for e in log} | {s.date for s in project.switches}
             | {d.date for d in project.derails})
    return {
        "total_timbers": total + sw_a + dr_a, "switch_timbers": sw_a,
        "switches": len(project.switches), "derails": len(project.derails),
        "new_ties": total - relay, "relay_ties": relay, "days_worked": len(dates),
    }


def _week_summary_line(is_company, wk_log, wk_switches, wk_derails, options, period) -> str:
    pre = period.summary_prefix
    empty = "No work recorded this week." if period.kind == "week" else "No work recorded in this period."
    if is_company:
        parts = []
        if options.switches and wk_switches:
            sw = sum(t.actual for s in wk_switches for t in s.timbers)
            parts.append(f"<b>{sw:,} switch timber{'s' if sw != 1 else ''}</b> across "
                         f"<b>{len(wk_switches)} switch{'es' if len(wk_switches) != 1 else ''}</b>")
        if options.derails and wk_derails:
            dr = sum(t.actual for d in wk_derails for t in d.timbers)
            parts.append(f"<b>{dr:,} derail head block{'s' if dr != 1 else ''}</b> "
                         f"({len(wk_derails)} derail{'s' if len(wk_derails) != 1 else ''})")
        if options.ties_mode != "none" and wk_log:
            ties = sum(e.ties for e in wk_log)
            parts.append(f"<b>{ties:,} tie{'s' if ties != 1 else ''}</b>")
        return (f"{pre}: " + ", ".join(parts) + ".") if parts else empty
    if options.ties_mode != "none" and wk_log:
        ties = sum(e.ties for e in wk_log)
        return f"{pre}: <b>{ties:,} ties</b> over <b>{len(wk_log)} day(s)</b>."
    return empty


# ── Chart datasets → SVG ──────────────────────────────────────────────────────────

def _tie_value(e, ties_mode: str) -> int:
    relay = getattr(e, "relay_ties", 0)
    if ties_mode == "new":
        return e.ties - relay
    if ties_mode == "relay":
        return relay
    return e.ties


def _timber_events(project: Project, options: ReportOptions) -> list:
    """[(date, amount)] across the INCLUDED streams (ties per ties_mode + switch/derail timbers)."""
    events = []
    if options.ties_mode != "none":
        for e in project.daily_log:
            v = _tie_value(e, options.ties_mode)
            if v:
                events.append((e.date, v))
    if options.switches:
        for s in project.switches:
            v = sum(t.actual for t in s.timbers)
            if v:
                events.append((s.date, v))
    if options.derails:
        for d in project.derails:
            v = sum(t.actual for t in d.timbers)
            if v:
                events.append((d.date, v))
    return events


def _weekly(events: list):
    wk: dict = {}
    for d, v in events:
        wk[_sunday(d)] = wk.get(_sunday(d), 0) + v
    weeks = sorted(wk)
    labels = [w.strftime("%b %d") for w in weeks]
    vals = [wk[w] for w in weeks]
    cum, run = [], 0
    for v in vals:
        run += v
        cum.append(run)
    return labels, vals, cum


def _composition(project: Project, options: ReportOptions) -> list:
    segs = []
    if options.ties_mode in ("new", "both"):
        segs.append(("New ties", sum(e.ties - getattr(e, "relay_ties", 0)
                                     for e in project.daily_log), charts.NAVY))
    if options.ties_mode in ("relay", "both"):
        segs.append(("Relay ties", sum(getattr(e, "relay_ties", 0)
                                       for e in project.daily_log), charts.YELLOW))
    if options.switches:
        segs.append(("Switch timbers", sum(t.actual for s in project.switches
                                           for t in s.timbers), charts.WOOD))
    if options.derails:
        segs.append(("Derail timbers", sum(t.actual for d in project.derails
                                           for t in d.timbers), charts.GREEN))
    return [(l, v, c) for (l, v, c) in segs if v > 0]


def _per_worksite(project: Project, options: ReportOptions):
    names = {loc.id: loc.name for loc in project.locations}
    if len(names) < 2:
        return None
    tot = {lid: 0 for lid in names}
    if options.ties_mode != "none":
        for e in project.daily_log:
            if e.location in tot:
                tot[e.location] += _tie_value(e, options.ties_mode)
    if options.switches:
        for s in project.switches:
            if s.location in tot:
                tot[s.location] += sum(t.actual for t in s.timbers)
    if options.derails:
        for d in project.derails:
            if d.location in tot:
                tot[d.location] += sum(t.actual for t in d.timbers)
    items = sorted([(names[lid], v) for lid, v in tot.items() if v > 0],
                   key=lambda x: -x[1])
    if len(items) < 2:
        return None
    return [l for l, _ in items], [v for _, v in items]


def _charts(project, options, summary, period, location) -> dict:
    meta = project.project
    out: dict = {}
    if meta.kind == "company":
        labels, vals, cum = _weekly(_timber_events(project, options))
        out["weekly"] = charts.bar_chart(labels, vals, color=charts.NAVY) if vals else None
        out["cumulative"] = (charts.line_chart(labels, [("Cumulative", charts.GREEN, cum)])
                             if cum and cum[-1] > 0 else None)
        comp = _composition(project, options)
        out["composition"] = charts.stacked_bar(comp) if comp else None
        pw = _per_worksite(project, options) if location is None else None
        out["per_worksite"] = charts.bar_chart(pw[0], pw[1], color=charts.NAVY) if pw else None
    else:
        if period.kind == "week":
            # one bar per day of the week, with the daily target line
            days = [period.start + timedelta(days=i) for i in range(7)]
            by = {e.date: e.ties for e in project.daily_log if period.start <= e.date <= period.end}
            out["weekly_output"] = charts.bar_chart(
                [d.strftime("%a") for d in days], [by.get(d, 0) for d in days],
                color=charts.NAVY, target=meta.daily_target)
        else:
            # a multi-week window doesn't fit a 7-day chart → bars per Sun–Sat week in range
            labels, vals, _cum = _weekly([(e.date, e.ties) for e in project.daily_log
                                          if period.start <= e.date <= period.end])
            out["weekly_output"] = charts.bar_chart(labels, vals, color=charts.NAVY) if vals else None
        slog = sorted(project.daily_log, key=lambda e: e.date)
        if slog:
            out["cumulative_target"] = charts.line_chart(
                [str(i + 1) for i in range(len(slog))],
                [("Actual", charts.NAVY, [e.running_total for e in slog]),
                 ("Target", charts.YELLOW, [(i + 1) * meta.daily_target for i in range(len(slog))])])
        else:
            out["cumulative_target"] = None
        out["progress_pct"] = summary.get("percent_complete")
    return out


def assemble(project: Project, period: Period, options: ReportOptions,
             *, location: Optional[str] = None, scope_label: Optional[str] = None) -> dict:
    """Build the per-project view-model the template renders. `project` is already location-scoped
    by the caller when a worksite is in view; `location`/`scope_label` describe that scope; `period`
    is the time slice (week/range/full) everything is filtered to."""
    meta = project.project
    is_company = meta.kind == "company"
    summary = build_summary(project)
    week_start, week_end = period.start, period.end

    title = f"{meta.name}: {meta.job}" if meta.job else meta.name
    meta_parts = []
    if meta.line:
        meta_parts.append(f"Line: {meta.line}")
    if meta.base:
        meta_parts.append(f"Base: {meta.base}")
    if meta.deadline:
        meta_parts.append(f"Deadline: {meta.deadline}")
    if meta.goal_ties:
        meta_parts.append(f"Goal: {meta.goal_ties:,} ties")
    meta_parts.append(f"Daily Target: {meta.daily_target:,}")

    wk_log = [e for e in project.daily_log if week_start <= e.date <= week_end]
    wk_switches = sorted([s for s in project.switches if week_start <= s.date <= week_end],
                         key=lambda s: (s.date, s.id))
    wk_derails = sorted([d for d in project.derails if week_start <= d.date <= week_end],
                        key=lambda d: (d.date, d.id))
    wk_downtime = [e for e in project.equipment_downtime if week_start <= e.date <= week_end]

    show = {
        "ties": options.ties_mode != "none",
        "switches": options.switches,
        "derails": options.derails,
        "downtime": options.downtime,
        "charts": options.charts,
    }
    return {
        "kind": meta.kind, "is_company": is_company, "title": title, "scope_label": scope_label,
        "meta_parts": meta_parts, "summary": summary,
        "company_cards": _company_cards(project) if is_company else None,
        "week_summary_line": _week_summary_line(is_company, wk_log, wk_switches, wk_derails, options, period),
        "show": show,
        "ties": _tie_section(wk_log, options.ties_mode) if show["ties"] else None,
        "switches": _entity_view(wk_switches, diagrams.switch_svg, charts.WOOD, options) if show["switches"] else None,
        "derails": _entity_view(wk_derails, diagrams.derail_svg, charts.GREEN, options) if show["derails"] else None,
        "downtime": [_downtime_row(e) for e in wk_downtime] if show["downtime"] else [],
        "charts": _charts(project, options, summary, period, location) if show["charts"] else {},
    }
