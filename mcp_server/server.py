"""MCP server for MOW Tracker: the tools an AI assistant (Claude) uses to read and log work.

Mounted inside the web app at /mcp (see app/main.py). Can also run on its own on port 8001
for development: python mcp_server/server.py
"""

from __future__ import annotations

import sys
from datetime import date as _date
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

# Add project root to path so app.* modules are importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import storage                          # noqa: E402
from app.models import Timber  # noqa: E402
from app.reporting import build_summary  # noqa: E402
from app import downtime  # noqa: E402
from app import structures  # noqa: E402


from mcp_server.auth import build_auth  # noqa: E402

mcp = FastMCP("MOW Tracker", auth=build_auth())


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_projects() -> list[dict]:
    """List all VRS MOW projects with basic stats."""
    projects = storage.list_projects()
    result = []
    for p in projects:
        total = sum(e.ties for e in p.daily_log)
        goal = p.project.goal_ties
        pct = round(total / goal * 100, 1) if goal else None
        result.append({
            "id": p.project.id,
            "name": p.project.name,
            "kind": p.project.kind,
            "status": p.project.status,
            "deadline": str(p.project.deadline) if p.project.deadline else None,
            "goal_ties": goal,
            "total_ties": total,
            "percent_complete": pct,
            "locations": [{"id": loc.id, "name": loc.name} for loc in p.locations],
        })
    return result


@mcp.tool()
def get_project_summary(project_id: str) -> dict:
    """Get computed summary stats for a project (totals, progress, projected finish)."""
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    summary = build_summary(project)
    return {k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in summary.items()}


def _loc_name(project, loc_id: Optional[str]) -> Optional[str]:
    """Resolve a Location id to its display name (or None / the raw id if unknown)."""
    if not loc_id:
        return None
    loc = next((loc for loc in project.locations if loc.id == loc_id), None)
    return loc.name if loc else loc_id


@mcp.tool()
def get_daily_log(project_id: str) -> list[dict]:
    """Get full daily tie installation log for a project."""
    project = storage.load_project(project_id)
    if not project:
        return [{"error": f"Project '{project_id}' not found"}]
    return [
        {
            "date": str(e.date),
            "day": e.day,
            "ties": e.ties,
            "relay_ties": e.relay_ties,
            "new_ties": e.ties - e.relay_ties,
            "vs_target": e.vs_target,
            "running_total": e.running_total,
            "remaining": e.remaining,
            "location": e.location,
            "location_name": _loc_name(project, e.location),
            "tracks": [{"track": t.track, "ties": t.ties, "relay_ties": t.relay_ties} for t in e.tracks],
        }
        for e in project.daily_log
    ]


@mcp.tool()
def get_downtime_log(project_id: str) -> list[dict]:
    """Get full equipment downtime log for a project."""
    project = storage.load_project(project_id)
    if not project:
        return [{"error": f"Project '{project_id}' not found"}]
    return [
        {
            "date": str(e.date),
            "machine": e.machine,
            "down_at": e.down_at,
            "resumed": e.resumed,
            "duration_minutes": e.duration_minutes,
            "notes": e.notes,
        }
        for e in project.equipment_downtime
    ]


