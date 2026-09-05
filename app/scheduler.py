"""In-process weekly report timer.

Replaces the external cron. Reads the schedule from app_settings, fires the weekly report at
the configured day and time, and records the week it sent in DATA_DIR/scheduler_state.json so
a restart or a missed tick never sends the same week twice. It runs inside the single web
worker: run exactly one worker, or two timers will compete.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import app_settings, storage
from .config import settings as env
from .reporting import run_report, week_period

log = logging.getLogger("trackwork.scheduler")
JOB_ID = "weekly-report"

_scheduler: Optional[BackgroundScheduler] = None
_run_lock = threading.Lock()


def _state() -> dict:
    return storage.load_json(env.scheduler_state_file, {}) or {}


def _save_state(**fields) -> None:
    current = _state()
    current.update(fields)
    storage.save_json(env.scheduler_state_file, current)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run_weekly(force: bool = False) -> dict:
    """The job body: send the report for the most recently completed week, once. Idempotent
    per week through the state marker unless `force` (the admin "run now" action)."""
    with _run_lock:
        target = week_period().start.isoformat()
        state = _state()
        if not force and state.get("last_sent_week") == target:
            log.info("weekly report for the week of %s already sent; skipping", target)
            return {"ran": False, "reason": "already sent this week", "week": target}
        try:
            result = run_report(email=True)
        except Exception as e:      # a mail or render failure is recorded, never crashes the app
            log.exception("weekly report failed")
            _save_state(last_run=_now(), last_error=str(e), last_week=target)
            return {"ran": False, "reason": str(e), "week": target}
        if result.generated:
            _save_state(last_run=_now(), last_error=None, last_week=target,
                        last_sent_week=target, last_recipients=result.emailed_to)
            log.info("weekly report sent to %s", ", ".join(result.emailed_to))
            return {"ran": True, "week": target, "recipients": result.emailed_to}
        _save_state(last_run=_now(), last_error=None, last_week=target, last_reason=result.reason)
        log.info("weekly report not generated: %s", result.reason)
        return {"ran": False, "reason": result.reason, "week": target}


def _trigger(sched) -> CronTrigger:
    return CronTrigger(day_of_week=sched.day_of_week, hour=sched.hour, minute=sched.minute,
                       timezone=sched.timezone)


def start() -> None:
    """Start the timer (called from the app lifespan). No-op when SCHEDULER_ENABLED is false."""
    global _scheduler
    if not env.scheduler_enabled:
        log.info("scheduler disabled by SCHEDULER_ENABLED")
        return
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(
        job_defaults={"coalesce": True, "misfire_grace_time": 3600, "max_instances": 1})
    _scheduler.start()
    reschedule()


def reschedule() -> None:
    """Re-read the schedule from settings and (re)install the single job. Call after the
    admin saves a new day or time."""
    if _scheduler is None:
        return
    sched = app_settings.get_settings().schedule
    if _scheduler.get_job(JOB_ID):
        _scheduler.remove_job(JOB_ID)
    if not sched.enabled:
        log.info("weekly report schedule is turned off in Settings")
        return
    _scheduler.add_job(run_weekly, _trigger(sched), id=JOB_ID, replace_existing=True)
    log.info("weekly report scheduled for %s %02d:%02d %s",
             sched.day_of_week, sched.hour, sched.minute, sched.timezone)


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def run_now() -> dict:
    """Admin action: send the current week's report immediately, even if already sent."""
    return run_weekly(force=True)


def status() -> dict:
    """What the admin screen shows: the schedule, whether the timer is live, the next run,
    and what happened last time."""
    sched = app_settings.get_settings().schedule
    job = _scheduler.get_job(JOB_ID) if _scheduler is not None else None
    next_run = (job.next_run_time.isoformat(timespec="minutes")
                if job is not None and job.next_run_time else None)
    return {
        "enabled": bool(env.scheduler_enabled and sched.enabled),
        "running": _scheduler is not None,
        "schedule": sched.model_dump(),
        "next_run": next_run,
        **_state(),
    }
