# Architecture

For a developer changing the code. The `CLAUDE.md` file in each directory says the same
things in the form an AI coding assistant reads; keep the two in step.

## The one rule

Three entry points, one service layer, one data directory.

```
routes/ (web API)    mcp_server/ (Claude)    scripts/cli.py (terminal)
        \                    |                     /
         +-------------------+--------------------+
                             |
                        app/ services
      storage  structures  downtime  users  app_settings  reporting  scheduler
                             |
                          DATA_DIR
```

Entry points validate input, call one service function, save if it mutated a project, and
return. They never contain business logic. Every MCP tool has a CLI command and a web route
that do the same thing, and `tests/test_parity.py` fails if one is missing.

## Layout

```
app/
  config.py        env bootstrap and DATA_DIR paths (pydantic-settings)
  models.py        every Pydantic model: stored records, requests, settings, responses
  structures.py    switches, derails, worksites on a Project (pure, no I/O)
  downtime.py      equipment downtime on a Project (pure, no I/O)
  storage.py       the only module that touches disk; daily-count math; project lifecycle
  app_settings.py  organisation settings (env is the default, settings.json wins)
  mailer.py        the SMTP transport
  auth.py          bcrypt, JWT cookie, permission dependencies
  users.py         accounts and roles, last-admin guard
  mcp_tokens.py    per-user tokens for the MCP server
  scheduler.py     the weekly timer (APScheduler, once-per-week marker)
  limiter.py       slowapi rate limiter
  main.py          wiring only: routers, static mounts, lifespan, MCP mount
  routes/          auth.py, api.py, admin.py, pages.py, common.py
  reporting/       run.py, data.py, options.py, charts.py, diagrams.py, render.py, email.py, templates/
  static/          index.html, style.css, js/*.js (ES modules), vendor/chart.umd.min.js
mcp_server/        server.py (tools), auth.py (provider factory)
scripts/cli.py     the command line
deploy/            Dockerfile support, Caddy, nginx example, systemd, setup.sh
demo/data          fictional dataset for trials
tests/             pytest suite
docs/              these documents
```

Dependency direction (arrows point at what is imported; the graph is acyclic):

```
models <- structures, downtime, mailer, config
storage <- config, models, structures
app_settings <- config, models, storage, mailer
auth <- config, models, storage
users <- auth, storage, models
mcp_tokens <- config, storage
reporting <- models, storage, structures, app_settings, mailer
scheduler <- reporting, app_settings, storage, config
routes/* -> the services above
main -> routes, scheduler, limiter, mcp_server
mcp_server -> the services above, never routes
scripts/cli -> the services above, never routes, never mcp_server
```

Nothing imports `routes`, `main`, or `scripts`. `reporting` never imports `scheduler`.

## Data

No database server. `DATA_DIR` holds:

```
projects/<id>.json      one file per project (active and complete)
archived/<id>.json      archived projects
users.json              accounts with bcrypt hashes
settings.json           organisation settings (mail, recipients, schedule, names)
config.json             the equipment list
scheduler_state.json    last week sent, last run, last error
mcp_tokens.json         token records (id, email, label, expiry, revoked), never the token
```

A project file:

```json
{
  "project": {"id": "WACR_CRD", "name": "...", "kind": "company", "line": "WACR_CRD",
              "goal_ties": null, "daily_target": 350, "deadline": null, "status": "active", ...},
  "locations": [{"id": "st-johnsbury", "name": "St. Johnsbury", "notes": null}],
  "daily_log": [{"date": "2026-06-16", "day": "Tuesday", "ties": 144, "relay_ties": 144,
                 "vs_target": -206, "running_total": 467, "remaining": null,
                 "location": "st-johnsbury",
                 "tracks": [{"track": "Track 2", "ties": 68, "relay_ties": 68},
                            {"track": "Track 3", "ties": 76, "relay_ties": 76}]}],
  "equipment_downtime": [{"date": "2026-05-06", "machine": "Broom", "down_at": "08:00",
                          "resumed": "10:30", "duration_minutes": 150, "notes": "..."}],
  "switches": [{"id": "north-main-switch", "name": "North Main Switch", "date": "2026-06-22",
                "location": "st-johnsbury", "notes": null,
                "timbers": [{"length": 9, "planned": 6, "actual": 11, "head_block": false}]}],
  "derails": [{"id": "south-derail", "name": "South Derail", "date": "2026-06-17",
               "derail_type": "stationary", "location": "st-johnsbury", "notes": null,
               "timbers": [{"length": 12, "planned": 2, "actual": 2, "head_block": true}]}]
}
```

