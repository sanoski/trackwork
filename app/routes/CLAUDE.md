# app/routes/CLAUDE.md, the web API

## Agent instructions: wiring only

**Module directory:** `app/routes/`
**Files:** `api.py` (projects, log, downtime, switches, derails, locations, equipment, reports),
`admin.py` (users, settings, weekly timer, test email, MCP tokens), `auth.py` (sign in, sign out, me),
`pages.py` (serves the app shell), `common.py` (shared helpers).

## Scope
Every route validates its request with a model from `app/models.py`, calls one service
function, saves if the service mutated a project, and returns. No business logic lives here.
`common.service(fn, ...)` maps `LookupError` to 404 and `ValueError` to 409. Heavy work
(PDF rendering, SMTP) runs in `run_in_threadpool`.

## Permissions
- `read_permission`: any signed-in user, or anyone when `PUBLIC_READ=true`.
- `require_writer` (admin or entry): logging and correcting work, switches, derails,
  locations, downtime.
- `require_admin`: creating and editing projects, status, equipment, everything under
  `/api/admin`.

## Routes
```
POST /auth/login (5/min)  POST /auth/logout  GET /auth/me
GET  /api/projects                  GET /api/projects/{id}      GET /api/projects/{id}/summary
POST /api/projects (admin)          PATCH /api/projects/{id} (admin)   POST /api/projects/{id}/status (admin)
POST /api/projects/{id}/log                         PATCH  /api/projects/{id}/log/{date}
POST /api/projects/{id}/downtime                    PATCH|DELETE /api/projects/{id}/downtime/{date}
POST /api/projects/{id}/switches                    PATCH|DELETE /api/projects/{id}/switches/{switch_id}
POST /api/projects/{id}/derails                     PATCH|DELETE /api/projects/{id}/derails/{derail_id}
POST /api/projects/{id}/locations                   PATCH|DELETE /api/projects/{id}/locations/{location_id}
GET  /api/equipment                 POST /api/equipment (admin)
POST /api/reports/send (4/min)      POST /api/reports/preview (60/min)   POST /api/reports/pdf (10/min, download)
GET|POST /api/admin/users           PATCH|DELETE /api/admin/users/{email}
GET|PUT  /api/admin/settings        POST /api/admin/settings/test-email (4/min)
GET  /api/admin/scheduler           POST /api/admin/scheduler/run-now
GET|POST /api/admin/mcp-tokens      DELETE /api/admin/mcp-tokens/{jti}
GET  /                              (app shell; assets versioned by a content hash)
```
`tests/test_parity.py` asserts every MCP tool has a route here.

## Notes
- `pages.py` replaces `__ASSETVER__` in `index.html` with a hash of `static/js/*.js` and
  `style.css`, and serves the shell with `Cache-Control: no-cache`.
- The MCP mount at `/mcp` is wired in `app/main.py`, not here.
