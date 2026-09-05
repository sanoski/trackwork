#!/usr/bin/env python3
"""Regenerate demo/data through the real service layer, so the sample files are always valid.

    python demo/make_demo.py            # writes demo/data (projects/, settings.json, config.json)

Everything here is fictional: the railroad, the towns, the numbers. No user accounts are
included on purpose; deploy/setup.sh always asks you to create the real first admin.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "data"

work = Path(tempfile.mkdtemp(prefix="trackwork-demo-"))
os.environ["DATA_DIR"] = str(work)
os.environ["SECRET_KEY"] = "demo"
sys.path.insert(0, str(ROOT))

from app import app_settings, downtime, storage, structures  # noqa: E402
from app.models import Timber  # noqa: E402
from app.reporting import get_report_week  # noqa: E402

storage.settings.projects_dir.mkdir(parents=True, exist_ok=True)
storage.settings.archived_dir.mkdir(parents=True, exist_ok=True)

# Anchor the data to the week the app treats as "the most recently completed week" so a fresh
# install has something in last week and the default report is not empty.
last_saturday = get_report_week()[1]


def weekdays_back(end: date, n: int) -> list[date]:
    days, d = [], end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


# 1. A finished sponsored job (created first so the company line demotes it to complete).
job_days = weekdays_back(last_saturday - timedelta(days=28), 14)
job, _ = storage.create_project(
    "1187", "Project 1187", kind="sponsored", job="Tie replacement, MP 12 to MP 31",
    base="Millbrook", deadline=last_saturday - timedelta(days=21), goal_ties=4000, daily_target=300)
job_counts = [310, 295, 340, 0, 325, 360, 330, 290, 380, 345, 300, 335, 310, 240]
for d, n in zip(job_days, job_counts):
    if n:
        storage.record_daily_count(job, d, n)
downtime.add_downtime(job, job_days[3], "Tie Inserter", "07:30", "15:30", "Hydraulic pump failed; parts overnight")
downtime.add_downtime(job, job_days[8], "Tamper", "13:10", "14:25", "Clogged fuel filter")
storage.save_project(job)

# 2. The active company line with two worksites.
line, _ = storage.create_project(
    "NVR_ND", "Northern Valley Railroad, North Division", kind="company", line="NVR_ND",
    base="Millbrook", daily_target=300)
structures.add_location(line, "Millbrook Yard")
structures.add_location(line, "Cedar Falls")
line_days = weekdays_back(last_saturday, 15)
# (ties, relay, track, location)
plan = [
    (280, 0, None, "millbrook-yard"), (305, 0, None, "millbrook-yard"), (260, 60, None, "millbrook-yard"),
    (0, 0, None, None), (240, 240, None, "millbrook-yard"),
    (150, 150, "Track 2", "cedar-falls"), (140, 140, "Track 3", "cedar-falls"),
    (220, 220, None, "cedar-falls"), (0, 0, None, None), (190, 190, None, "cedar-falls"),
    (310, 0, None, "millbrook-yard"), (295, 45, None, "millbrook-yard"), (0, 0, None, None),
    (270, 270, None, "cedar-falls"), (255, 255, "Track 1", "cedar-falls"),
]
for d, (ties, relay, track, loc) in zip(line_days, plan):
    if ties:
        storage.record_daily_count(line, d, ties, relay_ties=relay, track=track, location=loc)
# a split day: second track on the same date as the first Cedar Falls entry
storage.record_daily_count(line, line_days[5], 95, relay_ties=95, track="Track 3", location="cedar-falls")
downtime.add_downtime(line, line_days[3], "Spiker/Gauger", "08:00", "11:45", "Broken spike feeder")
downtime.add_downtime(line, line_days[8], "Broom", "09:20", "10:05", "Belt replaced")
downtime.add_downtime(line, line_days[12], "Tamper", "07:00", None, "Down for the day; electrical")

T = lambda length, planned, actual, hb=False: Timber(length=length, planned=planned, actual=actual, head_block=hb)  # noqa: E731
structures.add_switch(line, "Millbrook North Switch", line_days[3], [T(9, 6, 8), T(10, 4, 4), T(12, 4, 3), T(16, 2, 2, True)],
                      notes="No. 10 turnout", location="millbrook-yard")
structures.add_switch(line, "Millbrook Crossover", line_days[8], [T(9, 8, 8), T(11, 4, 4), T(13, 2, 2), T(16, 2, 2, True)],
                      location="millbrook-yard")
structures.add_switch(line, "Cedar Falls Siding Switch", line_days[12], [T(9, 6, 6), T(12, 3, 3), T(14, 2, 0), T(16, 2, 2, True)],
                      notes="14 ft timbers back-ordered", location="cedar-falls")
structures.add_derail(line, "Cedar Falls Derail", line_days[13], [T(12, 2, 2, True)],
                      derail_type="stationary", location="cedar-falls")
storage.save_project(line)

# 3. Organisation settings with nothing real in them.
s = app_settings.get_settings()
s.org_name = "Northern Valley Railroad"
s.app_name = "MOW Tracker"
s.report_recipients = []
s.report_sender = ""
app_settings.save_settings(s)

# 4. Copy out.
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
shutil.copytree(work / "projects", OUT / "projects")
(OUT / "archived").mkdir()
shutil.copy(work / "settings.json", OUT / "settings.json")
(OUT / "config.json").write_text(json.dumps(
    {"equipment": ["Tie Inserter", "Broom", "Plate Setter", "Tamper", "Spiker/Gauger", "Other"]}, indent=2) + "\n")
shutil.rmtree(work)
print(f"wrote {OUT}: {sorted(p.name for p in (OUT / 'projects').iterdir())}, settings.json, config.json")
