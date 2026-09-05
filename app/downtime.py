"""Equipment downtime entries on a Project.

Pure functions, no I/O: they mutate the loaded Project and the caller persists with
storage.save_project(). The web API, the MCP server, and the CLI all call these, so the
duration math and the "which entry did you mean" rules live in exactly one place.
Not found raises LookupError; invalid or ambiguous input raises ValueError.
"""
from __future__ import annotations

from datetime import date as _date
from typing import Optional

from .models import EquipmentDowntime, Project


def calc_duration(down_at: Optional[str], resumed: Optional[str]) -> Optional[int]:
    """Minutes between two HH:MM times on the same day, or None when either is missing or
    the pair does not make sense (resumed before down)."""
    if not down_at or not resumed:
        return None
    try:
        dh, dm = map(int, down_at.split(":"))
        rh, rm = map(int, resumed.split(":"))
        minutes = (rh * 60 + rm) - (dh * 60 + dm)
        return minutes if minutes > 0 else None
    except (ValueError, AttributeError):
        return None


def find_downtime(project: Project, on_date: _date, machine: str,
                  down_at: Optional[str] = None) -> EquipmentDowntime:
    """Locate one entry by date and machine. When several match (a duplicate log), pass
    `down_at` to pick one; otherwise the ambiguity is an error rather than a guess."""
    matches = [e for e in project.equipment_downtime
               if e.date == on_date and e.machine == machine]
    if not matches:
        raise LookupError(f"No downtime entry found for {on_date} / {machine}")
    if down_at is not None:
        target = next((e for e in matches if e.down_at == down_at), None)
        if target is None:
            raise LookupError(f"No entry found for {on_date} / {machine} with down_at={down_at}")
        return target
    if len(matches) > 1:
        times = ", ".join(e.down_at or "?" for e in matches)
        raise ValueError(
            f"Multiple entries match {on_date} / {machine} ({times}); provide down_at to target one")
    return matches[0]


def add_downtime(project: Project, on_date: _date, machine: str,
                 down_at: Optional[str] = None, resumed: Optional[str] = None,
                 notes: Optional[str] = None) -> EquipmentDowntime:
    machine = (machine or "").strip()
    if not machine:
        raise ValueError("machine is required")
    entry = EquipmentDowntime(
        date=on_date, machine=machine, down_at=down_at or None, resumed=resumed or None,
        duration_minutes=calc_duration(down_at, resumed), notes=notes or None,
    )
    project.equipment_downtime.append(entry)
    project.equipment_downtime.sort(key=lambda e: e.date)
    return entry


def update_downtime(project: Project, on_date: _date, machine: str, *,
                    down_at: Optional[str] = None, resumed: Optional[str] = None,
                    notes: Optional[str] = None,
                    match_down_at: Optional[str] = None) -> EquipmentDowntime:
    """Edit an entry. Duration is recomputed when either time changes. An empty string clears
    notes. `match_down_at` selects one entry when several share the date and machine."""
    entry = find_downtime(project, on_date, machine, match_down_at)
    if down_at is None and resumed is None and notes is None:
        raise ValueError("No fields provided; specify at least one of: down_at, resumed, notes")
    if down_at is not None:
        entry.down_at = down_at
    if resumed is not None:
        entry.resumed = resumed
    if notes is not None:
        entry.notes = notes or None
    if down_at is not None or resumed is not None:
        entry.duration_minutes = calc_duration(entry.down_at, entry.resumed)
    return entry


def delete_downtime(project: Project, on_date: _date, machine: str,
                    down_at: Optional[str] = None) -> EquipmentDowntime:
    entry = find_downtime(project, on_date, machine, down_at)
    project.equipment_downtime.remove(entry)
    return entry
