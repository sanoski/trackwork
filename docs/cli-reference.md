# Command line reference

`scripts/cli.py` does everything the web app and the MCP tools do, plus install-time chores.
It reads the same `.env` and writes the same `DATA_DIR`, so a count logged here shows up in
the app immediately.

```bash
# Docker
docker compose exec web python scripts/cli.py <command> ...
# Bare metal
/opt/trackwork/.venv/bin/python /opt/trackwork/scripts/cli.py <command> ...
```

Make an alias if you use it often: `alias mow='docker compose -f /opt/trackwork/docker-compose.yml exec web python scripts/cli.py'`.
Every command has `--help`.

## Reading

| Command | Shows |
|---|---|
| `list` | every project with kind, status, totals, worksites |
| `summary <id>` | computed stats for one project |
| `log <id> [--date D \| --week D \| --month YYYY-MM \| --year YYYY \| --from D --to D]` | the daily tie log, filtered |
| `downtime <id>` | the downtime log |
| `switches <id>`, `derails <id>` | each with its timber breakdown |
| `locations <id>` | worksites on a company line and how much work references each |

## Logging work

```bash
scripts/cli.py add-count WACR_CRD 2026-06-25 163 --relay-ties 163 --location "St. Johnsbury"
scripts/cli.py add-count WACR_CRD 2026-06-26 200 --relay-ties 200 --track "Track 3" --location st-johnsbury
scripts/cli.py update-count WACR_CRD 2026-06-25 170 --relay-ties 170
scripts/cli.py add-downtime WACR_CRD 2026-06-25 Tamper --down-at 09:15 --resumed 10:40 --notes "hydraulic leak"
scripts/cli.py update-downtime WACR_CRD 2026-06-25 Tamper --resumed 11:00
scripts/cli.py delete-downtime WACR_CRD 2026-06-25 Tamper
```

- `--relay-ties` is a part of the total, never added on top.
- `--track` on `add-count` with a date that already has a different track adds to that day.
  On `update-count` it names which track's portion to correct.
- `--location` takes an id or a display name and must already exist (`add-location`). On
  `update-count` an empty string clears it.
- `--match-down-at` and `--down-at` on the downtime commands pick one entry when a machine
  went down more than once that day.

## Switches, derails, worksites

```bash
scripts/cli.py add-switch WACR_CRD "North Main Switch" 2026-06-22 --timber 9:6/11 --timber 16:2/2:hb --location st-johnsbury
scripts/cli.py update-switch WACR_CRD "North Main Switch" --timber 9:6/11 --timber 16:2/2:hb --timber 12:1/1
scripts/cli.py delete-switch WACR_CRD "North Main Switch"
scripts/cli.py add-derail WACR_CRD "South Derail" 2026-06-17 --derail-type stationary --timber 12:2/2:hb
scripts/cli.py add-location WACR_CRD "St. Johnsbury"
scripts/cli.py update-location WACR_CRD st-johnsbury --new-name "Saint Johnsbury"
scripts/cli.py delete-location WACR_CRD st-johnsbury
```

`--timber LENGTH:PLANNED/ACTUAL[:hb]` is repeatable; on `update-*` it replaces the whole
list. A dash on the source sheet is 0. `:hb` marks a head block. `--date` disambiguates when
two entities share a name.

## Projects

```bash
scripts/cli.py create 942 "Project 942" --kind sponsored --goal 7000 --deadline 2026-06-30 --daily-target 350
scripts/cli.py create WACR_CRD "WACR Connecticut River Division" --kind company --line WACR_CRD --daily-target 350
scripts/cli.py update 942 --goal 7549
scripts/cli.py set-status WACR_CRD active      # demotes the previous active project to complete
scripts/cli.py archive 942
scripts/cli.py export --output mow.db [--year 2026]
```

## Reports

```bash
scripts/cli.py report                                   # last week, active project, emailed to the recipients
scripts/cli.py report --no-email -o week.pdf            # build only
scripts/cli.py report --project 942 --full --no-email -o 942.pdf
scripts/cli.py report --location st-johnsbury --week 2026-06-17 --no-email -o sj.pdf
scripts/cli.py report --ties relay --detail itemized --no-downtime --no-charts
scripts/cli.py report --recipients boss@example.com     # override the configured list for this send
```

Flags: `--project`, `--location`, `--week`, `--full`, `--from`/`--to`, `--ties
new|relay|both|none`, `--detail summary|itemized`, `--no-switches`, `--no-derails`,
`--no-downtime`, `--no-charts`, `--no-email`, `--output`/`-o`. See [reports.md](reports.md).

## Administration

```bash
scripts/cli.py user list
scripts/cli.py user add rt@example.com "R. T." --role admin        # prompts for the password
scripts/cli.py user update rt@example.com --role viewer
scripts/cli.py user update rt@example.com --set-password
scripts/cli.py user delete rt@example.com

scripts/cli.py settings show                                        # password masked
scripts/cli.py settings set --org-name "Vermont Rail System" --recipients "rt@example.com,office@example.com"
scripts/cli.py settings set --smtp-host smtp.office365.com --smtp-port 587 --smtp-user mow@example.com --smtp-password '...' --sender mow@example.com
scripts/cli.py settings set --enable --day sun --hour 8 --minute 0 --timezone America/New_York
scripts/cli.py settings test-email you@example.com

scripts/cli.py schedule status
scripts/cli.py schedule run-now                                     # send this week's report now

scripts/cli.py token list
scripts/cli.py token create rt@example.com "Claude Code on the laptop" --days 90   # printed once
scripts/cli.py token revoke <id>
```

`user add --password` and `settings set --smtp-password` put the secret in your shell history.
Prefer the prompt (`user add` without `--password`, `user update --set-password`) or the app.

## Install and data

```bash
scripts/cli.py import /path/to/bundle [--overwrite] [--replace]   # copy projects/, archived/, users.json, settings.json, config.json into DATA_DIR; --replace clears existing projects first (demo data)
scripts/cli.py verify                                 # load every project, print counts
```

## Exit codes and errors

A rejected command prints one line to stderr and exits 1. Wording matches the app's error
messages ("no location matching ...", "is still referenced by ...").
