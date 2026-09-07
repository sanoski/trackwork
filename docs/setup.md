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

## Where to run it

Anywhere a Linux box with Docker can sit behind a host name. The app is small (one container,
under a gigabyte of memory with the PDF renderer) and its data is a single directory, so the
choice is about who looks after the machine, not about capacity.

- **A server your organisation already runs.** The usual choice. Follow Path A below.
- **A rented virtual server (VPS).** Any cloud provider's smallest Linux VM with 1 GB of memory
  is enough. Point a DNS name at it, open ports 80 and 443, run Path A. Back up the data volume
  off the machine (see Backups).
- **A small computer in the office**, such as a Raspberry Pi 5. The image builds on arm64 and
  this is how the project was developed. For access from outside the office you need either a
  port forward with a DNS name, or a tunnel service that publishes a local port on a public
  host name; the app does not care which.
- **Your own reverse proxy or HTTPS setup.** Drop the bundled Caddy and proxy to port 8000; see
  "Behind your own reverse proxy" below.

Whichever you pick, the requirements are the same: a host name, HTTPS in front (sign-in
cookies are marked secure), one running copy of the app (the weekly timer must not be
duplicated), and a backup of the data directory.

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

### HTTPS and certificates

You do not buy or install a certificate. The bundled Caddy web server gets one from Let's
Encrypt, a free public certificate authority, the first time it starts with a real host name,
and renews it on its own every couple of months for as long as the app runs. Browsers trust
these certificates exactly like paid ones. There is no account to create and nothing to
remember later.

Two things have to be true for that to work:

1. **The host name resolves to this machine.** Create a DNS record (for example
   `mow.example.com`) pointing at the server's public address before you run setup, and
   answer setup's host name question with that name. It lands in `TRACKWORK_DOMAIN` in `.env`.
2. **Ports 80 and 443 are reachable from the internet.** Let's Encrypt proves you control the
   name by connecting to it. Behind an office firewall or router, forward both ports to the
   server.

If either is missing, Caddy keeps retrying and logs why: `docker compose logs caddy`. Until it
succeeds the site is not reachable over HTTPS, and the app requires HTTPS in production.

For a trial with no public name, answer `localhost`. Caddy then signs a certificate itself;
your browser will warn once, which is expected, and `https://localhost/` works.

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
project files are always copied. Add `--replace` to remove every project already in the data
directory first. Do this if you installed with `--demo`: the sample railroad must not sit
beside real data, or two projects would be active at once. Accounts are never touched by an
import. Then run `scripts/cli.py verify` to load every project and print its counts.

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
