# MOW Tracker (trackwork)

Production tracking and weekly reporting for a railroad Maintenance of Way tie gang.

The crew logs what went in each day: ties (new and relay), switch and derail timbers, and
equipment downtime. The tracker keeps the running totals, shows the job on a dashboard that
works on a phone, and emails the boss a one-page PDF report every week without anyone having
to remember.

Built by Peaches for the VRS MOW crew.

## Three ways in, one source of truth

Every way of entering data calls the same service code and writes the same files, so it does
not matter which one a person uses.

```
   Phone or laptop           Claude (AI assistant)           Terminal
   +---------------+         +-------------------+         +---------------+
   |  Web app      |         |  MCP server       |         |  scripts/cli  |
   |  Log Work,    |         |  "log 340 ties    |         |  add-count,   |
   |  Manage, ...  |         |   at St. J today" |         |  report, ...  |
   +-------+-------+         +---------+---------+         +-------+-------+
           |                           |                           |
           +---------------------------+---------------------------+
                                       |
                            +----------v-----------+
                            |  app/  service layer |
                            |  storage, structures,|
                            |  reporting, settings |
                            +----------+-----------+
                                       |
                            +----------v-----------+
                            |  data/  JSON files   |
                            |  one file per project|
                            +----------------------+
```

- **Web app**: the everyday path. Big buttons, works on a phone in the field. Sign in, tap
  Log Work, type the count. Admins manage users, email, and the weekly schedule from the
  same app.
- **Claude**: the app ships an MCP server. Connect it to Claude and log work by talking:
  "we put in 412 new ties on Track 2 at St. Johnsbury today, and the tamper was down from
  9 to 11." Claude calls the same tools the web app uses.
- **Command line**: every action is also a `scripts/cli.py` command, for scripts, backfills,
  and the day the AI is not available.

## What it tracks

- **Sponsored projects** (a funded job with a tie goal and a deadline): progress, remaining,
  percent complete, projected finish, output against the daily target.
- **Company lines** (ongoing work on a railroad division): total timbers installed, split
  into new ties, relay ties, switch timbers, and derail timbers, by week and by worksite.
- **Switches and derails** as first-class records with a planned versus actual timber
  breakdown by length, drawn as schematic diagrams.
- **Worksites** on a line (a yard, a siding, a town) so a report can cover the whole line or
  one site.
- **Equipment downtime** by machine, with the duration computed for you.

## The weekly report

One PDF, usually a single page, styled for the railroad. It leads with the number the office
cares about, then charts, switch and derail blocks, the tie log, and downtime. The weekly
timer inside the app sends it on the day and time you choose. Anyone signed in can also
compose a report on demand: pick a worksite, a week, a date range, or the whole project,
choose what to include, watch the live preview, and email it or download the PDF. Email is
optional: without a mail server the app still builds every report for download.

## Quick start (Docker)

You need a Linux host with Docker and Docker Compose, and a host name that points at it if
you want HTTPS from Let's Encrypt. For a trial on a laptop, `localhost` works.

```bash
git clone https://github.com/sanoski/trackwork.git
cd trackwork
deploy/setup.sh --demo
```

The setup script writes `.env` with a fresh secret, builds the image, seeds a demo dataset,
asks you to create the first admin account, and starts the app behind Caddy. Open
`https://<your host>/` and sign in. Leave out `--demo` for an empty install; if you used it and
later import real data, add `--replace` to the import so the sample railroad is removed.

Then, in the app, open **Users & Settings**:

1. **Email & Names**: your organisation name, the SMTP server that sends mail, and who
   receives the weekly report. Use **Send Test** to prove it works. Skip the mail server
   if you only want reports downloaded from the wizard.
2. **Weekly Report**: the day, time, and time zone the report goes out.
3. **Users**: add the crew. `entry` can log work, `viewer` can only look, `admin` can do
   everything.

Full instructions, including the no-Docker path, are in [docs/setup.md](docs/setup.md).
If you would rather have an AI assistant walk you through it, paste
[docs/setup-with-ai.md](docs/setup-with-ai.md) into Claude.

## Documentation

| Read this | If you are |
|---|---|
| [docs/setup.md](docs/setup.md) | installing it (Docker or bare metal) |
| [docs/setup-with-ai.md](docs/setup-with-ai.md) | installing it with Claude's help |
| [docs/user-guide.md](docs/user-guide.md) | on the crew, logging work and reading the dashboard |
| [docs/admin-guide.md](docs/admin-guide.md) | the admin: users, email, schedule, projects, backups |
| [docs/reports.md](docs/reports.md) | anyone who wants to know what the PDF says and how to shape it |
| [docs/mcp-and-claude.md](docs/mcp-and-claude.md) | connecting Claude, and the full tool list |
| [docs/cli-reference.md](docs/cli-reference.md) | using the command line |
| [docs/architecture.md](docs/architecture.md) | a developer changing the code |
| [docs/troubleshooting.md](docs/troubleshooting.md) | stuck |

The repository also carries `CLAUDE.md` files in each directory. They are written for an AI
coding assistant so that Claude (or a similar tool) can maintain the project with the same
rules a human developer would follow.

## Stack

Python 3.12, FastAPI, Pydantic, WeasyPrint for the PDF, APScheduler for the weekly timer,
FastMCP for the AI tools. No database server: each project is one JSON file under `data/`,
written atomically. The browser app is plain HTML, CSS, and ES modules with no build step.

## License

MIT. See [LICENSE](LICENSE).