Writes take a per-file lock and write to a temp file then rename, so a crash never leaves a
half-written project.

## Invariants the services enforce

- `running_total`, `remaining`, and `vs_target` are recalculated on every write
  (`storage.recalc_running_totals`). Client values are never trusted.
- One daily entry per date. A `tracks` list may split it; the day is either untracked or
  fully track-tagged. Logging the same date with a new track adds to the day.
- `relay_ties` is a subset of `ties`. `new = ties - relay`.
- A day is worked at one worksite. Worksites are a managed list referenced by id, so a rename
  never re-tags work; deleting one is refused while anything references it.
- Switches and derails are separate from the daily tie count. Derails count toward timber
  totals but not the switch count.
- `kind` is `sponsored` (goal) or `company` (line). Goal fields self-suppress when
  `goal_ties` is null; there is one dashboard and one report template for both.
- Exactly one project is `active`. Activating one demotes the previous to `complete`.
- The work week is Sunday to Saturday.
- Errors: services raise `LookupError` (not found) and `ValueError` (invalid or conflict).
  The web maps them to 404 and 409, MCP returns `{"error": ...}`, the CLI prints and exits 1.

## Web app

FastAPI. Sign-in sets an httpOnly JWT cookie (7 days, secure in production). `read_permission`
allows anonymous reads when `PUBLIC_READ=true`; `require_writer` is admin or entry;
`require_admin` guards projects, equipment, and `/api/admin`. The browser app is ES modules
with no build step: `api.js` is the only fetch layer, `state.js` the only shared state, one
screen per file, screens rendered into one generic side panel. Role gating is CSS driven
(`body.can-write`, `body.is-admin`) and the server enforces the same rules.

## Reports

`reporting.run_report(...)` is the single orchestration entry used by the CLI, the timer,
and the admin run-now: scope, period, activity gate, options, render, save, send. One Jinja
template renders both the HTML preview and, through WeasyPrint, the PDF. Charts and diagrams
are inline SVG. WeasyPrint is imported lazily so startup never loads Pango.

## Weekly timer

`scheduler.py` runs an APScheduler `BackgroundScheduler` with one cron trigger read from
settings. The job writes the week it sent to `scheduler_state.json` and skips if that week
was already sent, so a restart never resends. Run one uvicorn worker.

## MCP

FastMCP. `mcp_server/server.py` defines the tools and calls services directly (no HTTP round
trip). `mcp_server/auth.py` builds the auth provider from `MCP_AUTH_PROVIDER`: the app's own
per-user JWTs (`app/mcp_tokens.py`), or FastMCP's Azure, Google, or GitHub OAuth proxy, which
handles the dynamic client registration claude.ai connectors need. `main.py` mounts the MCP
ASGI app at `/mcp` inside the web process when `MCP_ENABLED=true`, with the MCP lifespan
nested in the app's.

## Tests

`.venv/bin/python -m pytest -q` (install `requirements-dev.txt`). The suite points
`DATA_DIR` at a temp directory, never sends mail, and covers the services, the web routes by
role, the timer's marker, tokens, and the tool/command/route parity table.

## Conventions

- bcrypt directly, never passlib.
- No em dashes in any text a person reads: docs, UI, report, commit messages.
- Public text says "worksite" for a location and "relay" for reclaimed ties.
- Add a capability by adding a service function first, then its route, tool, and command,
  then a test.
