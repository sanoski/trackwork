# app/CLAUDE.md, core services

## Agent instructions: the service layer that every entry point calls

**Module directory:** `app/`
**Files:** `config.py`, `models.py`, `structures.py`, `downtime.py`, `storage.py`, `mailer.py`,
`app_settings.py`, `auth.py`, `users.py`, `scheduler.py`, `limiter.py`, `main.py`, plus the
`routes/`, `reporting/`, and `static/` sub-packages (each has its own CLAUDE.md).

## Scope

One rule above all: the web API (`routes/`), the MCP server (`mcp_server/`), and the CLI
(`scripts/cli.py`) are thin. Every piece of business logic lives in the modules below, and
nothing here imports `routes`, `main`, `mcp_server`, or `scripts`. Error convention:
`LookupError` means not found, `ValueError` means invalid input or a conflict; entry points map
them (404 and 409 on the web, an error message on MCP and the CLI).

This package does not know how it was called. It never reads request objects, never prints,
and never sends HTTP.

## Dependency direction (arrows point at what is imported)

```
models <- structures, downtime, mailer, config
storage <- config, models, structures
app_settings <- config, models, storage, mailer
auth <- config, models, storage
users <- auth, storage, models
reporting <- models, storage, structures, app_settings, mailer
scheduler <- reporting, app_settings, storage, config
main -> routes, scheduler, limiter, mcp_server (wiring only)
```

## Public interface, by file

### config.py
`settings` (pydantic-settings, reads `.env`). Env vars: `SECRET_KEY`, `ENVIRONMENT`,
`PUBLIC_READ`, `DATA_DIR`, `SMTP_HOST/PORT/USER/PASSWORD`, `REPORT_EMAIL_RECIPIENT`,
`REPORT_EMAIL_SENDER`, `SCHEDULER_ENABLED`, `MCP_ENABLED`, `MCP_AUTH_PROVIDER`, `MCP_BASE_URL`,
`MCP_OAUTH_CLIENT_ID/SECRET/TENANT`. Paths: `projects_dir`, `archived_dir`, `users_file`,
`config_file` (equipment list), `settings_file`, `scheduler_state_file`, `mcp_tokens_file`.
Env only bootstraps; organisation settings live in `settings_file` and win once saved.

### models.py
Every Pydantic model. Stored: `ProjectMeta`, `DailyLogEntry`, `TrackSplit`,
`EquipmentDowntime`, `Timber`, `Switch`, `Derail`, `Location`, `Project`, `User` (role is
`admin | entry | viewer`). Requests: `AddDailyCountRequest`, `UpdateDailyCountRequest`,
`AddDowntimeRequest`, `UpdateDowntimeRequest`, `SwitchCreate/UpdateRequest`,
`DerailCreate/UpdateRequest`, `LocationCreate/UpdateRequest`, `CreateProjectRequest`,
`UpdateProjectRequest`, `SetStatusRequest`, `UserCreate/UpdateRequest`, `SettingsUpdateRequest`,
`McpTokenCreateRequest`, `ReportOptions`, `ReportPeriod`, `SendReportRequest`, `PreviewRequest`.
Settings: `SmtpSettings`, `WeeklySchedule`, `AppSettings`. Responses: `ProjectListItem`,
`ProjectSummary`, `UserResponse`.

### structures.py (pure, no I/O)
`slugify`, `unique_id`, `entity_totals`, `coerce_timbers`, `find_entity`, `get_entity`,
`add_switch`, `update_switch`, `delete_switch`, `add_derail`, `update_derail`, `delete_derail`,
`find_location`, `resolve_location` (raises `ValueError` on an unknown worksite: locations are
a managed list), `location_refs`, `add_location`, `update_location` (the id stays stable on
rename), `delete_location` (refused while work references it), `scope_to_location`.

### downtime.py (pure, no I/O)
`calc_duration`, `find_downtime` (raises `ValueError` when several entries match unless
`down_at` picks one), `add_downtime`, `update_downtime`, `delete_downtime`.

### storage.py (the only module that touches disk)
`load_project`, `save_project` (moves a file between `projects/` and `archived/` by status),
`list_projects`, `recalc_running_totals`, `record_daily_count`, `update_daily_count` (both
recalc; the caller saves), `demote_other_actives`, `create_project` (saves), `set_status` and
`update_project_meta` (mutate and recalc; the caller saves), `load_users`, `save_users`,
`load_equipment_list`, `save_equipment_list`, `load_json`, `save_json`. Per-file lock and
atomic write (tmp then rename).

### mailer.py
`send_message(smtp, sender, recipients, subject, body, attachment=None, filename=None)`.
STARTTLS. Raises `RuntimeError` when settings are incomplete or there is no recipient.

### app_settings.py
`get_settings`, `save_settings`, `update_settings` (nested merge; a blank `smtp.password`
keeps the stored one), `effective_smtp`, `public_view` (never echoes the password, only
`password_set`), `test_email(to)`.

### auth.py
`hash_password`, `verify_password`, `create_access_token`, `authenticate_user`,
`get_current_user` (httpOnly cookie or bearer), `require_writer` (admin or entry),
`require_admin`, `read_permission` (honours `PUBLIC_READ`). There are no service tokens.

### users.py
`list_users`, `find_user`, `create_user`, `update_user`, `delete_user`. Passwords are at least
8 characters. The last admin can be neither demoted nor deleted.

### scheduler.py
`start`, `stop`, `reschedule`, `run_now`, `status`, `run_weekly`. Sends the report for the most
recently completed Sunday-to-Saturday week once, recording the week in `scheduler_state_file`.
Run exactly one web worker.

### limiter.py, main.py
`limiter` (slowapi). `main.py` only wires: routers, static mounts, the lifespan (scheduler
start and stop), and the MCP mount at `/mcp` when enabled.

## Notes
- bcrypt is called directly; never passlib (it breaks on bcrypt 4).
- weasyprint is imported lazily inside `reporting.render.build_pdf` so startup never loads Pango.
- Running totals are recalculated on every daily-count write; client values are never trusted.
- `relay_ties` is a subset of `ties`. The work week is Sunday to Saturday.
- Exactly one project is active; activating one demotes the others to complete.
