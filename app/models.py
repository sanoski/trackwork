from __future__ import annotations

import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Stored data models ────────────────────────────────────────────────────────

class ProjectMeta(BaseModel):
    id: str
    name: str
    kind: str = "sponsored"      # "sponsored" (goal + code name, e.g. 942) or "company" (line work, e.g. WACR_CRD)
    line: Optional[str] = None   # railroad line for company projects (e.g. "WACR_CRD")
    job: str = ""
    base: str = ""
    deadline: Optional[date] = None
    goal_ties: Optional[int] = None
    confirmed_work_orders: int = 0
    work_order_locations: list[int] = Field(default_factory=list)
    daily_target: int = 350
    status: str = "active"        # "active" (one at a time), "complete" (finished, still visible/reportable), or "archived" (hidden)
    work_week_note: str = ""
    created: date

    @field_validator("kind", mode="before")
    @classmethod
    def _map_legacy_kind(cls, v):
        # Older data used project/line; the model now uses sponsored/company.
        return {"project": "sponsored", "line": "company"}.get(v, v)


class TrackSplit(BaseModel):
    """How a day's ties broke down across a named track (e.g. 'Track 2', a siding, a
    yard track). Optional, main-line days carry no splits. `ties`/`relay_ties` here are
    the portion installed on that track and sum to the parent day's totals."""
    track: str = Field(..., min_length=1, max_length=40)
    ties: int = Field(..., ge=0)
    relay_ties: int = Field(0, ge=0)


class DailyLogEntry(BaseModel):
    date: date
    day: str
    ties: int                    # total plain-track ties installed that day (new + relay)
    relay_ties: int = 0          # subset of `ties` that were relay (reclaimed) ties; new = ties - relay
    vs_target: int
    running_total: int
    remaining: Optional[int] = None
    location: Optional[str] = None           # Location id (company lines); None = main line / unassigned
    tracks: list[TrackSplit] = Field(default_factory=list)   # optional per-track breakdown; empty = unspecified/main line


class EquipmentDowntime(BaseModel):
    date: date
    machine: str
    down_at: Optional[str] = None
    resumed: Optional[str] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None


class Timber(BaseModel):
    """One length row of a switch or derail: planned vs actual count for that length.
    A dash on the source sheet is recorded as 0."""
    length: int                  # nominal length in feet (e.g. 9..17)
    planned: int = 0             # count the boss marked ("planned" / "assigned")
    actual: int = 0              # count actually installed
    head_block: bool = False     # this length is a head-block timber


class Switch(BaseModel):
    id: str                      # stable within the project (e.g. "sw-01")
    name: str                    # e.g. "North Main Switch", "Switch to NH"
    date: date                   # day completed (buckets it into the weekly report)
    timbers: list[Timber] = Field(default_factory=list)
    location: Optional[str] = None       # Location id within the line; None = unassigned
    notes: Optional[str] = None


class Derail(BaseModel):
    id: str
    name: str
    date: date
    derail_type: Optional[str] = None    # "stationary" | "portable" | "switch" (switch-to-nowhere)
    timbers: list[Timber] = Field(default_factory=list)   # head blocks for stationary; empty for portable
    location: Optional[str] = None       # Location id within the line; None = unassigned
    notes: Optional[str] = None


class Location(BaseModel):
    """A worksite within a company line, a city/town/yard/siding (e.g. 'St. Johnsbury').
    A managed list (only company lines have them); work items reference a location by its
    stable slug `id`, so renaming `name` never requires re-tagging. Sponsored projects
    carry none. Managed via the add/update/delete_location tools (+ CLI twins)."""
    id: str                      # stable slug within the project (e.g. "st-johnsbury")
    name: str                    # display name (e.g. "St. Johnsbury")
    notes: Optional[str] = None


