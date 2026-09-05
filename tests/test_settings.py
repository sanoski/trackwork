import pytest

from app import app_settings, mailer
from app.models import SmtpSettings


def test_defaults_from_env(monkeypatch):
    monkeypatch.setattr(app_settings.env, "report_email_recipient", "a@x.com, b@x.com,")
    monkeypatch.setattr(app_settings.env, "smtp_host", "mail.example.com")
    s = app_settings.get_settings()
    assert s.report_recipients == ["a@x.com", "b@x.com"]
    assert s.smtp.host == "mail.example.com"
    assert s.schedule.day_of_week == "sun" and s.schedule.hour == 8


def test_update_merges_and_keeps_password():
    app_settings.update_settings({"report_recipients": ["rt@example.com"],
                                  "smtp": {"host": "smtp.example.com", "user": "u", "password": "secret"}})
    s = app_settings.get_settings()
    assert s.smtp.password == "secret" and s.report_recipients == ["rt@example.com"]
    app_settings.update_settings({"smtp": {"host": "smtp2.example.com", "password": ""}})
    s = app_settings.get_settings()
    assert s.smtp.host == "smtp2.example.com" and s.smtp.password == "secret"
    app_settings.update_settings({"schedule": {"day_of_week": "mon", "hour": 6}})
    s = app_settings.get_settings()
    assert (s.schedule.day_of_week, s.schedule.hour, s.schedule.minute) == ("mon", 6, 0)


def test_update_validates():
    with pytest.raises(ValueError):
        app_settings.update_settings({"schedule": {"hour": 99}})
    with pytest.raises(ValueError):
        app_settings.update_settings({"schedule": {"day_of_week": "someday"}})


def test_public_view_masks_password():
    app_settings.update_settings({"smtp": {"password": "secret"}})
    view = app_settings.public_view()
    assert view["smtp"]["password"] == "" and view["smtp"]["password_set"] is True


def test_mailer_requires_settings():
    with pytest.raises(RuntimeError):
        mailer.send_message(SmtpSettings(), "", ["a@b.c"], "s", "b")
    with pytest.raises(RuntimeError):
        mailer.send_message(SmtpSettings(host="h", user="u", password="p"), "", [" "], "s", "b")
    with pytest.raises(RuntimeError):
        app_settings.test_email("a@b.c")     # incomplete settings, never reaches the network
