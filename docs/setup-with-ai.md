# Setting up with an AI assistant

If you would rather be walked through the install by an assistant, open Claude (claude.ai,
the desktop app, or Claude Code in a terminal on the server) and paste the prompt below.
It tells the assistant what this project is and how to guide you. Answer its questions; it
will give you the commands one step at a time and help when something goes wrong.

Claude Code is the best fit because it can run the commands for you on the server. In the
web or desktop app, you will copy commands into a terminal yourself.

## The prompt

Copy everything between the lines.

---

I am setting up MOW Tracker, an open source web app that tracks railroad tie installation
for a Maintenance of Way crew and emails a weekly PDF report. The repository is at
https://github.com/sanoski/trackwork and the install guide is `docs/setup.md`. Please guide
me through the install one step at a time. Ask before assuming.

Facts about the project you should rely on:

- It is a Python 3.12 FastAPI app. Docker is the recommended path: `deploy/setup.sh` writes
  `.env`, builds the image, creates the first admin, and starts `docker compose` with a
  Caddy container that terminates HTTPS. `deploy/setup.sh --demo` also seeds sample data.
- Without Docker, `deploy/bare-metal.md` covers apt packages (the PDF renderer WeasyPrint
  needs Pango), a venv, `deploy/setup.sh --bare`, and a systemd unit. Exactly one uvicorn
  worker, always: the weekly report timer runs inside the process.
- All data lives in one directory, `DATA_DIR` (`/data` in Docker, a named volume called
  `trackwork-data`). Backing up that directory backs up everything.
- Sign-in cookies are secure, so production needs HTTPS and a DNS name. For a trial the host
  name `localhost` gives a locally issued certificate.
- After the install, the admin finishes configuration inside the app under Users & Settings:
  SMTP and recipients (with a Send Test button), the weekly schedule (day, time, time zone),
  and user accounts with roles admin, entry, or viewer.
- The command line tool is `scripts/cli.py` (`docker compose exec web python scripts/cli.py`).
  Useful commands: `user add`, `settings show`, `settings test-email`, `schedule status`,
  `report --no-email -o test.pdf`, `import <bundle> --overwrite`, `verify`.
- Optional: the app has an MCP server at `/mcp` for AI assistants. `MCP_ENABLED=true` turns it
  on. `MCP_AUTH_PROVIDER=token` issues per-user tokens from the app (works with Claude Code
  and the desktop app); `azure`, `google`, or `github` use an OAuth app and are what
  claude.ai web connectors need. `docs/mcp-and-claude.md` has the details.
- Never suggest putting real passwords in a chat message. Tell me to type them at the prompt.

Start by asking me: whether the server has Docker, whether I have a DNS name pointed at it,
and whether I was given a data bundle to import.

---

## What to expect

A typical session runs: confirm Docker and the DNS name, clone, run `deploy/setup.sh`, sign
in, set up email and send a test, set the schedule, add users, then optionally import the
data bundle and connect Claude. Fifteen minutes on a host that already has Docker.