@mcp.tool()
def add_daily_count(project_id: str, date: str, ties: int, relay_ties: int = 0,
                    track: Optional[str] = None, location: Optional[str] = None) -> dict:
    """
    Log a day's plain-track tie installation count.

    Args:
        project_id: Project ID (e.g. 'WACR_CRD')
        date: Date in YYYY-MM-DD format
        ties: Total ties installed that day (new + relay)
        relay_ties: How many of those were relay (reclaimed) ties, a subset of `ties` (default 0).
                    New ties = ties - relay_ties. Switch timbers are tracked separately via add_switch.
        track: Optional track label (e.g. 'Track 2', 'Siding 3'). Omit for main-line work.
               To record a day worked across multiple tracks, call this once per track with the
               same date and different track labels, the ties add into that day's total and a
               per-track breakdown is kept.
        location: Optional worksite within a company line (id or name, e.g. 'St. Johnsbury').
                  It must already exist, create it first with add_location. A day is worked at a
                  single location. Omit for main-line / unassigned work.
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}

    try:
        entry_date = _date.fromisoformat(date)
    except ValueError:
        return {"error": "Invalid date, expected YYYY-MM-DD"}

    try:
        entry = storage.record_daily_count(project, entry_date, ties, relay_ties, track, location)
    except ValueError as e:
        return {"error": str(e)}
    storage.save_project(project)

    return {
        "date": str(entry.date),
        "day": entry.day,
        "ties": entry.ties,
        "relay_ties": entry.relay_ties,
        "new_ties": entry.ties - entry.relay_ties,
        "vs_target": entry.vs_target,
        "running_total": entry.running_total,
        "remaining": entry.remaining,
        "location": entry.location,
        "location_name": _loc_name(project, entry.location),
        "tracks": [{"track": t.track, "ties": t.ties, "relay_ties": t.relay_ties} for t in entry.tracks],
    }


def _downtime_dict(entry) -> dict:
    return {
        "date": str(entry.date),
        "machine": entry.machine,
        "down_at": entry.down_at,
        "resumed": entry.resumed,
        "duration_minutes": entry.duration_minutes,
        "notes": entry.notes,
    }


@mcp.tool()
def add_downtime(
    project_id: str,
    date: str,
    machine: str,
    down_at: Optional[str] = None,
    resumed: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """
    Log an equipment downtime incident.

    Args:
        project_id: Project ID (e.g. '942')
        date: Date in YYYY-MM-DD format
        machine: Equipment name (e.g. 'Broom', 'Tie Inserter')
        down_at: Time equipment went down, HH:MM 24-hour format (optional)
        resumed: Time equipment resumed, HH:MM 24-hour format (optional)
        notes: Description of the issue (optional)
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    try:
        entry_date = _date.fromisoformat(date)
    except ValueError:
        return {"error": "Invalid date, expected YYYY-MM-DD"}
    try:
        entry = downtime.add_downtime(project, entry_date, machine, down_at, resumed, notes)
    except ValueError as e:
        return {"error": str(e)}
    storage.save_project(project)
    return _downtime_dict(entry)


@mcp.tool()
def update_daily_count(project_id: str, date: str, new_ties: int,
                       relay_ties: Optional[int] = None,
                       track: Optional[str] = None,
                       location: Optional[str] = None) -> dict:
    """
    Correct the tie count for an existing log entry. Recalculates running_total,
    remaining, and vs_target for all entries in chronological order.

    Args:
        project_id: Project ID (e.g. 'WACR_CRD')
        date: Date of the entry to correct, YYYY-MM-DD format
        new_ties: The correct number of ties (the day total, or, if `track` is given,
                  that track's portion; the day total is re-derived from its tracks)
        relay_ties: Optionally correct how many of those were relay (reclaimed) ties
                    (subset of new_ties; omit to leave unchanged)
        track: When the day is split across tracks, the track label to correct (e.g. 'Track 2').
               Omit for a single (untracked) day.
        location: Move the whole day to another worksite (id or name; must already exist).
                  Pass an empty string to clear it; omit to leave it unchanged.
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}

    try:
        entry_date = _date.fromisoformat(date)
    except ValueError:
        return {"error": "Invalid date, expected YYYY-MM-DD"}

    try:
        updated, old_ties = storage.update_daily_count(project, entry_date, new_ties, relay_ties, track, location)
    except ValueError as e:
        return {"error": str(e)}
    storage.save_project(project)

    return {
        "date": str(updated.date),
        "day": updated.day,
        "old_ties": old_ties,
        "new_ties": updated.ties,
        "relay_ties": updated.relay_ties,
        "vs_target": updated.vs_target,
        "running_total": updated.running_total,
        "remaining": updated.remaining,
        "location": updated.location,
        "location_name": _loc_name(project, updated.location),
        "tracks": [{"track": t.track, "ties": t.ties, "relay_ties": t.relay_ties} for t in updated.tracks],
    }


@mcp.tool()
def update_project(
    project_id: str,
    goal_ties: Optional[int] = None,
    deadline: Optional[str] = None,
    daily_target: Optional[int] = None,
) -> dict:
    """
    Update goal_ties, deadline, or daily_target on an existing project.
    Recalculates vs_target and remaining on all log entries after any change.

    Args:
        project_id: Project ID (e.g. '942')
        goal_ties: New total tie goal (optional)
        deadline: New deadline in YYYY-MM-DD format (optional)
        daily_target: New daily tie target (optional)
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    if goal_ties is None and deadline is None and daily_target is None:
        return {"error": "No fields provided; specify at least one of: goal_ties, deadline, daily_target"}
    parsed_deadline = None
    if deadline is not None:
        try:
            parsed_deadline = _date.fromisoformat(deadline)
        except ValueError:
            return {"error": "Invalid deadline, expected YYYY-MM-DD"}
    try:
        storage.update_project_meta(project, goal_ties=goal_ties, deadline=parsed_deadline,
                                    daily_target=daily_target)
    except ValueError as e:
        return {"error": str(e)}
    storage.save_project(project)
    return {
        "id": project.project.id,
        "goal_ties": project.project.goal_ties,
        "deadline": str(project.project.deadline),
        "daily_target": project.project.daily_target,
        "log_entries_recalculated": len(project.daily_log),
    }


