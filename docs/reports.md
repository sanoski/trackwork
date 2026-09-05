# Reports

One report path serves the weekly email, the on-demand wizard, the live preview, and the
command line. They all call the same code with the same options, so a report looks the same
however it was made.

## What the weekly report contains

The report is a Letter-size PDF, usually one page, with the organisation's name in the
header and the week in the title.

**Company line** (no tie goal):

1. **Total Timbers Installed** for the period, the number the office reads first.
2. Cards: switch timbers, switches, derails, new ties, relay ties, days worked.
3. Charts: weekly timber production, cumulative timbers, work composition (new, relay,
   switch, derail), and, on a whole-line report, timbers by worksite.
4. **Switches** and **Derails** blocks. By default all switches in the period are summed into
   one "timbers by length" chart and one combined planned versus actual table, with a line
   listing which switches are included. Derails likewise.
5. **Tie Production**: the daily log with new, relay, and total columns when relay ties
   exist, and the running total. A day split across tracks shows the split under its date.
6. **Equipment Downtime**: machine, time down, back in service, duration, notes.

**Sponsored project** (has a goal):

1. Cards: total ties installed, remaining, versus schedule, average daily output, percent
   complete, projected finish.
2. A progress bar.
3. This week's output against the daily target, and cumulative versus target.
4. The daily log and downtime.

Sections with nothing in them are left out.

## Relay ties

`relay` is a part of `ties`, never added on top. If the crew put in 300 ties of which 120
were relay, the day is 300 ties, 120 relay, 180 new. The report always shows relay and new
separately so the office never mistakes reclaimed ties for new ones.

## Scope and period

- **Scope**: the active project by default. Any project by id. On a company line, the whole
  line or one worksite.
- **Period**: the most recently completed Sunday-to-Saturday week by default. Any week
  (give a date in it), the full project span, or a date range. The wording of the headings
  follows the period.
- **Nothing to report**: if no ties or switch and derail timbers were logged in the period,
  no PDF is built and no email is sent. This gate looks at the whole project regardless of
  which sections are toggled on, so switching sections off cannot produce a blank report.

## Options

| Option | Values | Default |
|---|---|---|
| ties | `both`, `new`, `relay`, `none` | `both` |
| detail | `summary` (consolidate switches and derails), `itemized` (a diagram and table per switch and derail) | `summary` |
| switches, derails | on or off | on (company lines) |
| charts | on or off | on |
| downtime | on or off | on for a whole line; off automatically for a single worksite, since downtime is logged at line level |

`itemized` makes a longer report. Use it when someone needs each switch broken out.

## Three ways to make one

**The weekly timer.** Users & Settings, Weekly Report. Sends the default report for the
active project to the configured recipients. Once per week, on the schedule you set.

**The wizard.** The Report button in the app header. Pick scope, period, and options, watch
the preview, type a recipient, send. The recipient is whatever you type.

**The command line.**

```bash
scripts/cli.py report --no-email -o week.pdf                     # last week, active project, saved not sent
scripts/cli.py report --project 942 --full --no-email -o 942.pdf # a finished job, its whole span
scripts/cli.py report --project WACR_CRD --location st-johnsbury --week 2026-06-17 --no-email -o sj.pdf
scripts/cli.py report --ties relay --no-switches --no-derails    # relay ties only, emailed to the recipients
scripts/cli.py report --detail itemized --from 2026-06-01 --to 2026-06-30 --no-email -o june.pdf
```

`--no-email` builds without sending. Without `-o` the PDF is not kept after sending.

## Testing without emailing anyone

`--no-email` plus `-o` is the safe way to look at a report. Send Test under Email & Names
proves the mail settings without sending a report. If you want the real thing delivered to
yourself, use the wizard and type your own address.

## How it is built

`app/reporting/` turns projects into a view model, renders one Jinja template
(`templates/report.html` plus `report.css`) to HTML for the preview and, through WeasyPrint,
to PDF for email. Charts and the switch and derail diagrams are inline SVG, because the PDF
renderer runs no JavaScript. The Oswald heading font is bundled. See
[architecture.md](architecture.md).
