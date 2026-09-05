import json
import os
import re
import threading
from datetime import date
from pathlib import Path
from typing import Optional

from .config import settings
from .models import DailyLogEntry, Project, ProjectMeta, TrackSplit, User
from .structures import resolve_location

_file_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_lock(path: str) -> threading.Lock:
    with _locks_lock:
        if path not in _file_locks:
            _file_locks[path] = threading.Lock()
        return _file_locks[path]


def _atomic_write(path: Path, data: object) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, path)


def _ensure_dirs() -> None:
    settings.projects_dir.mkdir(parents=True, exist_ok=True)
    settings.archived_dir.mkdir(parents=True, exist_ok=True)


def load_project(project_id: str) -> Optional[Project]:
    _ensure_dirs()
    for directory in [settings.projects_dir, settings.archived_dir]:
        path = directory / f"{project_id}.json"
        if path.exists():
            lock = _get_lock(str(path))
            with lock:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            return Project.model_validate(data)
    return None


def save_project(project: Project) -> None:
    _ensure_dirs()
    is_archived = project.project.status == "archived"
    directory = settings.archived_dir if is_archived else settings.projects_dir
    other = settings.projects_dir if is_archived else settings.archived_dir
    path = directory / f"{project.project.id}.json"
    lock = _get_lock(str(path))
    with lock:
        _atomic_write(path, project.model_dump(mode="json"))
    # A status change can move a project between projects_dir and archived_dir.
    # Remove any stale copy in the other directory so load_project can't find both.
    stale = other / f"{project.project.id}.json"
    if stale.exists():
        stale.unlink()


# ── Daily-count writes (single source of truth for all three entry points) ──────
# The web API, the MCP server, and the CLI all funnel daily-tie writes through these
# so the "recalc running_total/remaining on every write" rule lives in exactly one
# place. Callers load the project, call one of these, then call save_project().

def recalc_running_totals(project: Project) -> None:
    """Recompute vs_target, running_total and remaining across the whole daily log in
    date order. There is one log entry per date (a day's per-track breakdown lives in
    that entry's `tracks` list), so day totals, and these derived fields, are unchanged
    by track tagging. Call after every daily-count write."""
    project.daily_log.sort(key=lambda e: e.date)
    goal = project.project.goal_ties
    target = project.project.daily_target
    running = 0
    for e in project.daily_log:
        running += e.ties
        e.vs_target = e.ties - target
        e.running_total = running
        e.remaining = (goal - running) if goal is not None else None


def record_daily_count(project: Project, entry_date: date, ties: int,
                       relay_ties: int = 0, track: Optional[str] = None,
                       location: Optional[str] = None) -> DailyLogEntry:
    """Log ties for a date, optionally tagged to a track and/or a location. Same date + a
    *new* track is additive, it appends to that day's per-track breakdown and grows the day
    totals, so a day worked across two tracks is recorded with two calls. A day is either
    untracked or fully track-tagged, and is worked at a single location (a same-date add may
    not contradict the day's location). `location` is a Location id or name that must already
    exist on a company line (blank = main line / unassigned). Recomputes running totals.
    Raises ValueError on any conflict or invalid input; the caller maps that and persists."""
    if ties <= 0:
        raise ValueError("ties must be greater than 0")
    if relay_ties < 0 or relay_ties > ties:
        raise ValueError("relay_ties must be between 0 and ties (it is a subset of the day's tie count)")
    track = track.strip() if track and track.strip() else None
    loc_id = resolve_location(project, location)   # raises ValueError on an unknown location

    existing = next((e for e in project.daily_log if e.date == entry_date), None)
    if existing is None:
        entry = DailyLogEntry(
            date=entry_date, day=entry_date.strftime("%A"),
            ties=ties, relay_ties=relay_ties, vs_target=0, running_total=0, remaining=None,
            location=loc_id,
            tracks=[TrackSplit(track=track, ties=ties, relay_ties=relay_ties)] if track else [],
        )
        project.daily_log.append(entry)
    else:
        if track is None:
            raise ValueError(
                f"A daily entry for {entry_date} already exists. Use update_daily_count to correct "
                f"it, or pass a track to add another track's ties to that day.")
        if not existing.tracks:
            raise ValueError(
                f"{entry_date} already has untracked ties; correct it with update_daily_count "
                f"before adding per-track entries.")
        if any(t.track.lower() == track.lower() for t in existing.tracks):
            raise ValueError(
                f"{entry_date} already has an entry for track '{track}'. Use update_daily_count to correct it.")
        if loc_id is not None and existing.location is not None and loc_id != existing.location:
            raise ValueError(
                f"{entry_date} is already logged at a different location, a day is worked at one site. "
                f"Use update_daily_count to move the whole day.")
        if loc_id is not None and existing.location is None:
            existing.location = loc_id   # backfill when the first track-add omitted the location
        existing.tracks.append(TrackSplit(track=track, ties=ties, relay_ties=relay_ties))
        existing.ties += ties
        existing.relay_ties += relay_ties
        entry = existing

    recalc_running_totals(project)
    return entry


