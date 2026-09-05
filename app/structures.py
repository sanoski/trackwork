"""Service layer for switch and derail records, shared by the MCP tools and the CLI.

Switches and derails have the same shape: a named, dated entity with a list of
Timber rows. They live in separate collections on the Project and render with
different visuals, but their creation and lookup logic is identical and lives
here so the MCP server and the CLI can never drift apart.
"""

from __future__ import annotations

import re
from datetime import date as _date
from typing import Optional

from .models import Derail, Location, Project, Switch, Timber


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "item"


def unique_id(existing_ids: set[str], base: str) -> str:
    """Return `base`, or `base-2`, `base-3`, ... if it's already taken."""
    if base not in existing_ids:
        return base
    n = 2
    while f"{base}-{n}" in existing_ids:
        n += 1
    return f"{base}-{n}"


def entity_totals(entity) -> tuple[int, int]:
    """(total planned, total actual) across a switch's or derail's timbers."""
    return (sum(t.planned for t in entity.timbers),
            sum(t.actual for t in entity.timbers))


def coerce_timbers(timbers) -> list[Timber]:
    """Accept Timber instances or plain dicts (from MCP/JSON) and return Timbers."""
    return [t if isinstance(t, Timber) else Timber.model_validate(t) for t in timbers]


def find_entity(entities: list, ident: str, on_date: Optional[_date] = None):
    """Find a switch/derail by id, or by name (with `on_date` to disambiguate when
    several share a name). Returns (entity, None) on success or (None, error_message)."""
    for e in entities:
        if e.id == ident:
            return e, None
    matches = [e for e in entities if e.name == ident]
    if on_date is not None:
        matches = [e for e in matches if e.date == on_date]
    if not matches:
        suffix = f" on {on_date}" if on_date else ""
        return None, f"no entry found matching '{ident}'{suffix}"
    if len(matches) > 1:
        dates = ", ".join(str(e.date) for e in matches)
        return None, f"multiple entries named '{ident}' ({dates}), specify the date to target one"
    return matches[0], None


def add_switch(project: Project, name: str, on_date: _date, timbers,
               notes: Optional[str] = None, location: Optional[str] = None) -> Switch:
    sw = Switch(
        id=unique_id({s.id for s in project.switches}, slugify(name)),
        name=name, date=on_date, timbers=coerce_timbers(timbers),
        location=resolve_location(project, location), notes=notes,
    )
    project.switches.append(sw)
    project.switches.sort(key=lambda s: (s.date, s.id))
    return sw


def add_derail(project: Project, name: str, on_date: _date, timbers,
               derail_type: Optional[str] = None, notes: Optional[str] = None,
               location: Optional[str] = None) -> Derail:
    dr = Derail(
        id=unique_id({d.id for d in project.derails}, slugify(name)),
        name=name, date=on_date, derail_type=derail_type,
        timbers=coerce_timbers(timbers),
        location=resolve_location(project, location), notes=notes,
    )
    project.derails.append(dr)
    project.derails.sort(key=lambda d: (d.date, d.id))
    return dr


# ── Locations (managed worksites within a company line) ─────────────────────────
# A Location is a named sub-entity with a stable slug id, modeled like switches/derails.
# Work items (daily log, switches, derails) reference a location by id, so renaming a
# location's display name never re-tags work. Pure functions, callers persist via storage.

def find_location(project: Project, ident: str):
    """Find a Location by id (exact) or name (case-insensitive). Returns (loc, None) on
    success or (None, error_message)."""
    for loc in project.locations:
        if loc.id == ident:
            return loc, None
    matches = [loc for loc in project.locations if loc.name.lower() == str(ident).strip().lower()]
    if not matches:
        return None, f"no location matching '{ident}', create it first with add_location"
    if len(matches) > 1:
        ids = ", ".join(loc.id for loc in matches)
        return None, f"multiple locations named '{ident}' ({ids}), use the id"
    return matches[0], None


def resolve_location(project: Project, token: Optional[str]) -> Optional[str]:
    """Map a location token (id or name) to a Location id. Blank/None → None (main line /
    unassigned). Raises ValueError if a non-blank token matches no managed location, this
    is what makes locations a managed list (you must create one before logging to it)."""
    if token is None or not str(token).strip():
        return None
    loc, err = find_location(project, str(token))
    if err:
        raise ValueError(err)
    return loc.id


def location_refs(project: Project, loc_id: str) -> tuple[int, int, int]:
    """(tie days, switches, derails) that reference this location id."""
    return (
        sum(1 for e in project.daily_log if e.location == loc_id),
        sum(1 for s in project.switches if s.location == loc_id),
        sum(1 for d in project.derails if d.location == loc_id),
    )


def add_location(project: Project, name: str, notes: Optional[str] = None) -> Location:
    name = (name or "").strip()
    if not name:
        raise ValueError("location name is required")
    if any(loc.name.lower() == name.lower() for loc in project.locations):
        raise ValueError(f"a location named '{name}' already exists")
    loc = Location(
        id=unique_id({loc.id for loc in project.locations}, slugify(name)),
        name=name, notes=notes,
    )
    project.locations.append(loc)
    project.locations.sort(key=lambda loc: loc.name.lower())
    return loc


