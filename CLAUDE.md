# CLAUDE.md, MOW Tracker (trackwork)

Production tracking and weekly PDF reporting for a railroad Maintenance of Way tie gang.
Three ways in (web app, MCP tools for Claude, CLI), one service layer, one data directory.
This file routes; each directory's own CLAUDE.md holds the detail. Read the one for the
directory you are changing before editing.

## Where things live

| Task | Directory | Start with |
|---|---|---|
| Business rules, data, settings, accounts, timer | `app/` | `app/CLAUDE.md` |
| Web API routes and permissions | `app/routes/` | `app/routes/CLAUDE.md` |
| The PDF and preview report | `app/reporting/` | `app/reporting/CLAUDE.md` |
| The browser app | `app/static/` | `app/static/CLAUDE.md` |
| MCP tools and their auth | `mcp_server/` | `mcp_server/CLAUDE.md` |
| The command line | `scripts/` | `scripts/CLAUDE.md` |
| Docker, Caddy, nginx, systemd, setup script | `deploy/` | `deploy/CLAUDE.md` |
| Sample data | `demo/` | `demo/CLAUDE.md` |
| Tests | `tests/` | `tests/CLAUDE.md` |
| Human documentation | `docs/` | `docs/CLAUDE.md` |

## Tree

```
app/            config, models, structures, downtime, storage, mailer, app_settings, auth,
                users, mcp_tokens, scheduler, limiter, main; routes/, reporting/, static/
mcp_server/     server.py (tools), auth.py (provider factory)
scripts/cli.py  every tool as a command, plus report, user, settings, schedule, token, import, verify, export
deploy/         setup.sh, caddy/, nginx/, systemd/, bare-metal.md
demo/data       fictional dataset (seeded by deploy/setup.sh --demo)
docs/           setup, setup-with-ai, user-guide, admin-guide, reports, mcp-and-claude,
                cli-reference, architecture, troubleshooting
tests/          pytest; run .venv/bin/python -m pytest -q
data/           runtime DATA_DIR (gitignored)
```

## Dependency direction (arrows point at what is imported; acyclic)

```
models <- structures, downtime, mailer, config
storage <- config, models, structures
app_settings <- config, models, storage, mailer
auth <- config, models, storage
users <- auth, storage, models
mcp_tokens <- config, storage
reporting <- models, storage, structures, app_settings, mailer
scheduler <- reporting, app_settings, storage, config
routes/*, mcp_server/, scripts/cli.py -> the services above (never each other, never main)
main -> routes, scheduler, limiter, mcp_server
```

## Environment (.env, bootstrap only; settings.json wins once saved)

`SECRET_KEY` (required), `ENVIRONMENT` (production|development), `DATA_DIR` (./data),
`PUBLIC_READ`, `SCHEDULER_ENABLED`, `SMTP_HOST/PORT/USER/PASSWORD`,
`REPORT_EMAIL_RECIPIENT/SENDER`, `MCP_ENABLED`, `MCP_AUTH_PROVIDER`
(token|azure|google|github|none), `MCP_BASE_URL`, `MCP_OAUTH_CLIENT_ID/SECRET/TENANT`,
`TRACKWORK_DOMAIN` (Caddy only).

## Rules that must hold

- Entry points are thin. Every write goes through `app/` services; never re-implement logic
  in a route, tool, or command.
- Every MCP tool has a CLI command and a web route with the same behaviour, added in the
  same change. `tests/test_parity.py` enforces it.
- `running_total`, `remaining`, `vs_target` are recalculated on every write; client values
  are never trusted. All daily-tie writes use `storage.record_daily_count` /
  `storage.update_daily_count`.
- One daily entry per date, optional per-track split, one worksite per day. `relay_ties` is
  a subset of `ties`. Work week is Sunday to Saturday. Exactly one project is `active`.
- Worksites are a managed list referenced by id; unknown worksite is rejected; delete is
  refused while referenced.
- Switches and derails are first-class records, separate from the daily tie count.
- One report template feeds both the HTML preview and the PDF; charts and diagrams are
  inline SVG; `weasyprint` is imported lazily in `reporting.render.build_pdf`; keep the
  bundled Oswald TTFs.
- bcrypt directly, never passlib. No static shared secret for MCP: per-user tokens or OAuth.
- Exactly one uvicorn worker (the weekly timer lives in the process).
- Never log passwords, tokens, or SMTP credentials.
- No em dashes in anything a person reads: docs, UI text, report, commit messages, comments.
- No real people, addresses, or hosts in code, docs, or sample data. Use example.com.

## Working here

- Tests: `.venv/bin/python -m pytest -q`. Dev server:
  `ENVIRONMENT=development .venv/bin/uvicorn app.main:app --reload`.
- Test reports with `scripts/cli.py report --no-email -o out.pdf`; never email anyone while
  developing.
- When you add a capability: service function, then route, tool, command, test, then the
  matching `docs/` page and the directory's CLAUDE.md.
