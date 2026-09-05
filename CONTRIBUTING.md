# Contributing

Thanks for keeping this useful for the crew.

## Setting up

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env            # set SECRET_KEY and ENVIRONMENT=development
.venv/bin/python scripts/cli.py import demo/data --overwrite
.venv/bin/python scripts/cli.py user add you@example.com "You" --role admin
.venv/bin/uvicorn app.main:app --reload --port 8000
```

The PDF renderer needs the Pango libraries listed in `deploy/bare-metal.md`.

## Before you open a pull request

- `.venv/bin/python -m pytest -q` passes.
- A new capability has all three doors: a service function in `app/`, a web route, an MCP
  tool, and a CLI command. `tests/test_parity.py` checks the tool, command, and route lists.
- Docs updated: the matching file in `docs/` and the `CLAUDE.md` in the directory you changed.
- No em dashes in anything a person reads. No real names, addresses, or hosts in code, docs,
  or sample data.
- Commit messages say what changed and why, in plain sentences.

## Style

Python: type hints, small functions, docstrings that say what a function is for. Services
raise `LookupError` and `ValueError`; entry points translate. JavaScript: ES modules, no
framework, no build step, `api.js` is the only fetch layer. Keep the phone layout working.

## Reporting a problem

Open an issue with what you did, what you expected, what happened, and the relevant lines
from `docker compose logs web` or `journalctl -u trackwork`. Never paste passwords, tokens, or
SMTP credentials.
