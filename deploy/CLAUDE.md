# deploy/CLAUDE.md, packaging and hosting

## Agent instructions: how the app is run on a server

**Module directory:** `deploy/` plus the root `Dockerfile`, `docker-compose.yml`,
`.dockerignore`, and `.env.example`.
**Files:** `setup.sh` (first-run helper), `caddy/Caddyfile`, `nginx/trackwork.conf.example`,
`systemd/trackwork.service`, `bare-metal.md`.

## Scope
Two supported paths. Docker (default): `docker compose up` runs one `web` container (uvicorn,
one worker, the weekly timer inside) and a `caddy` container that terminates HTTPS. Bare
metal: a venv, the same uvicorn command under systemd, Caddy or nginx in front. Both keep all
data in one directory (`DATA_DIR`, the `/data` volume in Docker).

## Rules
- Exactly one uvicorn worker, always. Two workers would run two weekly timers.
- The image is Debian slim, never Alpine: WeasyPrint needs the Pango stack listed in the
  Dockerfile (the same apt line is in `bare-metal.md`).
- `.env` holds bootstrap secrets only (SECRET_KEY, first-run mail defaults, MCP settings).
  Recipients, mail, and the schedule are edited in the app afterwards.
- `--proxy-headers` is on so the rate limiter sees real client addresses behind the proxy.

## Notes
- `setup.sh --demo` seeds `demo/data` through `cli import`.
- The MCP server is mounted inside the same process at `/mcp` when `MCP_ENABLED=true`.
