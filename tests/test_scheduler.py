from app import app_settings, scheduler
from app.reporting import RunResult


def test_run_weekly_is_idempotent_per_week(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduler, "run_report",
                        lambda **kw: (calls.append(kw), RunResult(True, "", emailed_to=["rt@example.com"]))[1])
    r1 = scheduler.run_weekly()
    assert r1["ran"] is True and r1["recipients"] == ["rt@example.com"]
    r2 = scheduler.run_weekly()
    assert r2["ran"] is False and "already" in r2["reason"]
    r3 = scheduler.run_weekly(force=True)
    assert r3["ran"] is True and len(calls) == 2
    st = scheduler.status()
    assert st["last_sent_week"] == r1["week"] and st["last_recipients"] == ["rt@example.com"]


def test_no_work_is_not_marked_sent(monkeypatch):
    monkeypatch.setattr(scheduler, "run_report", lambda **kw: RunResult(False, "no work logged"))
    r = scheduler.run_weekly()
    assert r["ran"] is False and r["reason"] == "no work logged"
    st = scheduler._state()
    assert "last_sent_week" not in st and st["last_reason"] == "no work logged"


def test_failure_is_recorded_not_raised(monkeypatch):
    def boom(**kw):
        raise RuntimeError("smtp down")
    monkeypatch.setattr(scheduler, "run_report", boom)
    r = scheduler.run_weekly()
    assert r["ran"] is False and "smtp down" in r["reason"]
    assert scheduler._state()["last_error"] == "smtp down"


def test_start_reschedule_stop():
    scheduler.stop()
    scheduler.start()
    try:
        st = scheduler.status()
        assert st["running"] and st["enabled"] and st["next_run"]
        app_settings.update_settings({"schedule": {"enabled": False}})
        scheduler.reschedule()
        st = scheduler.status()
        assert st["enabled"] is False and st["next_run"] is None
        app_settings.update_settings({"schedule": {"enabled": True, "day_of_week": "mon", "hour": 6, "minute": 30}})
        scheduler.reschedule()
        st = scheduler.status()
        assert st["schedule"]["day_of_week"] == "mon" and st["next_run"]
    finally:
        scheduler.stop()
    assert scheduler.status()["running"] is False