class Project(BaseModel):
    project: ProjectMeta
    locations: list[Location] = Field(default_factory=list)   # company-line worksites; empty for sponsored
    daily_log: list[DailyLogEntry] = Field(default_factory=list)
    equipment_downtime: list[EquipmentDowntime] = Field(default_factory=list)
    switches: list[Switch] = Field(default_factory=list)
    derails: list[Derail] = Field(default_factory=list)


class User(BaseModel):
    email: str
    password_hash: str
    name: str
    role: Literal["admin", "entry", "viewer"] = "viewer"   # admin manages, entry logs work, viewer reads


# ── Request models ────────────────────────────────────────────────────────────

def _validate_hhmm(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if not re.match(r"^\d{2}:\d{2}$", v):
        raise ValueError("Time must be in HH:MM format")
    h, m = map(int, v.split(":"))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Invalid time value")
    return v


class AddDailyCountRequest(BaseModel):
    date: date
    ties: int = Field(..., gt=0, le=10000)
    relay_ties: int = Field(0, ge=0)
    track: Optional[str] = Field(None, min_length=1, max_length=40)
    location: Optional[str] = Field(None, min_length=1, max_length=60)   # Location id or name; must already exist

    @field_validator("relay_ties")
    @classmethod
    def relay_within_ties(cls, v: int, info) -> int:
        ties = info.data.get("ties")
        if ties is not None and v > ties:
            raise ValueError("relay_ties cannot exceed ties (it is a subset of the day's tie count)")
        return v


class AddDowntimeRequest(BaseModel):
    date: date
    machine: str = Field(..., min_length=1, max_length=100)
    down_at: Optional[str] = None
    resumed: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("down_at", "resumed")
    @classmethod
    def validate_time(cls, v: Optional[str]) -> Optional[str]:
        return _validate_hhmm(v)


class AddDowntimeBatchRequest(BaseModel):
    incidents: list[AddDowntimeRequest] = Field(..., min_length=1)


class CreateProjectRequest(BaseModel):
    id: str = Field(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(..., min_length=1, max_length=100)
    kind: str = Field("company", pattern=r"^(sponsored|company)$")
    line: Optional[str] = Field(None, max_length=100)
    job: str = Field("", max_length=200)
    base: str = Field("", max_length=100)
    deadline: Optional[date] = None
    goal_ties: Optional[int] = Field(None, gt=0)
    confirmed_work_orders: int = Field(0, ge=0)
    work_order_locations: list[int] = Field(default_factory=list)
    daily_target: int = Field(350, gt=0)

    @field_validator("kind", mode="before")
    @classmethod
    def _map_legacy_kind(cls, v):
        return {"project": "sponsored", "line": "company"}.get(v, v)


class UpdateProjectRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    line: Optional[str] = Field(None, max_length=100)
    job: Optional[str] = Field(None, min_length=1, max_length=200)
    base: Optional[str] = Field(None, min_length=1, max_length=100)
    deadline: Optional[date] = None
    goal_ties: Optional[int] = Field(None, gt=0)
    confirmed_work_orders: Optional[int] = Field(None, ge=0)
    work_order_locations: Optional[list[int]] = None
    daily_target: Optional[int] = Field(None, gt=0)
    status: Optional[str] = Field(None, pattern=r"^(active|complete|archived)$")


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class AddEquipmentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class ReportOptions(BaseModel):
    """Which data points a report includes, composition toggles only. Scope
    (project / location / week) is a separate request-routing concern, so this object
    serializes cleanly to the print wizard and back. When a request omits `options`,
    the server fills the scope-aware "overview" defaults via
    `reporting.options.default_options`, so the legacy `{email, project_id, location}`
    body is byte-for-byte unchanged.

    `ties_mode` picks which tie columns/series appear: `none` hides ties entirely,
    `new`/`relay` show only that subset, `both` shows New / Relay / Total (current behavior).

    `entity_detail` controls how switches AND derails are drawn: `summary` (default) consolidates
    all of them in scope into ONE block per type (a single by-length bar chart with timber counts
    summed, plus a combined Planned/Actual table) so the report doesn't run to pages of individual
    diagrams; `itemized` (verbose) draws every switch/derail as its own turnout/derail diagram and
    table, the way it used to."""
    ties_mode: Literal["none", "new", "relay", "both"] = "both"
    entity_detail: Literal["summary", "itemized"] = "summary"
    switches: bool = True
    derails: bool = True
    downtime: bool = True
    charts: bool = True


class ReportPeriod(BaseModel):
    """The time slice a report covers (the wizard's time control). Omitted on a request → the server
    resolves the most recently completed Sun–Sat week, falling back to the week of latest activity
    (`reporting.resolve_period`), so the legacy body is unchanged. `mode=week` uses `week` (any date
    in the target week) or that default when null; `mode=full` covers the project's whole span;
    `mode=range` uses `start`/`end` (open ends default to the project span)."""
    mode: Literal["week", "full", "range"] = "week"
    week: Optional[date] = None
    start: Optional[date] = None
    end: Optional[date] = None


class SendReportRequest(BaseModel):
    """On-demand report email triggered from the portal. `project_id` defaults to
    the active project when omitted; `location` (a worksite id or name) narrows the
    report to one site on a company line, else it covers the whole line. `options`
    (omitted = overview defaults) composes which data points the report includes;
    `period` (omitted = most recent week) sets the time scope."""
    email: EmailStr
    project_id: Optional[str] = Field(default=None, max_length=64)
    location: Optional[str] = Field(default=None, max_length=64)
    options: Optional[ReportOptions] = None
    period: Optional[ReportPeriod] = None


class PreviewRequest(BaseModel):
    """Same scope/composition fields as a report request, minus email, backs the wizard's live
    HTML preview (`POST /api/reports/preview`). `_report_scope` reads `project_id`/`location`."""
    project_id: Optional[str] = Field(default=None, max_length=64)
    location: Optional[str] = Field(default=None, max_length=64)
    options: Optional[ReportOptions] = None
    period: Optional[ReportPeriod] = None


# ── Editing, users, and organisation settings ────────────────────────────────────
# Request shapes shared by the web API. The MCP server and the CLI take the same fields as
# plain arguments; all three call the same service functions.

class UpdateDailyCountRequest(BaseModel):
    """Correct a logged day. `new_ties` is the day total, or one track's portion when `track`
    is given. `relay_ties` omitted leaves it unchanged. `location` moves the whole day (an empty
    string clears it)."""
    new_ties: int = Field(..., gt=0, le=10000)
    relay_ties: Optional[int] = Field(None, ge=0)
    track: Optional[str] = Field(None, min_length=1, max_length=40)
    location: Optional[str] = Field(None, max_length=60)


class UpdateDowntimeRequest(BaseModel):
    machine: str = Field(..., min_length=1, max_length=100)   # which entry, with the date in the URL
    down_at: Optional[str] = None
    resumed: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=1000)
    match_down_at: Optional[str] = None   # picks one entry when several share the date and machine

    @field_validator("down_at", "resumed", "match_down_at")
    @classmethod
    def validate_time(cls, v: Optional[str]) -> Optional[str]:
        return _validate_hhmm(v)


class SwitchCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    date: date
    timbers: list[Timber] = Field(..., min_length=1)
    notes: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=60)


