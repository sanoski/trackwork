# app/reporting/CLAUDE.md, the weekly report

## Agent instructions: one report path for the CLI, the timer, the API, and the preview

**Module directory:** `app/reporting/`
**Files:** `run.py`, `data.py`, `options.py`, `charts.py`, `diagrams.py`, `render.py`,
`email.py` (send + `report_filename`, shared with the portal download), `templates/report.html`, `templates/report.css`, `templates/fonts/Oswald-*.ttf`.

## Scope
Turn projects (optionally scoped to one worksite) into a report: HTML for the portal preview,
PDF for email. ONE Jinja template feeds both. Charts and switch/derail diagrams are inline SVG
(WeasyPrint runs no JavaScript). This package never imports `app.routes`, `app.main`, or
`app.scheduler`, and knows nothing about who asked for the report.

## Public interface
- `run_report(project_id=None, location=None, *, week=None, full=False, start=None, end=None,
  ties=None, detail=None, switches=True, derails=True, downtime=True, charts=True,
  email=True, recipients=None, output=None) -> RunResult`. The one orchestration entry:
  scope, period, activity gate (no work logged means no report and no email), options,
  render, save, send. Used by `cli report`, `scheduler.run_weekly`, and the admin run-now.
- `build_html(projects, period, options, *, scope_label=None, location=None, font_base=...)`
  and `build_pdf(...)` (weasyprint is imported lazily inside `build_pdf`).
- `send_email(pdf, week_start, week_end, recipients=None, scope_label=None)`; recipients and
  mail settings come from `app_settings`; delivery via `app.mailer`.
- Period helpers: `Period`, `week_period`, `full_period`, `range_period`, `resolve_period`,
  `resolve_report_week`, `week_activity`, `scope_projects`, `build_summary`, `default_options`.

## Notes
- Oswald is bundled as `@font-face` (the PDF embeds it; the portal serves the same files at
  `/report-assets/fonts`). Do not delete the TTFs.
- The default period is the most recently completed Sunday-to-Saturday week.
- `entity_detail="summary"` consolidates all switches (and all derails) into one block each;
  `"itemized"` draws every one.
