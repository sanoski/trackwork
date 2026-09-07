# Troubleshooting

## The app will not start

**"SECRET_KEY must be set in .env"**: run `deploy/setup.sh`, or add a line
`SECRET_KEY=<64 hex characters>` to `.env` (generate one with
`python3 -c "import secrets; print(secrets.token_hex(32))"`).

**"MCP_AUTH_PROVIDER=azure needs these settings: ..."**: the OAuth providers need
`MCP_BASE_URL`, `MCP_OAUTH_CLIENT_ID`, and `MCP_OAUTH_CLIENT_SECRET` (`MCP_OAUTH_TENANT` too
for Azure). Fill them in or set `MCP_AUTH_PROVIDER=token`.

**Logs**: `docker compose logs -f web` or `sudo journalctl -u trackwork -f`.

## I cannot sign in

- **Sign-in works over http but the page reloads signed out**: in production the cookie is
  marked secure and the browser drops it over plain HTTP. Use HTTPS, or set
  `ENVIRONMENT=development` for a laptop trial.
- **Behind a reverse proxy the sign-in loops**: the proxy must forward
  `X-Forwarded-Proto: https`. See `deploy/nginx/trackwork.conf.example`.
- **"Too many requests"**: sign-in is limited to 5 attempts a minute per address. Wait a
  minute.
- **Lost the only admin password**: from the host,
  `scripts/cli.py user update <email> --set-password`.

## Email

- **Send Test fails with "SMTP is not configured"**: fill in server, port, username,
  password, and From address under Email & Names and save.
- **Authentication error**: Microsoft 365 and Google both need either an app password or SMTP
  AUTH enabled for the mailbox. The From address should be the mailbox you authenticate as.
- **Connection refused or timed out**: port 587 (STARTTLS) is what the app uses. Check the
  host's outbound firewall.
- **The weekly report never arrives**: open Users & Settings, Weekly Report. It shows whether
  the timer is enabled, the next run, the last run, and the last error. "Nothing to report"
  means no work was logged in the week that just ended, which is by design.
- **No mail server at all**: the wizard's Download PDF works without one. Only Generate &
  Send and the weekly timer need SMTP.
- Run it by hand to see the full message:
  `scripts/cli.py report --no-email -o test.pdf` (builds the PDF without sending) or
  `scripts/cli.py schedule run-now`.

## PDF and preview

- **"cannot load library 'libpango'"** (bare metal): install the apt line from
  `deploy/bare-metal.md`. The Docker image already has it.
- **Headings render in a fallback font**: the Oswald TTFs under
  `app/reporting/templates/fonts/` are missing. Restore them from the repository.
- **The preview in the wizard is blank**: the selected scope has no work in the selected
  period. Widen the period or choose the whole line.

## Data

- **"is already logged at a different location"**: a day is worked at one worksite. Correct
  the existing entry's worksite first, or log the ties under that worksite.
- **"no location matching ..."**: worksites are a managed list. Add it under Worksites (or
  `scripts/cli.py add-location`) before tagging work to it.
- **"is still referenced by ..."** when deleting a worksite: move or delete the tie days,
  switches, and derails that reference it first.
- **Two projects both show as active**: activate the one you want. The app demotes the other
  to complete.
- **Running totals look wrong after a manual edit of a JSON file**: log any count through the
  app, CLI, or Claude; every write recalculates the whole project. Prefer never editing the
  JSON by hand.

## Claude and MCP

- **401 from `/mcp`**: the token is missing, expired, or revoked. Create a new one under
  Users & Settings, AI (Claude), or `scripts/cli.py token create`.
- **A claude.ai custom connector cannot connect with `token` auth**: claude.ai web connectors
  authenticate with OAuth. Switch to `azure`, `google`, or `github`, or use Claude Code or the
  desktop app, which accept a bearer token.
- **"Invalid host header"**: `MCP_BASE_URL` must match the public URL that clients use.

## Docker

- **"bind: address already in use" when starting, or Caddy keeps restarting**: something on
  the host already listens on port 80 or 443 (often another web server). Either stop it, or
  move Caddy to other ports without editing the tracked files. Create
  `docker-compose.override.yml` next to `docker-compose.yml`:

  ```yaml
  services:
    caddy:
      ports: !override
        - "8080:80"
        - "8443:443"
  ```

  Then `docker compose up -d` again. The app is now at `https://HOST:8443/`. If Caddy starts
  but the site does not load, check that `TRACKWORK_DOMAIN` resolves to this host:
  `docker compose logs caddy`.
- **setup.sh stopped after creating the admin**: that is the same port clash, hit at the
  final `docker compose up`. The admin account and any demo data were already written to
  the volume, so fix the ports and run `docker compose up -d` yourself; do not rerun the
  demo seed.
- **Caddy logs "obtaining certificate" errors, or the browser cannot connect over HTTPS**:
  Let's Encrypt could not reach the host name. Check that the DNS record points at this
  machine's public address (`dig +short mow.example.com` from outside), that ports 80 and 443
  are forwarded to it, and that `TRACKWORK_DOMAIN` in `.env` matches the record exactly.
  Caddy retries on its own once those are right; no certificate is ever bought or installed
  by hand.
- **Where is my data?** In the `trackwork-data` volume:
  `docker volume inspect trackwork-data`. See the backup commands in `setup.md`.
