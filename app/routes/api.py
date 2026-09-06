from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from starlette.concurrency import run_in_threadpool

from ..auth import get_current_user, read_permission, require_admin, require_writer
from ..limiter import limiter
from ..models import (
    AddDailyCountRequest,
    AddDowntimeBatchRequest,
    AddEquipmentRequest,
    CreateProjectRequest,
    DailyLogEntry,
    Derail,
    DerailCreateRequest,
    DerailUpdateRequest,
    EquipmentDowntime,
    Location,
    LocationCreateRequest,
    LocationUpdateRequest,
    Project,
    ProjectListItem,
    ProjectSummary,
    PreviewRequest,
    SendReportRequest,
    SetStatusRequest,
    Switch,
    SwitchCreateRequest,
    SwitchUpdateRequest,
    UpdateDailyCountRequest,
    UpdateDowntimeRequest,
    UpdateProjectRequest,
    User,
)
from .. import downtime, reporting, storage, structures
from ..structures import resolve_location
from .common import service as _service

router = APIRouter(prefix="/api", tags=["api"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_project_or_404(project_id: str) -> Project:
    project = storage.load_project(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project



# ── Projects (read) ───────────────────────────────────────────────────────────

@router.get("/projects", response_model=list[ProjectListItem])
async def list_projects(_: Optional[User] = Depends(read_permission)):
    projects = storage.list_projects()
    items = []
    for p in projects:
        total = sum(e.ties for e in p.daily_log)
        goal = p.project.goal_ties
        pct = round(total / goal * 100, 1) if goal else None
        items.append(ProjectListItem(
            id=p.project.id,
            name=p.project.name,
            kind=p.project.kind,
            status=p.project.status,
            deadline=p.project.deadline,
            goal_ties=goal,
            total_ties=total,
            percent_complete=pct,
            locations=p.locations,
        ))
    return items


@router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str, _: Optional[User] = Depends(read_permission)):
    return _get_project_or_404(project_id)


@router.get("/projects/{project_id}/summary", response_model=ProjectSummary)
async def get_project_summary(project_id: str, _: Optional[User] = Depends(read_permission)):
    project = _get_project_or_404(project_id)
    return reporting.build_summary(project)


# ── Projects (write) ──────────────────────────────────────────────────────────

@router.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(body: CreateProjectRequest, _: User = Depends(require_admin)):
    project, _demoted = _service(
        storage.create_project, body.id, body.name, kind=body.kind, line=body.line,
        job=body.job, base=body.base, deadline=body.deadline, goal_ties=body.goal_ties,
        daily_target=body.daily_target, confirmed_work_orders=body.confirmed_work_orders,
        work_order_locations=body.work_order_locations)
    return project


@router.patch("/projects/{project_id}", response_model=Project)
async def update_project(project_id: str, body: UpdateProjectRequest, _: User = Depends(require_admin)):
    project = _get_project_or_404(project_id)
    _service(storage.update_project_meta, project, **body.model_dump(exclude_none=True))
    storage.save_project(project)
    return project


@router.post("/projects/{project_id}/status", response_model=Project)
async def set_status(project_id: str, body: SetStatusRequest, _: User = Depends(require_admin)):
    """Set active, complete, or archived. Activating demotes any other active project."""
    project = _get_project_or_404(project_id)
    _service(storage.set_status, project, body.status)
    storage.save_project(project)
    return project


# ── Daily log ─────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/log", response_model=DailyLogEntry, status_code=status.HTTP_201_CREATED)
async def add_daily_count(project_id: str, body: AddDailyCountRequest, _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    try:
        entry = storage.record_daily_count(
            project, body.date, body.ties, body.relay_ties, body.track, body.location,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    storage.save_project(project)
    return entry


# ── Downtime ──────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/downtime", response_model=list[EquipmentDowntime], status_code=status.HTTP_201_CREATED)
async def add_downtime(project_id: str, body: AddDowntimeBatchRequest, _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    added = [_service(downtime.add_downtime, project, i.date, i.machine, i.down_at, i.resumed, i.notes)
             for i in body.incidents]
    storage.save_project(project)
    return added


@router.patch("/projects/{project_id}/downtime/{entry_date}", response_model=EquipmentDowntime)
async def update_downtime(project_id: str, entry_date: date, body: UpdateDowntimeRequest,
                          _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    entry = _service(downtime.update_downtime, project, entry_date, body.machine,
                     down_at=body.down_at, resumed=body.resumed, notes=body.notes,
                     match_down_at=body.match_down_at)
    storage.save_project(project)
    return entry


@router.delete("/projects/{project_id}/downtime/{entry_date}")
async def delete_downtime(project_id: str, entry_date: date, machine: str,
                          down_at: Optional[str] = None, _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    entry = _service(downtime.delete_downtime, project, entry_date, machine, down_at)
    storage.save_project(project)
    return {"deleted": entry}


# ── Daily log corrections ─────────────────────────────────────────────────────

@router.patch("/projects/{project_id}/log/{entry_date}", response_model=DailyLogEntry)
async def update_daily_count(project_id: str, entry_date: date, body: UpdateDailyCountRequest,
                             _: User = Depends(require_writer)):
    """Correct a logged day, or one track of a split day. Every later total is recalculated."""
    project = _get_project_or_404(project_id)
    entry, _old = _service(storage.update_daily_count, project, entry_date, body.new_ties,
                           body.relay_ties, body.track, body.location)
    storage.save_project(project)
    return entry


# ── Switches and derails ──────────────────────────────────────────────────────

@router.post("/projects/{project_id}/switches", response_model=Switch, status_code=status.HTTP_201_CREATED)
async def add_switch(project_id: str, body: SwitchCreateRequest, _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    sw = _service(structures.add_switch, project, body.name, body.date, body.timbers,
                  notes=body.notes, location=body.location)
    storage.save_project(project)
    return sw


@router.patch("/projects/{project_id}/switches/{switch_id}", response_model=Switch)
async def update_switch(project_id: str, switch_id: str, body: SwitchUpdateRequest,
                        _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    sw = _service(structures.update_switch, project, switch_id, new_name=body.new_name,
                  timbers=body.timbers, notes=body.notes, location=body.location)
    storage.save_project(project)
    return sw


@router.delete("/projects/{project_id}/switches/{switch_id}")
async def delete_switch(project_id: str, switch_id: str, _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    sw = _service(structures.delete_switch, project, switch_id)
    storage.save_project(project)
    return {"deleted": sw}


@router.post("/projects/{project_id}/derails", response_model=Derail, status_code=status.HTTP_201_CREATED)
async def add_derail(project_id: str, body: DerailCreateRequest, _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    dr = _service(structures.add_derail, project, body.name, body.date, body.timbers,
                  derail_type=body.derail_type, notes=body.notes, location=body.location)
    storage.save_project(project)
    return dr


@router.patch("/projects/{project_id}/derails/{derail_id}", response_model=Derail)
async def update_derail(project_id: str, derail_id: str, body: DerailUpdateRequest,
                        _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    dr = _service(structures.update_derail, project, derail_id, new_name=body.new_name,
                  derail_type=body.derail_type, timbers=body.timbers, notes=body.notes,
                  location=body.location)
    storage.save_project(project)
    return dr


@router.delete("/projects/{project_id}/derails/{derail_id}")
async def delete_derail(project_id: str, derail_id: str, _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    dr = _service(structures.delete_derail, project, derail_id)
    storage.save_project(project)
    return {"deleted": dr}


# ── Locations (worksites on a company line) ───────────────────────────────────

@router.post("/projects/{project_id}/locations", response_model=Location, status_code=status.HTTP_201_CREATED)
async def add_location(project_id: str, body: LocationCreateRequest, _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    loc = _service(structures.add_location, project, body.name, notes=body.notes)
    storage.save_project(project)
    return loc


@router.patch("/projects/{project_id}/locations/{location_id}", response_model=Location)
async def update_location(project_id: str, location_id: str, body: LocationUpdateRequest,
                          _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    loc = _service(structures.update_location, project, location_id, new_name=body.new_name,
                   notes=body.notes)
    storage.save_project(project)
    return loc


@router.delete("/projects/{project_id}/locations/{location_id}")
async def delete_location(project_id: str, location_id: str, _: User = Depends(require_writer)):
    project = _get_project_or_404(project_id)
    loc = _service(structures.delete_location, project, location_id)
    storage.save_project(project)
    return {"deleted": loc}


# ── Equipment ─────────────────────────────────────────────────────────────────

@router.get("/equipment")
async def get_equipment(_: Optional[User] = Depends(read_permission)):
    return {"equipment": storage.load_equipment_list()}


@router.post("/equipment", status_code=status.HTTP_201_CREATED)
async def add_equipment(body: AddEquipmentRequest, _: User = Depends(require_admin)):
    equipment = storage.load_equipment_list()
    if body.name in equipment:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Equipment type already exists")
    equipment.append(body.name)
    storage.save_equipment_list(equipment)
    return {"equipment": equipment}


# ── Reports ───────────────────────────────────────────────────────────────────

def _report_scope(body: SendReportRequest):
    """Resolve a report request to (projects, scope_label). Raises HTTPException on an
    unknown worksite (404) or empty scope (404). Shared by the send + preview routes."""
    try:
        projects = reporting.scope_projects(body.project_id, body.location)
    except ValueError as e:
        # location token matched no worksite on the scoped line
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if not projects:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(f"Project '{body.project_id}' not found."
                    if body.project_id else "No active project to report on."),
        )
    scope_label = None
    if body.location:
        lid = resolve_location(projects[0], body.location)
        scope_label = next((l.name for l in projects[0].locations if l.id == lid), None)
    return projects, scope_label


@router.post("/reports/send")
@limiter.limit("4/minute")
async def send_report(
    request: Request,
    body: SendReportRequest,
    _: User = Depends(get_current_user),
):
    """Generate the current weekly PDF report on demand and email it to one address.
    Scope is the given project (or the active project when omitted); `location` narrows
    it to one worksite on a company line; `options` composes which data points appear."""
    projects, scope_label = _report_scope(body)

    period = reporting.resolve_period(projects, body.period)
    if reporting.week_activity(projects, period.start, period.end) == 0:
        where = "this worksite" if body.location else "this project"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No work was logged for {where} in the selected period, nothing to report.",
        )

    options = body.options or reporting.default_options(projects[0], body.location)
    pdf = await run_in_threadpool(
        reporting.build_pdf, projects, period, options,
        scope_label=scope_label, location=body.location)
    try:
        await run_in_threadpool(
            reporting.send_email, pdf, period.start, period.end, [str(body.email)], scope_label)
    except RuntimeError as e:
        # missing SMTP settings / no recipient
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The report was generated but could not be emailed. Please try again.",
        )

    return {
        "ok": True,
        "email": str(body.email),
        "week_start": period.start.isoformat(),
        "week_end": period.end.isoformat(),
        "week_label": period.date_label,
        "period": period.kind,
        "projects": [p.project.name for p in projects],
        "worksite": scope_label,
    }


@router.post("/reports/preview", response_class=HTMLResponse)
@limiter.limit("60/minute")
async def preview_report(
    request: Request,
    body: PreviewRequest,
    _: User = Depends(get_current_user),
):
    """Render the report to HTML for the wizard's live preview, no email, no PDF. Same scope +
    composition + period as the send route, funneled through the same `_report_scope` and
    `reporting.build_html` (one report path). Fonts resolve against the `/report-assets/fonts`
    mount. Not activity-gated: an empty period still previews (sections self-suppress), so the
    user sees exactly what would be generated."""
    projects, scope_label = _report_scope(body)
    period = reporting.resolve_period(projects, body.period)
    options = body.options or reporting.default_options(projects[0], body.location)
    html = await run_in_threadpool(
        reporting.build_html, projects, period, options,
        scope_label=scope_label, location=body.location, font_base="/report-assets/fonts")
    return HTMLResponse(html)


@router.post("/reports/pdf")
@limiter.limit("10/minute")
async def download_report(
    request: Request,
    body: PreviewRequest,
    _: User = Depends(get_current_user),
):
    """Build the PDF and hand it to the browser as a download, no email involved. Same scope,
    composition, and period as the send route (one report path), and the same file name the
    email attachment would carry, so an office without a mail server still gets the report."""
    projects, scope_label = _report_scope(body)
    period = reporting.resolve_period(projects, body.period)
    if reporting.week_activity(projects, period.start, period.end) == 0:
        where = "this worksite" if body.location else "this project"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No work was logged for {where} in the selected period, nothing to report.",
        )
    options = body.options or reporting.default_options(projects[0], body.location)
    pdf = await run_in_threadpool(
        reporting.build_pdf, projects, period, options,
        scope_label=scope_label, location=body.location)
    filename = reporting.report_filename(scope_label, period.start)
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