def update_daily_count(project: Project, entry_date: date, new_ties: int,
                       relay_ties: Optional[int] = None,
                       track: Optional[str] = None,
                       location: Optional[str] = None) -> tuple[DailyLogEntry, int]:
    """Correct a day's count, or one track's portion within a split day (pass `track`).
    Re-derives the day totals from its track splits when tracked. Pass `location` (an id or
    name) to move the whole day to another worksite; an empty string clears it; None leaves
    it unchanged. Recomputes running totals. Returns (entry, old_day_total). Raises
    ValueError if not found / invalid."""
    entry = next((e for e in project.daily_log if e.date == entry_date), None)
    if entry is None:
        raise ValueError(f"No log entry found for {entry_date}")
    if new_ties <= 0:
        raise ValueError("new_ties must be greater than 0")
    if relay_ties is not None and (relay_ties < 0 or relay_ties > new_ties):
        raise ValueError("relay_ties must be between 0 and new_ties (it is a subset of the day's tie count)")
    old_total = entry.ties
    track = track.strip() if track and track.strip() else None
    if location is not None:
        entry.location = resolve_location(project, location)   # raises on an unknown location

    if track:
        ts = next((t for t in entry.tracks if t.track.lower() == track.lower()), None)
        if ts is None:
            raise ValueError(f"{entry_date} has no entry for track '{track}'.")
        ts.ties = new_ties
        if relay_ties is not None:
            ts.relay_ties = relay_ties
        entry.ties = sum(t.ties for t in entry.tracks)
        entry.relay_ties = sum(t.relay_ties for t in entry.tracks)
    else:
        if entry.tracks:
            raise ValueError(
                f"{entry_date} is split across tracks ({', '.join(t.track for t in entry.tracks)}); "
                f"pass a track to correct one of them.")
        entry.ties = new_ties
        if relay_ties is not None:
            entry.relay_ties = relay_ties

    recalc_running_totals(project)
    return entry, old_total


def demote_other_actives(keep_id: str) -> list[str]:
    """Enforce the single-active invariant: set every active project other than
    `keep_id` to 'complete'. Returns the IDs that were demoted. The caller is
    responsible for setting `keep_id` itself to active."""
    demoted = []
    for p in list_projects():
        if p.project.id != keep_id and p.project.status == "active":
            p.project.status = "complete"
            save_project(p)
            demoted.append(p.project.id)
    return demoted


