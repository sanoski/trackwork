# demo/CLAUDE.md, sample data

**Module directory:** `demo/`
**Files:** `make_demo.py` (generator), `data/` (its output: `projects/`, `archived/`,
`settings.json`, `config.json`), `README.md`.

## Scope
A fictional dataset for trials and screenshots. `deploy/setup.sh --demo` and
`scripts/cli.py import demo/data --overwrite` copy it into `DATA_DIR`.

## Rules
- Regenerate with `python demo/make_demo.py`; never hand-edit `data/`. The generator calls
  the real services (`storage`, `structures`, `downtime`, `app_settings`) so running totals
  and ids are always consistent with the code.
- Nothing real: no real railroad names, towns, people, addresses, or credentials. No
  `users.json` in the bundle, ever; setup creates the first admin interactively.
- Dates are relative to the generation date (anchored to the last completed Sunday-to-Saturday
  week) so "last week" has work.
