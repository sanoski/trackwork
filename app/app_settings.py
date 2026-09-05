"""Runtime organisation settings.

Who receives the weekly report, how mail is sent, when the report runs, and the names shown
in the app. Stored in DATA_DIR/settings.json and edited from the admin screen or the CLI.
Environment variables supply the first-run defaults; once a settings file has been saved it
takes precedence, so changing a recipient never means editing .env or a crontab.
"""
from __future__ import annotations

from typing import Any, Optional

from . import mailer, storage
from .config import settings as env
from .models import AppSettings, SmtpSettings, WeeklySchedule


def _defaults() -> AppSettings:
    recipients = [r.strip() for r in env.report_email_recipient.split(",") if r.strip()]
    return AppSettings(
        report_recipients=recipients,
        report_sender=env.report_email_sender,
        smtp=SmtpSettings(host=env.smtp_host, port=env.smtp_port,
                          user=env.smtp_user, password=env.smtp_password),
        schedule=WeeklySchedule(),
    )


def _merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def get_settings() -> AppSettings:
    """Effective settings: env defaults overlaid with whatever settings.json holds."""
    stored = storage.load_json(env.settings_file, None)
    if not stored:
        return _defaults()
    return AppSettings.model_validate(_merge(_defaults().model_dump(), stored))


def save_settings(new: AppSettings) -> AppSettings:
    storage.save_json(env.settings_file, new.model_dump())
    return new


def update_settings(patch: dict[str, Any]) -> AppSettings:
    """Apply a partial update (nested sections merge). A blank smtp.password keeps the stored
    password, so the admin screen never has to send it back."""
    current = get_settings()
    patch = {k: v for k, v in patch.items() if v is not None}
    smtp = patch.get("smtp")
    if isinstance(smtp, dict) and not smtp.get("password"):
        smtp = dict(smtp)
        smtp.pop("password", None)
        patch["smtp"] = smtp
    merged = _merge(current.model_dump(), patch)
    return save_settings(AppSettings.model_validate(merged))


def effective_smtp() -> SmtpSettings:
    return get_settings().smtp


def public_view(current: Optional[AppSettings] = None) -> dict:
    """Settings as shown to an admin: the SMTP password is never echoed, only whether it is set."""
    current = current or get_settings()
    view = current.model_dump()
    view["smtp"]["password"] = ""
    view["smtp"]["password_set"] = bool(current.smtp.password)
    return view


def test_email(to: str) -> list[str]:
    """Send a short plain-text message to prove the mail settings work. Raises RuntimeError
    when settings are incomplete; SMTP errors propagate to the caller."""
    current = get_settings()
    return mailer.send_message(
        current.smtp, current.report_sender, [to],
        f"{current.app_name} test email",
        f"This is a test message from {current.org_name} {current.app_name}. "
        "If you are reading it, outbound email is configured correctly.",
    )