@mcp.tool()
def update_downtime(
    project_id: str,
    date: str,
    machine: str,
    new_down_at: Optional[str] = None,
    new_resumed: Optional[str] = None,
    new_notes: Optional[str] = None,
    match_down_at: Optional[str] = None,
) -> dict:
    """
    Edit an existing equipment downtime entry. Recalculates duration_minutes if
    down_at or resumed changes. Pass an empty string for new_notes to clear it.

    Args:
        project_id: Project ID (e.g. '942')
        date: Date of the entry to edit, YYYY-MM-DD format
        machine: Equipment name to identify which entry to edit
        new_down_at: Updated down time, HH:MM 24-hour format (optional)
        new_resumed: Updated resume time, HH:MM 24-hour format (optional)
        new_notes: Updated notes text (optional; pass empty string to clear)
        match_down_at: When several entries share the date and machine, the down_at of the
                       one to edit (optional)
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    try:
        entry_date = _date.fromisoformat(date)
    except ValueError:
        return {"error": "Invalid date, expected YYYY-MM-DD"}
    try:
        entry = downtime.update_downtime(project, entry_date, machine, down_at=new_down_at,
                                         resumed=new_resumed, notes=new_notes,
                                         match_down_at=match_down_at)
    except (ValueError, LookupError) as e:
        return {"error": str(e)}
    storage.save_project(project)
    return _downtime_dict(entry)


@mcp.tool()
def delete_downtime(
    project_id: str,
    date: str,
    machine: str,
    down_at: Optional[str] = None,
) -> dict:
    """
    Delete an equipment downtime entry. If multiple entries exist for the same
    date and machine (e.g. a duplicate), provide down_at to target a specific one.

    Args:
        project_id: Project ID (e.g. '942')
        date: Date of the entry, YYYY-MM-DD format
        machine: Equipment name
        down_at: Down time HH:MM to disambiguate when multiple entries match (optional)
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    try:
        entry_date = _date.fromisoformat(date)
    except ValueError:
        return {"error": "Invalid date, expected YYYY-MM-DD"}
    try:
        target = downtime.delete_downtime(project, entry_date, machine, down_at)
    except (ValueError, LookupError) as e:
        return {"error": str(e)}
    storage.save_project(project)
    return {"deleted": _downtime_dict(target)}


