"""Weekly report email: subject, filename, and body.

Delivery goes through app.mailer. Who receives the report and how it is sent come from
app_settings, which the admin screen edits, so changing a recipient never touches a file.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from .. import app_settings, mailer
from ..structures import slugify


def send_email(pdf_bytes: bytes, week_start: date, week_end: date,
               recipients: Optional[list[str]] = None,
               scope_label: Optional[str] = None) -> list[str]:
    """Email the report PDF. Sends to `recipients` when given (on demand from the portal),
    otherwise to the configured report recipients (the weekly schedule). `scope_label` (a
    worksite name) labels a location-scoped report in the subject, filename, and body.
    Raises RuntimeError on incomplete mail settings or no recipient; the caller handles it."""
    cfg = app_settings.get_settings()
    if recipients is None:
        recipients = list(cfg.report_recipients)
    if not [r for r in recipients if r and r.strip()]:
        raise RuntimeError("No recipient address configured; set report recipients in Settings")

    label = f" ({scope_label})" if scope_label else ""
    span = f"{week_start.strftime('%b %d')} to {week_end.strftime('%b %d, %Y')}"
    subject = f"{cfg.org_name} {cfg.app_name} weekly report{label}: week of {span}"
    fname_loc = f"{slugify(scope_label)}_" if scope_label else ""
    filename = f"{slugify(cfg.app_name)}_report_{fname_loc}{week_start}.pdf"

    scope_line = f" for {scope_label}" if scope_label else ""
    covers = ("ties, switch timbers, and project totals for this worksite" if scope_label
              else "ties, switch timbers, project totals, and equipment downtime")
    body = (f"Attached is this week's MOW progress report{scope_line} "
            f"({week_start.strftime('%B %d')} to {week_end.strftime('%B %d, %Y')}). "
            f"It covers {covers}.\n\n"
            f"This report was generated automatically by the {cfg.org_name} {cfg.app_name}.")
    return mailer.send_message(cfg.smtp, cfg.report_sender, recipients, subject, body,
                               attachment=pdf_bytes, filename=filename)
