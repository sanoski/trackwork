# The command line, for people who would rather be spiking

A friendly walk through the MOW Tracker command line. It reads top to bottom like a short
course, using the fictional Northern Valley Railroad that ships with the demo data, so you
can type every command here on a demo install and see the same answers. The terse version
of all of this is [cli-reference.md](cli-reference.md).

You do not need the command line to use the tracker. The crew logs work on their phones and
the office reads the report. The command line is for whoever looks after the server, and for
anyone who wants to fix a number without opening a browser. It does exactly what the web app
and Claude do, through the same code, on the same files.

## Before we begin: one word, `mow`

Every command starts with `mow`. That is the whole trick. Everything else is what comes after.

`mow` is a short alias you create once. On a Docker install:

```bash
alias mow='docker compose -f /opt/trackwork/docker-compose.yml exec web python scripts/cli.py'
```

On a bare-metal install:

```bash
alias mow='/opt/trackwork/.venv/bin/python /opt/trackwork/scripts/cli.py'
```

Put that line in your `~/.bashrc` so it survives a new terminal. Adjust the path if you
installed somewhere other than `/opt/trackwork`.

Two rules that cover most of what follows:

- **Rule 1.** When in doubt, `mow --help`, or `mow <command> --help`. It always says exactly
  what a command needs.
- **Rule 2.** Nothing here deletes data unless the command has `delete` in its name, or you
  hand `import` the `--replace` flag. Those are marked.

## Chapter 1: the shape of a command

```
mow   log   NVR_ND   --week 2026-08-31
 |     |      |            |
 |     |      |            options: extra details, always start with two dashes
 |     |      the target: which project or line, by its id
 |     the command: what you want to do
 the tool, always first
```

Project ids are short and stable: a job number for a sponsored project (`1187`), a line code
for company work (`NVR_ND`). `mow list` shows them all.

```
$ mow list

ACTIVE
----------------------------------------
  [company] NVR_ND        Northern Valley Railroad, North Division
               3,010 ties installed / no goal

COMPLETE
----------------------------------------
  [sponsored] 1187          Project 1187
               4,160 ties installed / 4,000 (104.0%)
```

Two kinds of work show up there. A **sponsored** project has a tie goal and usually a
deadline, and the tracker keeps score against the goal. A **company** line is ongoing railroad
work with worksites underneath it, and usually no goal. Exactly one project is **active** at a
time: it opens by default in the app and the weekly report covers it.

For the full picture of one job:

```
$ mow summary NVR_ND
{
  "id": "NVR_ND",
  "name": "Northern Valley Railroad, North Division",
  "kind": "company",
  "status": "active",
  "total_ties": 3010,
  "remaining": null,
  "vs_schedule": -590,
  "projected_finish": null,
  "daily_target": 300,
  "avg_daily_output": 250.8,
  ...
}
```

`vs_schedule` is where you stand against the daily target over the days worked. Positive is
ahead, negative is a run of Mondays. `remaining` and `projected_finish` are `null` on a line
without a goal, because there is nothing to count down to.

## Chapter 2: the daily log

This is the part you will use most. At the end of the day, how many ties went in.

```
$ mow add-count NVR_ND 2026-09-07 312 --relay-ties 140 --location millbrook-yard
Saved - 312 ties on Monday 2026-09-07  |  @ millbrook-yard  |  relay: 140  |  running total: 3,322  |  remaining: -
```

Four things: the id, the date as `YYYY-MM-DD`, the tie count, and on a company line, the
worksite. The tracker answers with the new running total.

**Relay ties are part of the total, never on top of it.** 312 ties with 140 relays means 172
new ties went in. You never enter the new count; the tracker subtracts. The report shows both
so the office never mistakes a relay for a new tie.

**Worksite.** A company line has named worksites (a yard, a siding, a town) and a day belongs
to one of them. Use the id shown by `mow locations NVR_ND`, or the name; both work. Logging to
a worksite that does not exist is refused, so add it first (Chapter 4).

**One entry per date.** Try to log the same day twice and you get:

```
$ mow add-count NVR_ND 2026-09-07 312
Error: A daily entry for 2026-09-07 already exists. Correct that day instead of adding it again, or pass a track to add another track's ties to that day.
```

That is the tracker keeping you honest. Fix the day instead:

```
$ mow update-count NVR_ND 2026-09-07 298 --relay-ties 140
Updated - 2026-09-07: day 312 to 298  |  relay: 140  |  @ millbrook-yard  |  running total: 3,308  |  remaining: -
```

Every entry after that date is recalculated. You only ever supply the corrected number.

**Split days.** If the gang worked two tracks, log the day once per track with the same date.
The second entry adds to the first, and the report shows the breakdown:

```
$ mow add-count NVR_ND 2026-09-08 200 --track "Track 1" --location millbrook-yard
$ mow add-count NVR_ND 2026-09-08 90 --track "Track 2" --location millbrook-yard
```

A day is either untracked or fully tracked. If you logged it without a track and want to split
it later, correct the first entry with `--track` and then add the second.

**Reading the log.** The whole thing is long, so slice it:

```
$ mow log NVR_ND --week 2026-08-31
Date         Day          Ties  Relay   VS Tgt    Running  Remaining Loc
--------------------------------------------------------------------------------------
2026-08-31   Monday        310      -      +10      2,190          - millbrook-yard
2026-09-01   Tuesday       295     45       -5      2,485          - millbrook-yard
2026-09-03   Thursday      270    270      -30      2,755          - cedar-falls
2026-09-04   Friday        255    255      -45      3,010          - cedar-falls
```

```
mow log NVR_ND --date 2026-09-07                  # one day
mow log NVR_ND --week 2026-09-02                  # the Sunday-to-Saturday week around that date
mow log NVR_ND --month 2026-09                    # a month
mow log NVR_ND --year 2026                        # the season
mow log NVR_ND --from 2026-08-15 --to 2026-08-31  # any range
```

The work week runs Sunday through Saturday. Saturday's ties count toward the week that is
ending; Sunday opens the next one.

**There are no dumb questions.**

- *I forgot to log Tuesday and it is Friday.* Fine. `add-count` takes any date and everything
  is recalculated in order.
- *Can I delete a day?* No. Correct it to 0 if it was logged by mistake. The entry stays and
  counts nothing.
- *I typed the wrong worksite.* `mow update-count NVR_ND 2026-09-07 298 --location cedar-falls`
  moves the whole day.

## Chapter 3: equipment downtime

When a machine goes down, log it. It shows in the weekly report so the office sees what broke
and for how long.

```
$ mow add-downtime NVR_ND 2026-09-07 Tamper --down-at 09:30 --resumed 10:45 --notes "Hydraulic line blew"
Saved downtime: 2026-09-07 Tamper  |  duration: 75m
```

Times are 24-hour. The duration is worked out for you. If it was down all day and you do not
have a resume time, leave `--resumed` off. Machine names with spaces go in quotes, and the list
of machines is the one under Users & Settings in the app.

```
$ mow downtime NVR_ND
Date         Machine              Down At   Resumed   Duration   Notes
--------------------------------------------------------------------------------
2026-08-20   Spiker/Gauger        08:00     11:45     225m       Broken spike feeder
2026-08-27   Broom                09:20     10:05     45m        Belt replaced
2026-09-02   Tamper               07:00     -         -          Down for the day; electrical
2026-09-07   Tamper               09:30     10:45     75m        Hydraulic line blew
```

Fixing one, and the one command in this chapter that removes something:

```
$ mow update-downtime NVR_ND 2026-09-07 Tamper --resumed 11:00
Updated: 2026-09-07 Tamper  |  09:30 to 11:00  |  90m  |  Hydraulic line blew

$ mow delete-downtime NVR_ND 2026-09-07 Tamper
Deleted: 2026-09-07 Tamper  |  09:30 to 11:00  |  90m  |  Hydraulic line blew
```

Deleting prints everything that was in the entry, so if it was the wrong one you can add it
straight back. When the same machine broke twice in a day, add `--match-down-at 09:30` to
`update-downtime` or `--down-at 09:30` to `delete-downtime` to say which one you mean.

Downtime is tracked for the whole line, not per worksite.

## Chapter 4: worksites, switches, and derails

**Worksites** belong to company lines. Add one before logging work to it:

```
$ mow locations NVR_ND
ID                     Name                          Days   Sw   Dr
------------------------------------------------------------------
cedar-falls            Cedar Falls                      6    1    1
millbrook-yard         Millbrook Yard                   7    2    0

$ mow add-location NVR_ND "Pine Ridge"
Added location 'Pine Ridge' (pine-ridge)

$ mow update-location NVR_ND pine-ridge --new-name "Pine Ridge Siding"
$ mow delete-location NVR_ND pine-ridge
```