@mcp.tool()
def create_project(
    project_id: str,
    name: str,
    kind: str = "company",
    line: Optional[str] = None,
    job: str = "",
    base: str = "",
    deadline: Optional[str] = None,
    goal_ties: Optional[int] = None,
    daily_target: int = 350,
) -> dict:
    """
    Create a new project. A new project starts active (the single active job),
    demoting any previously-active project to complete.

    Args:
        project_id: Unique ID: work-order number for sponsored jobs (e.g. '942') or
                    line abbreviation for company line work (e.g. 'WACR_CRD')
        name: Display name (e.g. 'Project 942' or 'WACR Connecticut River Division')
        kind: 'sponsored' (state or Amtrak funded, has a tie goal) or 'company' (in-house
              railroad-line work, usually no goal). Default 'company'.
        line: Railroad line for company projects (e.g. 'WACR_CRD'); optional
        job: Job description (optional)
        base: Base of operations (optional)
        deadline: Deadline date YYYY-MM-DD (optional)
        goal_ties: Total tie goal (optional; omit for open-ended company work)
        daily_target: Daily tie target for plain-track ties (default 350)
    """
    parsed_deadline = None
    if deadline:
        try:
            parsed_deadline = _date.fromisoformat(deadline)
        except ValueError:
            return {"error": "Invalid deadline, expected YYYY-MM-DD"}
    try:
        project, demoted = storage.create_project(
            project_id, name, kind=kind, line=line, job=job, base=base,
            deadline=parsed_deadline, goal_ties=goal_ties, daily_target=daily_target)
    except ValueError as e:
        return {"error": str(e)}
    meta = project.project
    return {
        "id": meta.id,
        "name": meta.name,
        "kind": meta.kind,
        "line": meta.line,
        "job": meta.job,
        "base": meta.base,
        "deadline": str(meta.deadline) if meta.deadline else None,
        "goal_ties": meta.goal_ties,
        "daily_target": meta.daily_target,
        "status": meta.status,
        "demoted_to_complete": demoted,
        "created": str(meta.created),
    }


@mcp.tool()
def set_status(project_id: str, status: str) -> dict:
    """
    Set a project's lifecycle status.

    Statuses:
      - 'active': the current working job. Only ONE project may be active at a time;
                  setting one active demotes any other active project to 'complete'.
                  The website loads the active project by default and the weekly report
                  covers it.
      - 'complete': finished work. Stays visible in the UI and can still be reported on
                    demand.
      - 'archived': hidden from the main view (end-of-season cleanup).

    Args:
        project_id: Project ID (e.g. '942')
        status: One of 'active', 'complete', 'archived'
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    try:
        demoted = storage.set_status(project, status)
    except ValueError as e:
        return {"error": str(e)}
    storage.save_project(project)
    return {
        "id": project_id,
        "status": status,
        "demoted_to_complete": demoted,
    }


# ── Switches & derails ──────────────────────────────────────────────────────────

def _timber_dicts(entity) -> list[dict]:
    return [
        {"length": t.length, "planned": t.planned, "actual": t.actual, "head_block": t.head_block}
        for t in entity.timbers
    ]


def _switch_dict(project, s) -> dict:
    planned, actual = structures.entity_totals(s)
    return {
        "id": s.id, "name": s.name, "date": str(s.date),
        "timbers": _timber_dicts(s), "total_planned": planned, "total_actual": actual,
        "location": s.location, "location_name": _loc_name(project, s.location),
        "notes": s.notes,
    }


def _derail_dict(project, d) -> dict:
    planned, actual = structures.entity_totals(d)
    return {
        "id": d.id, "name": d.name, "date": str(d.date), "derail_type": d.derail_type,
        "timbers": _timber_dicts(d), "total_planned": planned, "total_actual": actual,
        "location": d.location, "location_name": _loc_name(project, d.location),
        "notes": d.notes,
    }


@mcp.tool()
def get_switches(project_id: str) -> list[dict]:
    """Get all switches for a project, each with its timber breakdown and planned/actual totals."""
    project = storage.load_project(project_id)
    if not project:
        return [{"error": f"Project '{project_id}' not found"}]
    return [_switch_dict(project, s) for s in project.switches]


@mcp.tool()
def get_derails(project_id: str) -> list[dict]:
    """Get all derails for a project, each with its timber breakdown and planned/actual totals."""
    project = storage.load_project(project_id)
    if not project:
        return [{"error": f"Project '{project_id}' not found"}]
    return [_derail_dict(project, d) for d in project.derails]


@mcp.tool()
def add_switch(project_id: str, name: str, date: str, timbers: list[Timber],
               notes: Optional[str] = None, location: Optional[str] = None) -> dict:
    """
    Add a switch with its timber breakdown.

    Args:
        project_id: Project ID (e.g. 'WACR_CRD')
        name: Switch name/location (e.g. 'North Main Switch', 'Switch to NH')
        date: Date completed, YYYY-MM-DD
        timbers: One row per length, e.g.
                 [{"length": 9, "planned": 6, "actual": 11},
                  {"length": 16, "planned": 2, "actual": 2, "head_block": true}]
                 planned/actual default to 0 (a dash on the source sheet = 0).
        notes: Optional note
        location: Optional worksite within a company line (id or name; must already exist;
                  create it first with add_location). Omit for unassigned.
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    try:
        d = _date.fromisoformat(date)
    except ValueError:
        return {"error": "Invalid date, expected YYYY-MM-DD"}
    if not timbers:
        return {"error": "At least one timber row is required"}
    try:
        sw = structures.add_switch(project, name, d, timbers, notes=notes, location=location)
    except ValueError as e:
        return {"error": str(e)}
    storage.save_project(project)
    return _switch_dict(project, sw)