def list_projects() -> list[Project]:
    _ensure_dirs()
    projects = []
    for directory in [settings.projects_dir, settings.archived_dir]:
        for path in sorted(directory.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                projects.append(Project.model_validate(data))
            except (json.JSONDecodeError, Exception):
                continue
    return projects


def load_users() -> list[User]:
    path = settings.users_file
    if not path.exists():
        return []
    lock = _get_lock(str(path))
    with lock:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    return [User.model_validate(u) for u in data]


def save_users(users: list[User]) -> None:
    path = settings.users_file
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _get_lock(str(path))
    with lock:
        _atomic_write(path, [u.model_dump() for u in users])


DEFAULT_EQUIPMENT = [
    "Tie Inserter",
    "Broom",
    "Plate Setter",
    "Tamper",
    "Spiker/Gauger",
    "Other",
]


def load_equipment_list() -> list[str]:
    path = settings.config_file
    if not path.exists():
        return list(DEFAULT_EQUIPMENT)
    lock = _get_lock(str(path))
    with lock:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    return data.get("equipment", list(DEFAULT_EQUIPMENT))


def save_equipment_list(equipment: list[str]) -> None:
    path = settings.config_file
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _get_lock(str(path))
    with lock:
        existing: dict = {}
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing["equipment"] = equipment
        _atomic_write(path, existing)


# ── Generic JSON documents (organisation settings, scheduler state, MCP tokens) ──────
# Same lock + atomic-write discipline as project files.

def load_json(path: Path, default=None):
    """Read one JSON document under its file lock; `default` when the file does not exist."""
    if not path.exists():
        return default
    lock = _get_lock(str(path))
    with lock:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = _get_lock(str(path))
    with lock:
        _atomic_write(path, data)


# ── Project lifecycle (single source of truth for the web API, the MCP server, and the CLI)

_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_KIND_ALIASES = {"project": "sponsored", "line": "company"}
STATUSES = ("active", "complete", "archived")
META_FIELDS = ("name", "line", "job", "base", "deadline", "goal_ties",
               "confirmed_work_orders", "work_order_locations", "daily_target")


def create_project(project_id: str, name: str, kind: str = "company",
                   line: Optional[str] = None, job: str = "", base: str = "",
                   deadline: Optional[date] = None, goal_ties: Optional[int] = None,
                   daily_target: int = 350, confirmed_work_orders: int = 0,
                   work_order_locations: Optional[list[int]] = None) -> tuple[Project, list[str]]:
    """Create and persist a project. It starts active, demoting any other active project to
    complete. Returns (project, demoted_ids). Raises ValueError on a bad id or kind, a blank
    name, or a duplicate id."""
    project_id = (project_id or "").strip()
    if not _ID_RE.match(project_id):
        raise ValueError("project_id may only contain letters, numbers, hyphens, and underscores")
    kind = _KIND_ALIASES.get(kind, kind)
    if kind not in ("sponsored", "company"):
        raise ValueError("kind must be 'sponsored' or 'company'")
    if not (name or "").strip():
        raise ValueError("name is required")
    if load_project(project_id):
        raise ValueError(f"ID '{project_id}' already exists")
    demoted = demote_other_actives(project_id)
    meta = ProjectMeta(
        id=project_id, name=name.strip(), kind=kind, line=line, job=job, base=base,
        deadline=deadline, goal_ties=goal_ties, daily_target=daily_target,
        confirmed_work_orders=confirmed_work_orders,
        work_order_locations=work_order_locations or [],
        status="active", created=date.today(),
    )
    project = Project(project=meta)
    save_project(project)
    return project, demoted


def set_status(project: Project, status: str) -> list[str]:
    """Change a loaded project's lifecycle status; the caller persists it with save_project.
    Activating demotes every other active project (those are saved here). Returns the demoted
    ids. Raises ValueError on an unknown status."""
    if status not in STATUSES:
        raise ValueError("status must be one of: active, complete, archived")
    demoted = demote_other_actives(project.project.id) if status == "active" else []
    project.project.status = status
    return demoted


def update_project_meta(project: Project, **fields) -> list[str]:
    """Apply metadata changes to a loaded project and recompute every log entry's derived
    fields (a goal or daily-target change moves all of them). `status` goes through
    set_status. The caller persists with save_project. Returns any ids demoted by an
    activation. Raises ValueError on an unknown field or when nothing is provided."""
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        raise ValueError("No fields provided")
    status = fields.pop("status", None)
    for k, v in fields.items():
        if k not in META_FIELDS:
            raise ValueError(f"unknown field '{k}'")
        setattr(project.project, k, v)
    demoted = set_status(project, status) if status is not None else []
    recalc_running_totals(project)
    return demoted