class SwitchUpdateRequest(BaseModel):
    new_name: Optional[str] = Field(None, min_length=1, max_length=100)
    timbers: Optional[list[Timber]] = None      # replaces the whole list
    notes: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=60)


class DerailCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    date: date
    timbers: list[Timber] = Field(default_factory=list)   # a portable derail may have none
    derail_type: Optional[str] = Field(None, pattern=r"^(stationary|portable|switch)$")
    notes: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=60)


class DerailUpdateRequest(BaseModel):
    new_name: Optional[str] = Field(None, min_length=1, max_length=100)
    derail_type: Optional[str] = Field(None, pattern=r"^(stationary|portable|switch|)$")
    timbers: Optional[list[Timber]] = None
    notes: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=60)


class LocationCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    notes: Optional[str] = Field(None, max_length=500)


class LocationUpdateRequest(BaseModel):
    new_name: Optional[str] = Field(None, min_length=1, max_length=80)
    notes: Optional[str] = Field(None, max_length=500)


class SetStatusRequest(BaseModel):
    status: Literal["active", "complete", "archived"]


class UserCreateRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    name: str = Field(..., min_length=1, max_length=100)
    role: Literal["admin", "entry", "viewer"] = "viewer"
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[Literal["admin", "entry", "viewer"]] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)


