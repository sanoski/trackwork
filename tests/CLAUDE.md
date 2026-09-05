# tests/CLAUDE.md, test suite

## Agent instructions: service-layer and API smoke tests

**Module directory:** `tests/`
**Run:** `.venv/bin/python -m pytest -q` from the repo root (needs `requirements-dev.txt`).

## Scope
Fast, dependency-free checks of the service layer: project lifecycle and daily-count math
(`test_storage`), switches, derails, and locations (`test_structures`), downtime
(`test_downtime`), organisation settings and the mail transport guard (`test_settings`),
accounts and the last-admin guard (`test_users`), the weekly timer's once-per-week marker
(`test_scheduler`), and the parity table that ties every MCP tool to its CLI twin
(`test_parity`). Web routes are covered by `test_api` (added with the web parity phase).

`conftest.py` points `DATA_DIR` at a throwaway directory before `app.config` is imported and
wipes it between tests, so the suite never touches real data and never sends mail.

## Notes
- The parity test has an explicit `TWINS` table. Adding an MCP tool without adding its CLI
  twin (and, later, its web route) fails the suite on purpose.
- `test_scheduler` monkeypatches `scheduler.run_report`; it starts and stops a real
  APScheduler instance for the schedule tests.
