# scripts/CLAUDE.md, the command line

## Agent instructions: one command per capability, services only

**Module directory:** `scripts/`
**Files:** `cli.py` (the whole CLI; `build_parser()` and `main()`), `make_train.py` (builds
the sign-in screen's train sprite from source frames; not needed at runtime).

## Scope
`cli.py` mirrors every MCP tool as a command and adds the install and admin chores:
`report`, `user`, `settings`, `schedule`, `token`, `import`, `verify`, `export`. It imports
only `app/` services (never `app.routes`, never `mcp_server`), parses arguments, calls one
function, saves when needed, prints. Errors: `_die(msg)` prints to stderr and exits 1.

## Conventions
- Positional `id` first, then the natural arguments, then options. Dates are `YYYY-MM-DD`
  (`_parse_date`). Times are `HH:MM`.
- Timbers: repeatable `--timber LENGTH:PLANNED/ACTUAL[:hb]`; on update it replaces the list.
- Worksites: `--location` accepts an id or a display name and must already exist.
- Secrets: prefer prompts (`user add` without `--password`, `user update --set-password`);
  the `--password` flags exist for scripts and warn about shell history in their help.
- `report` calls `reporting.run_report` with the same options as the timer and the API.
- `import` copies a bundle (`projects/`, `archived/`, `users.json`, `settings.json`,
  `config.json`) into `DATA_DIR`; `verify` loads every project and prints counts. Both are
  copy-and-count only, no transformation.

## Notes
- `tests/test_parity.py` reads `build_parser()` to check that every tool has a command.
- Help strings are public text: plain sentences, no em dashes.
- `docs/cli-reference.md` must list every command; update it in the same change.