The id in parentheses is what the data refers to, so renaming keeps all history. A worksite
that still has work logged against it cannot be deleted.

**Switches and derails** are their own records, not a kind of tie. Each has a name, a date, a
worksite, and a timber breakdown: for each length, how many were planned and how many went
in. `LEN:PLANNED/ACTUAL`, with `:hb` marking a head block.

```
$ mow add-switch NVR_ND "Pine Ridge Switch" 2026-09-07 --timber 9:6/6 --timber 12:3/2 --timber 16:2/2:hb --location millbrook-yard
Added switch 'Pine Ridge Switch' (pine-ridge-switch) on 2026-09-07  |  @ millbrook-yard  |  planned 11 / actual 10  |  3 lengths

$ mow add-derail NVR_ND "Pine Ridge Derail" 2026-09-07 --timber 12:2/2:hb --location millbrook-yard
Added derail 'Pine Ridge Derail' (pine-ridge-derail) on 2026-09-07  |  @ millbrook-yard  |  planned 2 / actual 2  |  1 lengths
```

```
$ mow switches NVR_ND
Date         ID                     Name                         Loc             Plan   Act  Lens
------------------------------------------------------------------------------------------------
2026-08-20   millbrook-north-switch Millbrook North Switch       millbrook-yard    16    17     4
2026-08-27   millbrook-crossover    Millbrook Crossover          millbrook-yard    16    16     4
2026-09-02   cedar-falls-siding-switch Cedar Falls Siding Switch cedar-falls       13    11     4
2026-09-07   pine-ridge-switch      Pine Ridge Switch            millbrook-yard    11    10     3
```

`update-switch` and `update-derail` take the same `--timber` rows and replace the whole
breakdown. `delete-switch` and `delete-derail` remove the record. Switch and derail timbers
count toward Total Timbers Installed in the report, but they are never mixed into the daily
tie count.

## Chapter 5: projects and lines

New funded job? Create it:

```
$ mow create 1204 "Project 1204" --kind sponsored --goal 5000 --deadline 2026-11-15 --daily-target 350
Created sponsored '1204': Project 1204  |  goal: 5,000  |  daily target: 350  |  demoted to complete: NVR_ND
```

Notice the tail of that line. A new project becomes the active one, and the previous active
project moves to complete. Complete projects stay visible and reportable; nothing is lost. If
that was not what you wanted:

```
$ mow set-status NVR_ND active
'NVR_ND' set to active. Demoted to complete: 1204.
```

A company line is the same command with `--kind company --line NVR_ND` and usually no goal.

Goals change, deadlines slip:

```
$ mow update 1204 --goal 5200
Updated '1204': goal_ties=5200
```

Every remaining-ties figure in the log is recalculated when the goal changes.

When a job is finished for good, archive it. It leaves the sidebar but stays on disk, still
exportable:

```
$ mow archive 1187
'1187' archived.
```

## Chapter 6: reports

The weekly report normally sends itself on the timer. From the command line you can build the
same report any time, and `--no-email` with `-o` is the safe way to look at one without
sending it anywhere:

```
$ mow report --project NVR_ND --no-email -o week.pdf
Report generated for August 30 – September 05, 2026 (44,837 bytes)
Saved to week.pdf
```

Shape it the way the wizard does:

```
mow report --project NVR_ND --location millbrook-yard --no-email -o millbrook.pdf   # one worksite
mow report --project 1187 --full --no-email -o 1187.pdf                              # a finished job, first day to last
mow report --project NVR_ND --week 2026-08-19 --no-email -o w34.pdf                  # a particular week
mow report --project NVR_ND --from 2026-08-01 --to 2026-08-31 --no-email -o aug.pdf  # any range
mow report --project NVR_ND --ties relay --no-switches --no-derails --no-email -o relay.pdf
mow report --project NVR_ND --detail itemized --no-email -o long.pdf                 # every switch and derail broken out
mow report --project NVR_ND --recipients boss@example.com                            # build and email it now
```

Without `--no-email` the report goes to the configured recipients, or to `--recipients` if
you give them. There is no confirmation step, so read the command twice.