class SmtpSettings(BaseModel):
    host: str = ""
    port: int = Field(587, ge=1, le=65535)
    user: str = ""
    password: str = ""


def _validate_tz(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    from zoneinfo import ZoneInfo
    try:
        ZoneInfo(v)
    except Exception:
        raise ValueError(f"unknown time zone '{v}' (use a name like America/New_York)")
    return v


class WeeklySchedule(BaseModel):
    """When the weekly report goes out. Sunday 08:00 by default, the original cron time."""
    enabled: bool = True
    day_of_week: Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"] = "sun"
    hour: int = Field(8, ge=0, le=23)
    minute: int = Field(0, ge=0, le=59)
    timezone: str = "America/New_York"

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        return _validate_tz(v)


class AppSettings(BaseModel):
    """Organisation settings stored in DATA_DIR/settings.json (see app_settings.py)."""
    org_name: str = "Vermont Rail System"
    app_name: str = "MOW Tracker"
    report_recipients: list[str] = Field(default_factory=list)
    report_sender: str = ""
    smtp: SmtpSettings = Field(default_factory=SmtpSettings)
    schedule: WeeklySchedule = Field(default_factory=WeeklySchedule)


class SmtpSettingsUpdate(BaseModel):
    """All optional: only the fields sent are changed."""
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    user: Optional[str] = None
    password: Optional[str] = None


class WeeklyScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    day_of_week: Optional[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]] = None
    hour: Optional[int] = Field(None, ge=0, le=23)
    minute: Optional[int] = Field(None, ge=0, le=59)
    timezone: Optional[str] = None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: Optional[str]) -> Optional[str]:
        return _validate_tz(v)


class SettingsUpdateRequest(BaseModel):
    """Partial update; omitted fields stay as they are. A blank smtp.password keeps the stored
    password, so the admin screen never has to echo it back."""
    org_name: Optional[str] = Field(None, min_length=1, max_length=100)
    app_name: Optional[str] = Field(None, min_length=1, max_length=100)
    report_recipients: Optional[list[str]] = None
    report_sender: Optional[str] = Field(None, max_length=254)
    smtp: Optional[SmtpSettingsUpdate] = None
    schedule: Optional[WeeklyScheduleUpdate] = None


class McpTokenCreateRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)   # the account this token acts as
    label: str = Field(..., min_length=1, max_length=80)
    days: int = Field(90, ge=1, le=365)


class TestEmailRequest(BaseModel):
    to: EmailStr


# ── Response models ───────────────────────────────────────────────────────────

class ProjectListItem(BaseModel):
    id: str
    name: str
    kind: str
    status: str
    deadline: Optional[date] = None
    goal_ties: Optional[int] = None
    total_ties: int
    percent_complete: Optional[float] = None
    locations: list[Location] = Field(default_factory=list)   # company-line worksites, for the sidebar tree


class ProjectSummary(BaseModel):
    id: str
    name: str
    kind: str
    status: str
    total_ties: int
    remaining: Optional[int] = None
    vs_schedule: int
    projected_finish: Optional[date] = None
    daily_target: int
    avg_daily_output: float
    percent_complete: Optional[float] = None
    deadline: Optional[date] = None
    days_remaining: Optional[int] = None


class UserResponse(BaseModel):
    email: str
    name: str
    role: str