@mcp.tool()
def update_switch(project_id: str, name: str, date: Optional[str] = None,
                  new_name: Optional[str] = None, timbers: Optional[list[Timber]] = None,
                  notes: Optional[str] = None, location: Optional[str] = None) -> dict:
    """
    Update a switch. Identify it by name (or id); if several switches share the name,
    pass `date` to target one. Providing `timbers` REPLACES the whole timber list.

    Args:
        project_id: Project ID
        name: Switch name (or id) to find
        date: YYYY-MM-DD to disambiguate when multiple switches share the name
        new_name: Rename the switch (optional)
        timbers: Full replacement timber list (optional; same shape as add_switch)
        notes: New note (optional; pass empty string to clear)
        location: Reassign to a worksite (id or name; must already exist). Empty string clears it.
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    on_date = None
    if date:
        try:
            on_date = _date.fromisoformat(date)
        except ValueError:
            return {"error": "Invalid date, expected YYYY-MM-DD"}
    try:
        sw = structures.update_switch(project, name, on_date, new_name=new_name,
                                      timbers=timbers, notes=notes, location=location)
    except (ValueError, LookupError) as e:
        return {"error": str(e)}
    storage.save_project(project)
    return _switch_dict(project, sw)


@mcp.tool()
def delete_switch(project_id: str, name: str, date: Optional[str] = None) -> dict:
    """
    Delete a switch. Identify by name (or id); pass `date` to disambiguate when
    multiple switches share the name.
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    on_date = None
    if date:
        try:
            on_date = _date.fromisoformat(date)
        except ValueError:
            return {"error": "Invalid date, expected YYYY-MM-DD"}
    try:
        sw = structures.delete_switch(project, name, on_date)
    except LookupError as e:
        return {"error": str(e)}
    storage.save_project(project)
    return {"deleted": _switch_dict(project, sw)}


@mcp.tool()
def add_derail(project_id: str, name: str, date: str, timbers: list[Timber],
               derail_type: Optional[str] = None, notes: Optional[str] = None,
               location: Optional[str] = None) -> dict:
    """
    Add a derail with its timber breakdown (head blocks for a stationary derail).

    Args:
        project_id: Project ID (e.g. 'WACR_CRD')
        name: Derail name/location (e.g. 'South Derail Head Blocks')
        date: Date completed, YYYY-MM-DD
        timbers: One row per length (same shape as add_switch). For a stationary
                 derail these are typically head blocks (set "head_block": true).
                 A portable derail may have none.
        derail_type: 'stationary', 'portable', or 'switch' (switch-to-nowhere); optional
        notes: Optional note
        location: Optional worksite within a company line (id or name; must already exist;
                  create it first with add_location). Omit for unassigned.
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    try:
        d = _date.fromisoformat(date)
    except ValueError:
        return {"error": "Invalid date, expected YYYY-MM-DD"}
    try:
        dr = structures.add_derail(project, name, d, timbers or [], derail_type=derail_type,
                                   notes=notes, location=location)
    except ValueError as e:
        return {"error": str(e)}
    storage.save_project(project)
    return _derail_dict(project, dr)


@mcp.tool()
def update_derail(project_id: str, name: str, date: Optional[str] = None,
                  new_name: Optional[str] = None, derail_type: Optional[str] = None,
                  timbers: Optional[list[Timber]] = None, notes: Optional[str] = None,
                  location: Optional[str] = None) -> dict:
    """
    Update a derail. Identify by name (or id); pass `date` to disambiguate.
    Providing `timbers` REPLACES the whole timber list. Pass `location` (id or name; must
    already exist) to reassign it; an empty string clears it.
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    on_date = None
    if date:
        try:
            on_date = _date.fromisoformat(date)
        except ValueError:
            return {"error": "Invalid date, expected YYYY-MM-DD"}
    try:
        dr = structures.update_derail(project, name, on_date, new_name=new_name,
                                      derail_type=derail_type, timbers=timbers,
                                      notes=notes, location=location)
    except (ValueError, LookupError) as e:
        return {"error": str(e)}
    storage.save_project(project)
    return _derail_dict(project, dr)