def update_location(project: Project, ident: str, new_name: Optional[str] = None,
                    notes: Optional[str] = None) -> Location:
    """Rename a location or edit its notes. The slug `id` stays stable on rename so work
    items keep pointing at it. Pass an empty string for `notes` to clear it."""
    loc, err = find_location(project, ident)
    if err:
        raise ValueError(err)
    if new_name is not None:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("new name cannot be empty")
        if any(o is not loc and o.name.lower() == new_name.lower() for o in project.locations):
            raise ValueError(f"a location named '{new_name}' already exists")
        loc.name = new_name
    if notes is not None:
        loc.notes = notes or None
    project.locations.sort(key=lambda loc: loc.name.lower())
    return loc


def delete_location(project: Project, ident: str) -> Location:
    """Remove a location. Refuses (ValueError) if any work still references it, to avoid
    orphaning records, reassign or correct those first."""
    loc, err = find_location(project, ident)
    if err:
        raise ValueError(err)
    days, sw, dr = location_refs(project, loc.id)
    if days or sw or dr:
        parts = []
        if days:
            parts.append(f"{days} tie day{'s' if days != 1 else ''}")
        if sw:
            parts.append(f"{sw} switch{'es' if sw != 1 else ''}")
        if dr:
            parts.append(f"{dr} derail{'s' if dr != 1 else ''}")
        raise ValueError(
            f"location '{loc.name}' is still referenced by {', '.join(parts)}, "
            f"reassign or correct them first")
    project.locations.remove(loc)
    return loc


def scope_to_location(project: Project, loc_id: str) -> Project:
    """Return a location-scoped copy of a company line for presentation/reporting:
    daily_log / switches / derails filtered to one worksite, `running_total` and
    `remaining` recomputed cumulatively for that subset, and equipment_downtime dropped
    (it is a line-level log, not located). The stored project stays line-wide, this is a
    derived view that does not persist. Server mirror of the portal's app.js
    `filterProjectByLocation`, so the PDF report and the web worksite view agree."""
    meta = project.project
    days = sorted(
        [e.model_copy(deep=True) for e in project.daily_log if e.location == loc_id],
        key=lambda e: e.date,
    )
    running = 0
    for e in days:
        running += e.ties
        e.running_total = running
        e.remaining = (meta.goal_ties - running) if meta.goal_ties is not None else None
    return Project(
        project=meta,
        locations=project.locations,
        daily_log=days,
        switches=[s for s in project.switches if s.location == loc_id],
        derails=[d for d in project.derails if d.location == loc_id],
        equipment_downtime=[],
    )


# ── Editing switches and derails (shared by the web API, the MCP server, and the CLI) ──
# Pure functions like the rest of this module: they mutate the loaded Project and the caller
# persists with storage.save_project(). Not found (or an ambiguous name) raises LookupError;
# invalid input raises ValueError.

def get_entity(entities: list, ident: str, on_date: Optional[_date] = None):
    """find_entity that raises LookupError instead of returning an error message."""
    entity, err = find_entity(entities, ident, on_date)
    if err:
        raise LookupError(err)
    return entity


def update_switch(project: Project, ident: str, on_date: Optional[_date] = None, *,
                  new_name: Optional[str] = None, timbers=None,
                  notes: Optional[str] = None, location: Optional[str] = None) -> Switch:
    """Edit a switch found by id or name (`on_date` disambiguates a shared name). `timbers`
    replaces the whole list. An empty string clears notes or location."""
    sw = get_entity(project.switches, ident, on_date)
    if new_name is None and timbers is None and notes is None and location is None:
        raise ValueError("No fields provided; specify at least one of: new_name, timbers, notes, location")
    if new_name is not None:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("name cannot be empty")
        sw.name = new_name
    if timbers is not None:
        sw.timbers = coerce_timbers(timbers)
    if notes is not None:
        sw.notes = notes or None
    if location is not None:
        sw.location = resolve_location(project, location)
    project.switches.sort(key=lambda s: (s.date, s.id))
    return sw


def delete_switch(project: Project, ident: str, on_date: Optional[_date] = None) -> Switch:
    sw = get_entity(project.switches, ident, on_date)
    project.switches.remove(sw)
    return sw


def update_derail(project: Project, ident: str, on_date: Optional[_date] = None, *,
                  new_name: Optional[str] = None, derail_type: Optional[str] = None,
                  timbers=None, notes: Optional[str] = None,
                  location: Optional[str] = None) -> Derail:
    """Edit a derail found by id or name. `timbers` replaces the whole list. An empty string
    clears derail_type, notes, or location."""
    dr = get_entity(project.derails, ident, on_date)
    if (new_name is None and derail_type is None and timbers is None
            and notes is None and location is None):
        raise ValueError(
            "No fields provided; specify at least one of: new_name, derail_type, timbers, notes, location")
    if new_name is not None:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("name cannot be empty")
        dr.name = new_name
    if derail_type is not None:
        dr.derail_type = derail_type or None
    if timbers is not None:
        dr.timbers = coerce_timbers(timbers)
    if notes is not None:
        dr.notes = notes or None
    if location is not None:
        dr.location = resolve_location(project, location)
    project.derails.sort(key=lambda d: (d.date, d.id))
    return dr


def delete_derail(project: Project, ident: str, on_date: Optional[_date] = None) -> Derail:
    dr = get_entity(project.derails, ident, on_date)
    project.derails.remove(dr)
    return dr