## Chapter 7: looking after the server

These are the install-time and admin chores. The same things live under Users & Settings in
the app; the command line is for when the browser is not handy.

**Accounts.** Three roles: `admin` does everything, `entry` logs and corrects work, `viewer`
only reads.

```
$ mow user list
admin@example.com                  admin   Pat Admin

$ mow user add crew@example.com "Crew Entry" --role entry         # prompts for a password
$ mow user update crew@example.com --role admin
$ mow user update crew@example.com --set-password                  # prompts
$ mow user delete crew@example.com
```

The last admin cannot be removed, so you cannot lock yourself out.

**Email and names.** `mow settings show` prints everything except the mail password. Set
the organisation name that prints on the report, the mail server, and who gets the weekly
report:

```
$ mow settings set --org "Northern Valley Railroad" --recipients boss@example.com
$ mow settings set --smtp-host smtp.example.com --smtp-port 587 --smtp-user mow@example.com --smtp-password '...' --sender mow@example.com
$ mow settings test-email you@example.com
```

`test-email` sends a short message and prints the exact mail server error if it fails.
Without a mail server everything else still works; reports are built and downloaded instead.

**The weekly timer.**

```
$ mow schedule status
{
  "enabled": true,
  "running": true,
  "schedule": { "enabled": true, "day_of_week": "sun", "hour": 8, "minute": 0, "timezone": "America/New_York" },
  "next_run": "2026-09-13T08:00-04:00"
}

$ mow schedule run-now       # send this week's report immediately
```

**Claude.** When the MCP server is enabled, each person who connects Claude gets their own
token. Tokens expire and can be revoked:

```
$ mow token create pat@example.com "laptop" --days 30
$ mow token list
$ mow token revoke <id>
```

**Data in, data out.**

```
$ mow import /path/to/bundle --overwrite --replace   # load a data bundle; --replace clears existing projects first
$ mow verify                                         # load every project and print counts
$ mow export --year 2026                             # season_2026.db, SQLite, for spreadsheets and archives
```

```
$ mow verify
ID             Status     Days    Ties  Relay   Sw   Dr  Down  Locs
----------------------------------------------------------------------
NVR_ND         active       13   3,308  1,805    4    2     3     2
1187           archived     13   4,160      0    0    0     2     0
----------------------------------------------------------------------
2 project(s), 7,468 ties, 1 user(s)
```

`export` is read-only. The live data stays exactly as it is; the `.db` file is a copy with a
table each for projects, worksites, daily counts, downtime, switches, and derails.

## Quick reference card

| Want to | Type |
|---|---|
| See everything | `mow list`, `mow summary <id>` |
| Log a day | `mow add-count <id> YYYY-MM-DD <ties> --relay-ties N --location <site>` |
| Correct a day | `mow update-count <id> YYYY-MM-DD <ties> [--relay-ties N] [--location <site>]` |
| Read the log | `mow log <id> [--date D \| --week D \| --month YYYY-MM \| --year YYYY \| --from D --to D]` |
| Machine went down | `mow add-downtime <id> YYYY-MM-DD "<machine>" --down-at HH:MM --resumed HH:MM --notes "..."` |
| Fix or remove downtime | `mow update-downtime ...`, `mow delete-downtime ...` |
| Worksites | `mow locations <id>`, `mow add-location <id> "<name>"`, `mow update-location <id> <site> --new-name "..."` |
| Switches and derails | `mow add-switch <id> "<name>" YYYY-MM-DD --timber LEN:PLAN/ACT[:hb] ... --location <site>` (same for derail) |
| New job | `mow create <id> "<name>" --kind sponsored --goal N --deadline YYYY-MM-DD` |
| Change who is active | `mow set-status <id> active` |
| Build a report safely | `mow report --project <id> --no-email -o file.pdf` |
| Accounts | `mow user list \| add \| update \| delete` |
| Mail and names | `mow settings show \| set \| test-email` |
| Timer | `mow schedule status \| run-now` |
| Claude tokens | `mow token list \| create \| revoke` |
| Season's end | `mow archive <id>`, then `mow export --year YYYY` |
| Anything else | `mow --help`, `mow <command> --help` |

That is the whole system. Log counts, fix mistakes, track breakdowns, export at the end of the
year. The computer does the math. You do the ties.