@mcp.tool()
def delete_derail(project_id: str, name: str, date: Optional[str] = None) -> dict:
    """Delete a derail. Identify by name (or id); pass `date` to disambiguate."""
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    on_date = None
    if date:
        try:
            on_date = _date.fromisoformat(date)
        except ValueError:
            return {"error": "Invalid date, expected YYYY-MM-DD"}
    try:
        dr = structures.delete_derail(project, name, on_date)
    except LookupError as e:
        return {"error": str(e)}
    storage.save_project(project)
    return {"deleted": _derail_dict(project, dr)}


# ── Locations (managed worksites within a company line) ──────────────────────────

def _location_dict(project, loc) -> dict:
    days, sw, dr = structures.location_refs(project, loc.id)
    return {
        "id": loc.id, "name": loc.name, "notes": loc.notes,
        "tie_days": days, "switches": sw, "derails": dr,
    }


@mcp.tool()
def get_locations(project_id: str) -> list[dict]:
    """Get the worksites (locations) on a company line, each with how many tie days,
    switches, and derails are logged there."""
    project = storage.load_project(project_id)
    if not project:
        return [{"error": f"Project '{project_id}' not found"}]
    return [_location_dict(project, loc) for loc in project.locations]


@mcp.tool()
def add_location(project_id: str, name: str, notes: Optional[str] = None) -> dict:
    """
    Add a worksite (location) to a company line, a city/town/yard/siding such as
    'St. Johnsbury'. Locations are a managed list; work must reference one that exists.

    Args:
        project_id: Company line project ID (e.g. 'WACR_CRD')
        name: Display name (e.g. 'St. Johnsbury'); the id is a slug derived from it
        notes: Optional note
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    try:
        loc = structures.add_location(project, name, notes=notes)
    except ValueError as e:
        return {"error": str(e)}
    storage.save_project(project)
    return _location_dict(project, loc)


@mcp.tool()
def update_location(project_id: str, location: str, new_name: Optional[str] = None,
                    notes: Optional[str] = None) -> dict:
    """
    Rename a location or edit its note. Identify it by id or current name. The id stays
    stable on rename, so work tagged to it keeps pointing at it.

    Args:
        project_id: Company line project ID (e.g. 'WACR_CRD')
        location: Location id or current name to update
        new_name: New display name (optional)
        notes: New note (optional; pass empty string to clear)
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    if new_name is None and notes is None:
        return {"error": "No fields provided; specify at least one of: new_name, notes"}
    try:
        loc = structures.update_location(project, location, new_name=new_name, notes=notes)
    except ValueError as e:
        return {"error": str(e)}
    storage.save_project(project)
    return _location_dict(project, loc)


@mcp.tool()
def delete_location(project_id: str, location: str) -> dict:
    """
    Delete a location. Refused if any tie day, switch, or derail still references it;
    reassign or correct those first (update_daily_count / update_switch / update_derail).

    Args:
        project_id: Company line project ID (e.g. 'WACR_CRD')
        location: Location id or name to delete
    """
    project = storage.load_project(project_id)
    if not project:
        return {"error": f"Project '{project_id}' not found"}
    try:
        loc = structures.delete_location(project, location)
    except ValueError as e:
        return {"error": str(e)}
    storage.save_project(project)
    return {"deleted": {"id": loc.id, "name": loc.name}}


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8001, path="/mcp")
