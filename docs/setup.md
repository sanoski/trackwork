# Setup

Two supported ways to run MOW Tracker. Docker is the default because it carries the PDF
renderer's native libraries for you. Bare metal is the same app under systemd.

Either way, everything the app writes lives in one directory (`DATA_DIR`): project files,
accounts, settings, the weekly timer's state, and AI tokens. Back that directory up and you
have backed up everything.

## What you need

- A Linux host (amd64 or arm64; the Docker image was built and tested on a Raspberry Pi 5,
  which runs it comfortably).
- A DNS name pointing at the host if you want browser-trusted HTTPS. Sign-in cookies are
  marked secure, so in production the app must be reached over HTTPS.
- Optional: an SMTP account that can send mail (any Microsoft 365, Google Workspace, or hosted
  mailbox works). You can add this later in the app. Without it, reports are downloaded from
  the wizard instead of emailed, and the weekly timer stays off.

## Path A: Docker (recommended)

```bash
git clone https://github.com/sanoski/trackwork.git
cd trackwork
deploy/setup.sh            # add --demo to seed the sample data
```

What the script does:

1. Copies `.env.example` to `.env` and generates a random `SECRET_KEY`.
2. Asks for the public host name. Caddy uses it to get a Let's Encrypt certificate. Answer
   `localhost` for a trial and Caddy issues a local certificate instead (your browser will
   warn once).
3. Builds the image and, with `--demo`, imports `demo/data`.
4. Creates the first admin account (email, name, password prompt).
5. Runs `docker compose up -d`.

Open `https://<host>/` and sign in. Ports 80 and 443 must be reachable.

Running the CLI inside the container:

```bash
docker compose exec web python scripts/cli.py --help
```

Updating to a new version:

```bash
git pull
docker compose build
docker compose up -d
```

Your data is in the `trackwork-data` volume and survives rebuilds.

### Behind your own reverse proxy

If you already terminate HTTPS elsewhere, remove the `caddy` service from
`docker-compose.yml`, uncomment the `ports` block on `web`, and proxy to port 8000. Pass the
`Host`, `X-Forwarded-For`, and `X-Forwarded-Proto` headers (see
`deploy/nginx/trackwork.conf.example`).

## Path B: bare metal

Follow [deploy/bare-metal.md](../deploy/bare-metal.md). In short: apt install Python and the
Pango libraries, create a service user, clone into `/opt/trackwork`, make a venv, run
`deploy/setup.sh --bare`, install the systemd unit, put Caddy or nginx in front.

Run exactly one uvicorn worker. The weekly report timer lives inside the process, and two
workers would send two reports.

## Configuration

`.env` holds bootstrap values only. Once the app is running, organisation settings are edited
in **Users & Settings** and stored in `DATA_DIR/settings.json`, which wins over `.env`.

| Variable | Meaning | Default |
|---|---|---|
| `SECRET_KEY` | Signs sign-in cookies and AI tokens. Required. Changing it signs everyone out and invalidates every AI token. | none |
| `ENVIRONMENT` | `production` marks cookies secure (HTTPS only). `development` for a laptop over plain HTTP. | `production` |
| `TRACKWORK_DOMAIN` | Host name Caddy serves (Docker only). | `localhost` |
| `DATA_DIR` | Where data lives. Docker sets `/data`. | `./data` |
| `PUBLIC_READ` | Let anyone view the dashboard without signing in. Writes always need an account. | `false` |
| `SCHEDULER_ENABLED` | Run the weekly report timer inside the app. | `true` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | First-run mail defaults. | empty, 587 |
| `REPORT_EMAIL_RECIPIENT`, `REPORT_EMAIL_SENDER` | First-run recipients (comma separated) and From address. | empty |
| `MCP_ENABLED` | Serve the AI tools at `/mcp`. | `false` |
| `MCP_AUTH_PROVIDER` | `token`, `azure`, `google`, `github`, or `none`. See [mcp-and-claude.md](mcp-and-claude.md). | `token` |
| `MCP_BASE_URL` | Public URL of the app, needed by the OAuth providers. | empty |
| `MCP_OAUTH_CLIENT_ID`, `MCP_OAUTH_CLIENT_SECRET`, `MCP_OAUTH_TENANT` | OAuth app credentials (tenant is Azure only). | empty |

After changing `.env`, restart: `docker compose up -d` or `sudo systemctl restart trackwork`.

## First things to do in the app

1. **Users & Settings, Email & Names.** Set the organisation name (it appears on the report),
   the SMTP server, the From address, and the recipients. Click **Send Test** and check the
   inbox. No mail server yet? Set the organisation name and move on; the Download PDF
   button in the wizard works without one.
2. **Users & Settings, Weekly Report.** Pick the day, time, and time zone. The default is
   Sunday at 08:00, which covers the Sunday-to-Saturday week that just ended.
3. **Users.** Add accounts. Roles:
   - `admin`: everything, including users, settings, projects, and the weekly timer.
   - `entry`: log and correct work, switches, derails, worksites, downtime.
   - `viewer`: read only.
4. **Projects.** Create the first project (a sponsored job with a goal, or a company line),
   then add its worksites under **Worksites**.

## Importing existing data

If you were handed a data bundle (a directory containing `projects/`, optionally `archived/`,
`users.json`, `settings.json`, and `config.json`):

```bash
# Docker
docker compose run --rm -v /path/to/bundle:/seed:ro web python scripts/cli.py import /seed --overwrite
# Bare metal
.venv/bin/python scripts/cli.py import /path/to/bundle --overwrite
```

`--overwrite` replaces `users.json`, `settings.json`, and `config.json` if they already exist;
project files are always copied. Then run `scripts/cli.py verify` to load every project and
print its counts.

## Backups

Everything is in `DATA_DIR`. Copy it.

```bash
# Docker: archive the volume to the current directory
docker run --rm -v trackwork-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/trackwork-data-$(date +%F).tgz -C /data .
# Bare metal
tar czf trackwork-data-$(date +%F).tgz -C /opt/trackwork/data .
```

Restoring is the reverse: stop the app, unpack into the data directory, start it.
`scripts/cli.py export` also writes a SQLite file of every project for analysis in other tools.
