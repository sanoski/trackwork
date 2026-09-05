# mcp_server/CLAUDE.md, the MCP tools for Claude

## Agent instructions: thin tools over the service layer, with pluggable auth

**Module directory:** `mcp_server/`
**Files:** `server.py` (the `FastMCP("MOW Tracker")` instance and every tool), `auth.py`
(`build_auth()`, `allowed_hosts()`).

## Scope
Each tool validates its arguments, calls one function in `app/` (storage, structures,
downtime, reporting.build_summary), saves the project if it was mutated, and returns plain
dicts. Tools return `{"error": "..."}` on failure; they never raise to the client. The server
is mounted inside the web app at `/mcp` by `app/main.py` when `MCP_ENABLED=true`, sharing the
process and the per-file locks. `python mcp_server/server.py` runs it alone on port 8001
for development.

## Tools and their twins
| Tool | CLI command | Web route |
|---|---|---|
| list_projects, get_project_summary, get_daily_log, get_downtime_log | list, summary, log, downtime | GET /api/projects, /{id}, /{id}/summary |
| get_switches, get_derails, get_locations | switches, derails, locations | GET /api/projects/{id} |
| add_daily_count, update_daily_count | add-count, update-count | POST /log, PATCH /log/{date} |
| add_downtime, update_downtime, delete_downtime | add-downtime, update-downtime, delete-downtime | POST, PATCH, DELETE /downtime |
| add_switch, update_switch, delete_switch | add-switch, update-switch, delete-switch | POST, PATCH, DELETE /switches |
| add_derail, update_derail, delete_derail | add-derail, update-derail, delete-derail | POST, PATCH, DELETE /derails |
| add_location, update_location, delete_location | add-location, update-location, delete-location | POST, PATCH, DELETE /locations |
| create_project, update_project, set_status | create, update, set-status | POST /api/projects, PATCH /{id}, POST /{id}/status |

`tests/test_parity.py` holds this table as code. Add a tool only together with its command
and route.

## Auth (`auth.py`)
`MCP_AUTH_PROVIDER`: `token` (default) verifies the app's own per-user JWTs from
`app/mcp_tokens.py` through `TrackworkTokenVerifier`; `azure`, `google`, `github` return
FastMCP's OAuth proxy providers (they need `MCP_BASE_URL`, client id and secret, and for
Azure the tenant); `none` disables auth for local development. `allowed_hosts()` is the
public host from `MCP_BASE_URL` plus localhost. Never add a static shared bearer secret.

## Notes
- Docstrings are what Claude reads to decide how to call a tool. Keep them precise about
  units, subsets (relay within ties), and disambiguation (`date`, `down_at`).
- Dates are ISO strings; tools parse them and return `{"error": "Invalid date, expected
  YYYY-MM-DD"}` on bad input.
- No em dashes in docstrings; they are shown to people in some clients.
