"""Outbound mail transport.

One place that speaks SMTP, used by the weekly report and by the admin "send test email"
action. Knows nothing about reports or where settings are stored; it is handed an
SmtpSettings and a message.
"""
from __future__ import annotations

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from .models import SmtpSettings


def send_message(smtp: SmtpSettings, sender: str, recipients: list[str], subject: str,
                 body: str, attachment: Optional[bytes] = None,
                 filename: Optional[str] = None, subtype: str = "pdf") -> list[str]:
    """Send one message over STARTTLS and return the recipients used. Raises RuntimeError
    when the mail settings are incomplete or no recipient is given; SMTP errors propagate."""
    missing = [label for label, value in (("SMTP host", smtp.host),
                                          ("SMTP user", smtp.user),
                                          ("SMTP password", smtp.password)) if not value]
    if missing:
        raise RuntimeError(f"Missing settings: {', '.join(missing)}")
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        raise RuntimeError("No recipient address provided")
    sender = sender or smtp.user

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    if attachment is not None:
        att = MIMEApplication(attachment, _subtype=subtype)
        att.add_header("Content-Disposition", "attachment", filename=filename or "attachment")
        msg.attach(att)

    with smtplib.SMTP(smtp.host, smtp.port, timeout=30) as conn:
        conn.ehlo()
        conn.starttls()
        conn.login(smtp.user, smtp.password)
        conn.send_message(msg)
    return recipients
