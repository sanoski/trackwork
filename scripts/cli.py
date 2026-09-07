#!/usr/bin/env python3
"""
MOW Tracker command-line administration tool.

Mirrors every MCP tool (and every web screen) over the same service layer, and adds the
report runner, user and settings management, the weekly schedule, data import, and export.

Usage:
  python scripts/cli.py list
  python scripts/cli.py summary <id>
  python scripts/cli.py log <id>
  python scripts/cli.py downtime <id>
  python scripts/cli.py add-count <id> <date> <ties> [--relay-ties N] [--track NAME] [--location NAME]
  python scripts/cli.py update-count <id> <date> <new_ties> [--relay-ties N] [--track NAME] [--location NAME]
  python scripts/cli.py add-downtime <id> <date> <machine> [--down-at HH:MM] [--resumed HH:MM] [--notes TEXT]
  python scripts/cli.py switches <id>
  python scripts/cli.py add-switch <id> <name> <date> --timber 9:6/11 --timber 16:2/2:hb [--location NAME]
  python scripts/cli.py derails <id>
  python scripts/cli.py add-derail <id> <name> <date> [--derail-type stationary] --timber 12:2/2:hb [--location NAME]
  python scripts/cli.py locations <id>
  python scripts/cli.py add-location <id> <name> [--note TEXT]
  python scripts/cli.py update-location <id> <location> [--new-name NAME] [--note TEXT]
  python scripts/cli.py delete-location <id> <location>
  python scripts/cli.py create <id> <name> [--kind sponsored|company] [--line TEXT] [--job TEXT] [--base TEXT] [--deadline YYYY-MM-DD] [--goal N] [--daily-target N]
  python scripts/cli.py update <id> [--goal N] [--deadline YYYY-MM-DD] [--daily-target N] [--status active|complete|archived]
  python scripts/cli.py set-status <id> <active|complete|archived>
  python scripts/cli.py archive <id>
  python scripts/cli.py export [--output PATH] [--year YEAR]
  python scripts/cli.py report [--project ID] [--location NAME] [--week D | --full | --from D --to D] [--no-email] [-o PATH]
  python scripts/cli.py user list | add <email> <name> [--role admin|entry|viewer] | update <email> ... | delete <email>
  python scripts/cli.py settings show | set [--recipients a@x,b@y] [--smtp-host ...] [--day sun --hour 8] | test-email <to>
  python scripts/cli.py schedule status | run-now
  python scripts/cli.py import <bundle-dir> [--overwrite]
  python scripts/cli.py token list | create <email> <label> [--days N] | revoke <id>
  python scripts/cli.py verify
"""

import argparse
import getpass
import json
import shutil
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app_settings, downtime, mcp_tokens, reporting, scheduler, storage, structures, users
from app.config import settings as env_settings
from app.models import Project, Timber
from app.reporting import build_summary


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_die(project_id: str) -> Project:
    p = storage.load_project(project_id)
    if not p:
        print(f"Error: '{project_id}' not found.", file=sys.stderr)
        sys.exit(1)
    return p


def _die(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def _parse_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        _die(f"{label} must be YYYY-MM-DD")


def _print_json(data) -> None:
    print(json.dumps(data, indent=2, default=str))


def _filter_log(entries, args):
    if getattr(args, "date", None):
        try:
            d = date.fromisoformat(args.date)
        except ValueError:
            print("Error: --date must be YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)
        return [e for e in entries if e.date == d]

    if getattr(args, "week", None):
        try:
            d = date.fromisoformat(args.week)
        except ValueError:
            print("Error: --week must be YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)
        week_start = d - timedelta(days=(d.weekday() + 1) % 7)
        week_end = week_start + timedelta(days=6)
        return [e for e in entries if week_start <= e.date <= week_end]

    if getattr(args, "month", None):
        try:
            parts = args.month.split("-")
            if len(parts) != 2:
                raise ValueError()
            yr, mo = int(parts[0]), int(parts[1])
        except ValueError:
            print("Error: --month must be YYYY-MM", file=sys.stderr)
            sys.exit(1)
        return [e for e in entries if e.date.year == yr and e.date.month == mo]

    if getattr(args, "year", None):
        return [e for e in entries if e.date.year == args.year]

    from_date = getattr(args, "from_date", None)
    to_date = getattr(args, "to_date", None)
    if from_date or to_date:
        result = list(entries)
        if from_date:
            try:
                from_d = date.fromisoformat(from_date)
            except ValueError:
                print("Error: --from must be YYYY-MM-DD", file=sys.stderr)
                sys.exit(1)
            result = [e for e in result if e.date >= from_d]
        if to_date:
            try:
                to_d = date.fromisoformat(to_date)
            except ValueError:
                print("Error: --to must be YYYY-MM-DD", file=sys.stderr)
                sys.exit(1)
            result = [e for e in result if e.date <= to_d]
        return result

    return entries


def _parse_timber(spec: str) -> Timber:
    """Parse a CLI timber spec 'LEN:PLANNED/ACTUAL[:hb]' - e.g. '9:6/11', '16:2/2:hb',
    '12:-/2' (a dash or blank means 0)."""
    parts = spec.split(":")
    if len(parts) < 2:
        print(f"Error: bad --timber '{spec}' (expected LEN:PLANNED/ACTUAL[:hb])", file=sys.stderr)
        sys.exit(1)
    try:
        length = int(parts[0])
    except ValueError:
        print(f"Error: bad timber length in '{spec}'", file=sys.stderr)
        sys.exit(1)
    pa = parts[1].split("/")
    if len(pa) != 2:
        print(f"Error: bad planned/actual in '{spec}' (expected PLANNED/ACTUAL)", file=sys.stderr)
        sys.exit(1)

    def _num(x: str) -> int:
        x = x.strip()
        return 0 if x in ("", "-") else int(x)

    try:
        planned, actual = _num(pa[0]), _num(pa[1])
    except ValueError:
        print(f"Error: bad planned/actual numbers in '{spec}'", file=sys.stderr)
        sys.exit(1)
    head_block = len(parts) > 2 and parts[2].strip().lower() in ("hb", "headblock", "head-block", "yes")
    return Timber(length=length, planned=planned, actual=actual, head_block=head_block)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(args) -> None:
    projects = storage.list_projects()
    if not projects:
        print("No projects found.")
        return
    active   = [p for p in projects if p.project.status == "active"]
    complete = [p for p in projects if p.project.status == "complete"]
    archived = [p for p in projects if p.project.status == "archived"]
    other    = [p for p in projects if p.project.status not in ("active", "complete", "archived")]
    for section, items in [("ACTIVE", active), ("COMPLETE", complete), ("ARCHIVED", archived), ("OTHER", other)]:
        if not items:
            continue
        print(f"\n{section}")
        print("-" * 40)
        for p in items:
            meta = p.project
            total = sum(e.ties for e in p.daily_log)
            goal_str = f"{meta.goal_ties:,}" if meta.goal_ties else "no goal"
            pct_str  = f"({round(total / meta.goal_ties * 100, 1)}%)" if meta.goal_ties else ""
            print(f"  [{meta.kind}] {meta.id:12s}  {meta.name}")
            print(f"               {total:,} ties installed / {goal_str} {pct_str}")
    print()


def cmd_summary(args) -> None:
    project = _get_or_die(args.id)
    summary = build_summary(project)
    _print_json({k: v.isoformat() if hasattr(v, "isoformat") else v for k, v in summary.items()})


def cmd_log(args) -> None:
    project = _get_or_die(args.id)
    entries = _filter_log(project.daily_log, args)
    if not entries:
        print("No log entries.")
        return
    print(f"{'Date':<12} {'Day':<10} {'Ties':>6} {'Relay':>6} {'VS Tgt':>8} {'Running':>10} {'Remaining':>10} {'Loc':<16}")
    print("-" * 86)
    for e in entries:
        vs_str = f"+{e.vs_target}" if e.vs_target >= 0 else str(e.vs_target)
        rem_str = str(e.remaining) if e.remaining is not None else "-"
        relay_str = str(e.relay_ties) if e.relay_ties else "-"
        loc_str = e.location or "-"
        print(f"{str(e.date):<12} {e.day:<10} {e.ties:>6,} {relay_str:>6} {vs_str:>8} {e.running_total:>10,} {rem_str:>10} {loc_str:<16}")


def cmd_downtime(args) -> None:
    project = _get_or_die(args.id)
    if not project.equipment_downtime:
        print("No downtime entries.")
        return
    print(f"{'Date':<12} {'Machine':<20} {'Down At':<9} {'Resumed':<9} {'Duration':<10} Notes")
    print("-" * 80)
    for e in project.equipment_downtime:
        dur = f"{e.duration_minutes}m" if e.duration_minutes else "-"
        print(f"{str(e.date):<12} {e.machine:<20} {e.down_at or '-':<9} {e.resumed or '-':<9} {dur:<10} {e.notes or ''}")


def cmd_add_count(args) -> None:
    project = _get_or_die(args.id)
    try:
        entry_date = date.fromisoformat(args.date)
    except ValueError:
        print("Error: date must be YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)
    try:
        entry = storage.record_daily_count(
            project, entry_date, args.ties, args.relay_ties or 0, args.track, args.location)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    storage.save_project(project)
    rem_str = f"{entry.remaining:,}" if entry.remaining is not None else "-"
    relay_note = f"  |  relay: {args.relay_ties:,}" if args.relay_ties else ""
    track_note = f"  |  {args.track}" if args.track else ""
    loc_note = f"  |  @ {entry.location}" if entry.location else ""
    day_note = f"  |  day total: {entry.ties:,}" if entry.ties != args.ties else ""
    print(f"Saved - {args.ties:,} ties on {entry.day} {entry_date}{track_note}{loc_note}{relay_note}{day_note}"
          f"  |  running total: {entry.running_total:,}  |  remaining: {rem_str}")


def cmd_update_count(args) -> None:
    project = _get_or_die(args.id)
    try:
        entry_date = date.fromisoformat(args.date)
    except ValueError:
        print("Error: date must be YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)
    try:
        updated, old_ties = storage.update_daily_count(
            project, entry_date, args.new_ties, args.relay_ties, args.track, args.location)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    storage.save_project(project)
    rem_str = f"{updated.remaining:,}" if updated.remaining is not None else "-"
    relay_note = f"  |  relay: {updated.relay_ties:,}" if updated.relay_ties else ""
    track_note = f"  |  {args.track}" if args.track else ""
    loc_note = f"  |  @ {updated.location}" if updated.location else ""
    print(f"Updated - {args.date}{track_note}: day {old_ties:,} to {updated.ties:,}{relay_note}{loc_note}"
          f"  |  running total: {updated.running_total:,}  |  remaining: {rem_str}")


def cmd_add_downtime(args) -> None:
    project = _get_or_die(args.id)
    entry_date = _parse_date(args.date, "date")
    try:
        entry = downtime.add_downtime(project, entry_date, args.machine,
                                      args.down_at, args.resumed, args.notes)
    except ValueError as e:
        _die(str(e))
    storage.save_project(project)
    dur = f"{entry.duration_minutes}m" if entry.duration_minutes else "-"
    print(f"Saved downtime: {entry_date} {args.machine}  |  duration: {dur}")


def cmd_update_downtime(args) -> None:
    project = _get_or_die(args.id)
    entry_date = _parse_date(args.date, "date")
    try:
        target = downtime.update_downtime(project, entry_date, args.machine,
                                          down_at=args.down_at, resumed=args.resumed,
                                          notes=args.notes, match_down_at=args.match_down_at)
    except (ValueError, LookupError) as e:
        _die(str(e))
    storage.save_project(project)
    dur = f"{target.duration_minutes}m" if target.duration_minutes else "-"
    print(f"Updated: {entry_date} {args.machine}  |  {target.down_at or '?'} to {target.resumed or '?'}"
          f"  |  {dur}  |  {target.notes or ''}")


def cmd_delete_downtime(args) -> None:
    project = _get_or_die(args.id)
    entry_date = _parse_date(args.date, "date")
    try:
        target = downtime.delete_downtime(project, entry_date, args.machine, args.down_at)
    except (ValueError, LookupError) as e:
        _die(str(e))
    storage.save_project(project)
    dur = f"{target.duration_minutes}m" if target.duration_minutes else "-"
    print(f"Deleted: {entry_date} {args.machine}  |  {target.down_at or '?'} to {target.resumed or '?'}"
          f"  |  {dur}  |  {target.notes or ''}")


def cmd_switches(args) -> None:
    project = _get_or_die(args.id)
    if not project.switches:
        print("No switches.")
        return
    print(f"{'Date':<12} {'ID':<22} {'Name':<28} {'Loc':<14} {'Plan':>5} {'Act':>5} {'Lens':>5}")
    print("-" * 96)
    for s in project.switches:
        p, a = structures.entity_totals(s)
        print(f"{str(s.date):<12} {s.id:<22} {s.name:<28} {(s.location or '-'):<14} {p:>5} {a:>5} {len(s.timbers):>5}")


def cmd_add_switch(args) -> None:
    project = _get_or_die(args.id)
    try:
        d = date.fromisoformat(args.date)
    except ValueError:
        print("Error: date must be YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)
    if not args.timber:
        print("Error: at least one --timber is required (LEN:PLANNED/ACTUAL[:hb])", file=sys.stderr)
        sys.exit(1)
    timbers = [_parse_timber(t) for t in args.timber]
    try:
        sw = structures.add_switch(project, args.name, d, timbers, notes=args.note, location=args.location)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    storage.save_project(project)
    p, a = structures.entity_totals(sw)
    loc_note = f"  |  @ {sw.location}" if sw.location else ""
    print(f"Added switch '{sw.name}' ({sw.id}) on {sw.date}{loc_note}  |  planned {p} / actual {a}  |  {len(timbers)} lengths")


def cmd_update_switch(args) -> None:
    project = _get_or_die(args.id)
    on_date = _parse_date(args.date, "--date") if args.date else None
    timbers = [_parse_timber(t) for t in args.timber] if args.timber else None
    try:
        sw = structures.update_switch(project, args.name, on_date, new_name=args.new_name,
                                      timbers=timbers, notes=args.note, location=args.location)
    except (ValueError, LookupError) as e:
        _die(str(e))
    storage.save_project(project)
    p, a = structures.entity_totals(sw)
    print(f"Updated switch '{sw.name}' ({sw.id})  |  planned {p} / actual {a}")


def cmd_delete_switch(args) -> None:
    project = _get_or_die(args.id)
    on_date = _parse_date(args.date, "--date") if args.date else None
    try:
        sw = structures.delete_switch(project, args.name, on_date)
    except LookupError as e:
        _die(str(e))
    storage.save_project(project)
    print(f"Deleted switch '{sw.name}' ({sw.id}) on {sw.date}")


def cmd_derails(args) -> None:
    project = _get_or_die(args.id)
    if not project.derails:
        print("No derails.")
        return
    print(f"{'Date':<12} {'ID':<22} {'Name':<24} {'Type':<11} {'Loc':<14} {'Plan':>5} {'Act':>5}")
    print("-" * 98)
    for dr in project.derails:
        p, a = structures.entity_totals(dr)
        print(f"{str(dr.date):<12} {dr.id:<22} {dr.name:<24} {(dr.derail_type or '-'):<11} {(dr.location or '-'):<14} {p:>5} {a:>5}")


def cmd_add_derail(args) -> None:
    project = _get_or_die(args.id)
    try:
        d = date.fromisoformat(args.date)
    except ValueError:
        print("Error: date must be YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)
    timbers = [_parse_timber(t) for t in (args.timber or [])]
    try:
        dr = structures.add_derail(project, args.name, d, timbers,
                                   derail_type=args.derail_type, notes=args.note, location=args.location)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    storage.save_project(project)
    p, a = structures.entity_totals(dr)
    loc_note = f"  |  @ {dr.location}" if dr.location else ""
    print(f"Added derail '{dr.name}' ({dr.id}) on {dr.date}{loc_note}  |  planned {p} / actual {a}  |  {len(timbers)} lengths")


def cmd_update_derail(args) -> None:
    project = _get_or_die(args.id)
    on_date = _parse_date(args.date, "--date") if args.date else None
    timbers = [_parse_timber(t) for t in args.timber] if args.timber else None
    try:
        dr = structures.update_derail(project, args.name, on_date, new_name=args.new_name,
                                      derail_type=args.derail_type, timbers=timbers,
                                      notes=args.note, location=args.location)
    except (ValueError, LookupError) as e:
        _die(str(e))
    storage.save_project(project)
    p, a = structures.entity_totals(dr)
    print(f"Updated derail '{dr.name}' ({dr.id})  |  planned {p} / actual {a}")


def cmd_delete_derail(args) -> None:
    project = _get_or_die(args.id)
    on_date = _parse_date(args.date, "--date") if args.date else None
    try:
        dr = structures.delete_derail(project, args.name, on_date)
    except LookupError as e:
        _die(str(e))
    storage.save_project(project)
    print(f"Deleted derail '{dr.name}' ({dr.id}) on {dr.date}")


def cmd_locations(args) -> None:
    project = _get_or_die(args.id)
    if not project.locations:
        print("No locations.")
        return
    print(f"{'ID':<22} {'Name':<28} {'Days':>5} {'Sw':>4} {'Dr':>4}")
    print("-" * 66)
    for loc in project.locations:
        days, sw, dr = structures.location_refs(project, loc.id)
        print(f"{loc.id:<22} {loc.name:<28} {days:>5} {sw:>4} {dr:>4}")


def cmd_add_location(args) -> None:
    project = _get_or_die(args.id)
    try:
        loc = structures.add_location(project, args.name, notes=args.note)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    storage.save_project(project)
    print(f"Added location '{loc.name}' ({loc.id})")


def cmd_update_location(args) -> None:
    project = _get_or_die(args.id)
    if args.new_name is None and args.note is None:
        print("Nothing to update - specify --new-name or --note", file=sys.stderr)
        sys.exit(1)
    try:
        loc = structures.update_location(project, args.location, new_name=args.new_name, notes=args.note)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    storage.save_project(project)
    print(f"Updated location '{loc.name}' ({loc.id})")


def cmd_delete_location(args) -> None:
    project = _get_or_die(args.id)
    try:
        loc = structures.delete_location(project, args.location)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    storage.save_project(project)
    print(f"Deleted location '{loc.name}' ({loc.id})")


def cmd_create(args) -> None:
    deadline = _parse_date(args.deadline, "deadline") if args.deadline else None
    try:
        project, demoted = storage.create_project(
            args.id, args.name, kind=args.kind, line=args.line, job=args.job or "",
            base=args.base or "", deadline=deadline, goal_ties=args.goal,
            daily_target=args.daily_target)
    except ValueError as e:
        _die(str(e))
    goal_str = f"{args.goal:,}" if args.goal else "none"
    msg = (f"Created {args.kind} '{project.project.id}': {args.name}  |  goal: {goal_str}"
           f"  |  daily target: {args.daily_target:,}")
    if demoted:
        msg += f"  |  demoted to complete: {', '.join(demoted)}"
    print(msg)


def cmd_update(args) -> None:
    project = _get_or_die(args.id)
    deadline = _parse_date(args.deadline, "deadline") if args.deadline else None
    fields = {"goal_ties": args.goal, "deadline": deadline, "daily_target": args.daily_target,
              "line": args.line, "status": args.status}
    try:
        demoted = storage.update_project_meta(project, **fields)
    except ValueError as e:
        _die(str(e))
    storage.save_project(project)
    changed = [f"{k}={v}" for k, v in fields.items() if v is not None]
    msg = f"Updated '{args.id}': {', '.join(changed)}"
    if demoted:
        msg += f"  |  demoted to complete: {', '.join(demoted)}"
    print(msg)


def cmd_set_status(args) -> None:
    project = _get_or_die(args.id)
    try:
        demoted = storage.set_status(project, args.status)
    except ValueError as e:
        _die(str(e))
    storage.save_project(project)
    msg = f"'{args.id}' set to {args.status}."
    if demoted:
        msg += f" Demoted to complete: {', '.join(demoted)}."
    print(msg)


def cmd_archive(args) -> None:
    project = _get_or_die(args.id)
    storage.set_status(project, "archived")
    storage.save_project(project)
    print(f"'{args.id}' archived.")


def cmd_export(args) -> None:
    output = Path(args.output) if args.output else Path(f"season_{args.year or date.today().year}.db")
    projects = storage.list_projects()
    if args.year:
        year = args.year
    else:
        year = None

    con = sqlite3.connect(output)
    cur = con.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT,
            kind TEXT,
            line TEXT,
            job TEXT,
            base TEXT,
            deadline TEXT,
            goal_ties INTEGER,
            daily_target INTEGER,
            status TEXT,
            created TEXT
        );
        CREATE TABLE IF NOT EXISTS locations (
            project_id TEXT,
            id TEXT,
            name TEXT,
            notes TEXT,
            PRIMARY KEY (project_id, id)
        );
        CREATE TABLE IF NOT EXISTS daily_log (
            project_id TEXT,
            date TEXT,
            day TEXT,
            ties INTEGER,
            relay_ties INTEGER,
            vs_target INTEGER,
            running_total INTEGER,
            remaining INTEGER,
            location TEXT,
            PRIMARY KEY (project_id, date)
        );
        CREATE TABLE IF NOT EXISTS equipment_downtime (
            project_id TEXT,
            date TEXT,
            machine TEXT,
            down_at TEXT,
            resumed TEXT,
            duration_minutes INTEGER,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS switches (
            project_id TEXT,
            id TEXT,
            name TEXT,
            date TEXT,
            location TEXT,
            notes TEXT,
            PRIMARY KEY (project_id, id)
        );
        CREATE TABLE IF NOT EXISTS derails (
            project_id TEXT,
            id TEXT,
            name TEXT,
            date TEXT,
            derail_type TEXT,
            location TEXT,
            notes TEXT,
            PRIMARY KEY (project_id, id)
        );
        CREATE TABLE IF NOT EXISTS timbers (
            project_id TEXT,
            entity_kind TEXT,
            entity_id TEXT,
            length INTEGER,
            planned INTEGER,
            actual INTEGER,
            head_block INTEGER,
            PRIMARY KEY (project_id, entity_kind, entity_id, length)
        );
    """)

    exported = 0
    for p in projects:
        meta = p.project
        log_entries = p.daily_log
        downtime_entries = p.equipment_downtime
        switch_entries = p.switches
        derail_entries = p.derails

        if year:
            log_entries = [e for e in log_entries if e.date.year == year]
            downtime_entries = [e for e in downtime_entries if e.date.year == year]
            switch_entries = [s for s in switch_entries if s.date.year == year]
            derail_entries = [d for d in derail_entries if d.date.year == year]
            if not log_entries and not downtime_entries and not switch_entries and not derail_entries:
                continue

        cur.execute("""
            INSERT OR REPLACE INTO projects VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (meta.id, meta.name, meta.kind, meta.line, meta.job, meta.base,
              str(meta.deadline) if meta.deadline else None, meta.goal_ties,
              meta.daily_target, meta.status, str(meta.created)))

        for loc in p.locations:
            cur.execute("INSERT OR REPLACE INTO locations VALUES (?,?,?,?)",
                        (meta.id, loc.id, loc.name, loc.notes))

        for e in log_entries:
            cur.execute("""
                INSERT OR REPLACE INTO daily_log VALUES (?,?,?,?,?,?,?,?,?)
            """, (meta.id, str(e.date), e.day, e.ties, e.relay_ties,
                  e.vs_target, e.running_total, e.remaining, e.location))

        for e in downtime_entries:
            cur.execute("""
                INSERT OR IGNORE INTO equipment_downtime VALUES (?,?,?,?,?,?,?)
            """, (meta.id, str(e.date), e.machine, e.down_at, e.resumed,
                  e.duration_minutes, e.notes))

        for s in switch_entries:
            cur.execute("INSERT OR REPLACE INTO switches VALUES (?,?,?,?,?,?)",
                        (meta.id, s.id, s.name, str(s.date), s.location, s.notes))
            for t in s.timbers:
                cur.execute("INSERT OR REPLACE INTO timbers VALUES (?,?,?,?,?,?,?)",
                            (meta.id, "switch", s.id, t.length, t.planned, t.actual, int(t.head_block)))

        for dr in derail_entries:
            cur.execute("INSERT OR REPLACE INTO derails VALUES (?,?,?,?,?,?,?)",
                        (meta.id, dr.id, dr.name, str(dr.date), dr.derail_type, dr.location, dr.notes))
            for t in dr.timbers:
                cur.execute("INSERT OR REPLACE INTO timbers VALUES (?,?,?,?,?,?,?)",
                            (meta.id, "derail", dr.id, t.length, t.planned, t.actual, int(t.head_block)))

        exported += 1

    con.commit()
    con.close()
    print(f"Exported {exported} project(s) to {output}")


def cmd_report(args) -> None:
    """Build (and by default email) a report. The weekly timer runs this same path."""
    week = _parse_date(args.week, "--week") if args.week else None
    start = _parse_date(args.from_date, "--from") if args.from_date else None
    end = _parse_date(args.to_date, "--to") if args.to_date else None
    try:
        r = reporting.run_report(
            args.project, args.location, week=week, full=args.full, start=start, end=end,
            ties=args.ties, detail=args.detail, switches=not args.no_switches,
            derails=not args.no_derails, downtime=not args.no_downtime,
            charts=not args.no_charts, email=not args.no_email, output=args.output,
            recipients=[r.strip() for r in args.recipients.split(",") if r.strip()] if args.recipients else None)
    except RuntimeError as e:
        _die(str(e))
    if not r.generated:
        print(f"No report generated: {r.reason}.")
        return
    print(f"Report generated for {r.period_label} ({len(r.pdf):,} bytes)")
    if r.saved_to:
        print(f"Saved to {r.saved_to}")
    if r.emailed_to:
        print(f"Emailed to {', '.join(r.emailed_to)}")


def _prompt_password(label: str = "Password") -> str:
    pw = getpass.getpass(f"{label}: ")
    if pw != getpass.getpass("Confirm: "):
        _die("passwords do not match")
    return pw


def cmd_user(args) -> None:
    try:
        if args.user_cmd == "list":
            found = users.list_users()
            if not found:
                print("No users.")
            for u in found:
                print(f"{u.email:<34} {u.role:<7} {u.name}")
        elif args.user_cmd == "add":
            pw = args.password or _prompt_password()
            u = users.create_user(args.email, args.name, pw, args.role)
            print(f"Added {u.role} '{u.name}' ({u.email})")
        elif args.user_cmd == "update":
            pw = args.password or (_prompt_password("New password") if args.set_password else None)
            u = users.update_user(args.email, name=args.name, role=args.role, password=pw)
            print(f"Updated '{u.email}': role {u.role}, name {u.name}")
        elif args.user_cmd == "delete":
            u = users.delete_user(args.email)
            print(f"Deleted '{u.email}'")
    except (ValueError, LookupError) as e:
        _die(str(e))


def cmd_settings(args) -> None:
    if args.settings_cmd == "show":
        _print_json(app_settings.public_view())
        return
    if args.settings_cmd == "test-email":
        try:
            sent = app_settings.test_email(args.to)
        except RuntimeError as e:
            _die(str(e))
        except Exception as e:
            _die(f"send failed: {e}")
        print(f"Test email sent to {', '.join(sent)}")
        return
    patch = {}
    if args.recipients is not None:
        patch["report_recipients"] = [r.strip() for r in args.recipients.split(",") if r.strip()]
    for key, value in (("report_sender", args.sender), ("org_name", args.org_name),
                       ("app_name", args.app_name)):
        if value is not None:
            patch[key] = value
    smtp = {k: v for k, v in (("host", args.smtp_host), ("port", args.smtp_port),
                              ("user", args.smtp_user), ("password", args.smtp_password))
            if v is not None}
    if smtp:
        patch["smtp"] = smtp
    enabled = True if args.enable else (False if args.disable else None)
    sched = {k: v for k, v in (("enabled", enabled), ("day_of_week", args.day), ("hour", args.hour),
                               ("minute", args.minute), ("timezone", args.timezone))
             if v is not None}
    if sched:
        patch["schedule"] = sched
    if not patch:
        _die("nothing to set; see: settings set --help")
    try:
        app_settings.update_settings(patch)
    except ValueError as e:
        _die(str(e))
    _print_json(app_settings.public_view())


def cmd_schedule(args) -> None:
    if args.schedule_cmd == "status":
        _print_json(scheduler.status())
        return
    result = scheduler.run_now()
    _print_json(result)
    if not result.get("ran"):
        sys.exit(1)


def cmd_import(args) -> None:
    """Copy a data bundle (projects/, archived/, users.json, settings.json, config.json) into
    DATA_DIR. Existing top-level files are kept unless --overwrite is given. --replace first
    removes every project already in DATA_DIR (for example the demo dataset), so the bundle
    is the only data afterwards; accounts are never touched."""
    src = Path(args.bundle)
    if not src.is_dir():
        _die(f"'{src}' is not a directory")
    root = env_settings._data_root()
    copied = []
    if getattr(args, "replace", False):
        removed = 0
        for sub in ("projects", "archived"):
            d = root / sub
            if d.is_dir():
                for f in d.glob("*.json"):
                    f.unlink()
                    removed += 1
        print(f"Removed {removed} existing project file(s) from {root}")
    for sub in ("projects", "archived"):
        d = src / sub
        if d.is_dir():
            (root / sub).mkdir(parents=True, exist_ok=True)
            for f in sorted(d.glob("*.json")):
                shutil.copy2(f, root / sub / f.name)
                copied.append(f"{sub}/{f.name}")
    for name in ("users.json", "settings.json", "config.json"):
        f = src / name
        if f.is_file():
            if (root / name).exists() and not args.overwrite:
                print(f"Skipping {name} (already exists; use --overwrite to replace it)")
                continue
            shutil.copy2(f, root / name)
            copied.append(name)
    print(f"Imported {len(copied)} file(s) into {root}")
    for c in copied:
        print(f"  {c}")


def cmd_verify(args) -> None:
    """Load every project and print counts, so a fresh install can be checked against the source."""
    projects = storage.list_projects()
    if not projects:
        print("No projects found.")
        sys.exit(1)
    print(f"{'ID':<14} {'Status':<9} {'Days':>5} {'Ties':>7} {'Relay':>6} {'Sw':>4} {'Dr':>4} {'Down':>5} {'Locs':>5}")
    print("-" * 70)
    total = 0
    for p in projects:
        ties = sum(e.ties for e in p.daily_log)
        relay = sum(e.relay_ties for e in p.daily_log)
        total += ties
        print(f"{p.project.id:<14} {p.project.status:<9} {len(p.daily_log):>5} {ties:>7,} {relay:>6,} "
              f"{len(p.switches):>4} {len(p.derails):>4} {len(p.equipment_downtime):>5} {len(p.locations):>5}")
    print("-" * 70)
    print(f"{len(projects)} project(s), {total:,} ties, {len(users.list_users())} user(s)")


def cmd_token(args) -> None:
    """Per-user tokens for the MCP (AI assistant) server."""
    try:
        if args.token_cmd == "list":
            recs = mcp_tokens.list_tokens()
            if not recs:
                print("No tokens.")
            for r in recs:
                flag = "revoked" if r["revoked"] else "active"
                print(f"{r['id']:<18} {r['email']:<32} {r['label']:<24} expires {r['expires'][:10]}  {flag}")
        elif args.token_cmd == "create":
            users.find_user(args.email)
            token, rec = mcp_tokens.create_token(args.email, args.label, args.days)
            print(f"Token {rec['id']} for {rec['email']} ({rec['label']}), expires {rec['expires'][:10]}.")
            print("Copy it now; it is not stored and cannot be shown again:")
            print(token)
        elif args.token_cmd == "revoke":
            rec = mcp_tokens.revoke_token(args.id)
            print(f"Revoked token {rec['id']} ({rec['email']}, {rec['label']}).")
    except (ValueError, LookupError, RuntimeError) as e:
        _die(str(e))


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="MOW Tracker CLI")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all projects and lines")

    p_sum = sub.add_parser("summary", help="Show computed summary for a project")
    p_sum.add_argument("id")

    p_log = sub.add_parser("log", help="Show daily log for a project")
    p_log.add_argument("id")
    p_log.add_argument("--date", metavar="YYYY-MM-DD", help="Single day")
    p_log.add_argument("--week", metavar="YYYY-MM-DD", help="Work week (Sun-Sat) containing this date")
    p_log.add_argument("--month", metavar="YYYY-MM", help="Specific month")
    p_log.add_argument("--year", type=int, metavar="YYYY", help="Specific year")
    p_log.add_argument("--from", dest="from_date", metavar="YYYY-MM-DD", help="Range start (inclusive)")
    p_log.add_argument("--to", dest="to_date", metavar="YYYY-MM-DD", help="Range end (inclusive)")

    p_dt = sub.add_parser("downtime", help="Show downtime log for a project")
    p_dt.add_argument("id")

    p_ac = sub.add_parser("add-count", help="Log a day's tie count")
    p_ac.add_argument("id")
    p_ac.add_argument("date", metavar="YYYY-MM-DD")
    p_ac.add_argument("ties", type=int)
    p_ac.add_argument("--relay-ties", type=int, metavar="N",
                      help="How many of those ties were relay (reclaimed) ties (subset of ties)")
    p_ac.add_argument("--track", metavar="NAME",
                      help="Tag these ties to a track (e.g. 'Track 2'). Repeat the command with the "
                           "same date and a different track to record a day split across tracks.")
    p_ac.add_argument("--location", metavar="NAME",
                      help="Worksite on a company line (id or name, e.g. 'St. Johnsbury'). Must already "
                           "exist - create it first with add-location. Omit for main-line work.")

    p_uc = sub.add_parser("update-count", help="Correct an existing tie count")
    p_uc.add_argument("id")
    p_uc.add_argument("date", metavar="YYYY-MM-DD")
    p_uc.add_argument("new_ties", type=int)
    p_uc.add_argument("--relay-ties", type=int, metavar="N",
                      help="Correct how many of those ties were relay (reclaimed) ties (subset of new_ties)")
    p_uc.add_argument("--track", metavar="NAME",
                      help="When the day is split across tracks, which track's portion to correct")
    p_uc.add_argument("--location", metavar="NAME",
                      help="Move the whole day to another worksite (id or name; must exist). "
                           "Empty string clears it.")

    p_adt = sub.add_parser("add-downtime", help="Log a downtime incident")
    p_adt.add_argument("id")
    p_adt.add_argument("date", metavar="YYYY-MM-DD")
    p_adt.add_argument("machine")
    p_adt.add_argument("--down-at", metavar="HH:MM")
    p_adt.add_argument("--resumed", metavar="HH:MM")
    p_adt.add_argument("--notes")

    p_udt = sub.add_parser("update-downtime", help="Edit an existing downtime entry")
    p_udt.add_argument("id")
    p_udt.add_argument("date", metavar="YYYY-MM-DD")
    p_udt.add_argument("machine")
    p_udt.add_argument("--match-down-at", metavar="HH:MM", help="Target entry by original down time (required when multiple entries match)")
    p_udt.add_argument("--down-at", metavar="HH:MM", help="New down time")
    p_udt.add_argument("--resumed", metavar="HH:MM", help="New resumed time")
    p_udt.add_argument("--notes", help="New notes (empty string clears it)")

    p_ddt = sub.add_parser("delete-downtime", help="Delete a downtime entry")
    p_ddt.add_argument("id")
    p_ddt.add_argument("date", metavar="YYYY-MM-DD")
    p_ddt.add_argument("machine")
    p_ddt.add_argument("--down-at", metavar="HH:MM", help="Disambiguate when multiple entries match")

    p_sw = sub.add_parser("switches", help="List switches for a project")
    p_sw.add_argument("id")

    p_asw = sub.add_parser("add-switch", help="Add a switch with its timber breakdown")
    p_asw.add_argument("id")
    p_asw.add_argument("name")
    p_asw.add_argument("date", metavar="YYYY-MM-DD")
    p_asw.add_argument("--timber", action="append", metavar="LEN:PLAN/ACT[:hb]",
                       help="Repeatable. e.g. 9:6/11  or  16:2/2:hb  (dash = 0)")
    p_asw.add_argument("--note")
    p_asw.add_argument("--location", metavar="NAME", help="Worksite (id or name; must already exist)")

    p_usw = sub.add_parser("update-switch", help="Update a switch (--timber replaces all timbers)")
    p_usw.add_argument("id")
    p_usw.add_argument("name", help="Switch name or id to find")
    p_usw.add_argument("--date", metavar="YYYY-MM-DD", help="Disambiguate when names repeat")
    p_usw.add_argument("--new-name")
    p_usw.add_argument("--timber", action="append", metavar="LEN:PLAN/ACT[:hb]",
                       help="Repeatable; replaces the full timber list")
    p_usw.add_argument("--note", help="New note (empty string clears it)")
    p_usw.add_argument("--location", metavar="NAME", help="Reassign worksite (id or name; empty string clears)")

    p_dsw = sub.add_parser("delete-switch", help="Delete a switch")
    p_dsw.add_argument("id")
    p_dsw.add_argument("name", help="Switch name or id")
    p_dsw.add_argument("--date", metavar="YYYY-MM-DD", help="Disambiguate when names repeat")

    p_drl = sub.add_parser("derails", help="List derails for a project")
    p_drl.add_argument("id")

    p_adr = sub.add_parser("add-derail", help="Add a derail with its timber breakdown")
    p_adr.add_argument("id")
    p_adr.add_argument("name")
    p_adr.add_argument("date", metavar="YYYY-MM-DD")
    p_adr.add_argument("--derail-type", choices=["stationary", "portable", "switch"],
                       help="stationary (head blocks), portable (no timbers), or switch (switch-to-nowhere)")
    p_adr.add_argument("--timber", action="append", metavar="LEN:PLAN/ACT[:hb]",
                       help="Repeatable. e.g. 12:2/2:hb")
    p_adr.add_argument("--note")
    p_adr.add_argument("--location", metavar="NAME", help="Worksite (id or name; must already exist)")

    p_udr = sub.add_parser("update-derail", help="Update a derail (--timber replaces all timbers)")
    p_udr.add_argument("id")
    p_udr.add_argument("name", help="Derail name or id to find")
    p_udr.add_argument("--date", metavar="YYYY-MM-DD", help="Disambiguate when names repeat")
    p_udr.add_argument("--new-name")
    p_udr.add_argument("--derail-type", choices=["stationary", "portable", "switch"])
    p_udr.add_argument("--timber", action="append", metavar="LEN:PLAN/ACT[:hb]",
                       help="Repeatable; replaces the full timber list")
    p_udr.add_argument("--note", help="New note (empty string clears it)")
    p_udr.add_argument("--location", metavar="NAME", help="Reassign worksite (id or name; empty string clears)")

    p_ddr = sub.add_parser("delete-derail", help="Delete a derail")
    p_ddr.add_argument("id")
    p_ddr.add_argument("name", help="Derail name or id")
    p_ddr.add_argument("--date", metavar="YYYY-MM-DD", help="Disambiguate when names repeat")

    p_loc = sub.add_parser("locations", help="List worksites (locations) on a company line")
    p_loc.add_argument("id")

    p_aloc = sub.add_parser("add-location", help="Add a worksite (location) to a company line")
    p_aloc.add_argument("id")
    p_aloc.add_argument("name", help="Display name (e.g. 'St. Johnsbury')")
    p_aloc.add_argument("--note")

    p_uloc = sub.add_parser("update-location", help="Rename a location or edit its note (id stays stable)")
    p_uloc.add_argument("id")
    p_uloc.add_argument("location", help="Location id or current name")
    p_uloc.add_argument("--new-name")
    p_uloc.add_argument("--note", help="New note (empty string clears it)")

    p_dloc = sub.add_parser("delete-location", help="Delete a location (refused if work references it)")
    p_dloc.add_argument("id")
    p_dloc.add_argument("location", help="Location id or name")

    p_cr = sub.add_parser("create", help="Create a new project or line")
    p_cr.add_argument("id", help="Job number (e.g. 942) or line abbreviation (e.g. VTR)")
    p_cr.add_argument("name", help="Display name (e.g. 'Project 942')")
    p_cr.add_argument("--kind", choices=["sponsored", "company"], default="company")
    p_cr.add_argument("--line", help="Railroad line for company projects (e.g. WACR_CRD)")
    p_cr.add_argument("--job", help="Job description")
    p_cr.add_argument("--base", help="Base of operations")
    p_cr.add_argument("--deadline", metavar="YYYY-MM-DD")
    p_cr.add_argument("--goal", type=int, metavar="N", help="Total tie goal")
    p_cr.add_argument("--daily-target", type=int, default=350, metavar="N")

    p_up = sub.add_parser("update", help="Update project metadata")
    p_up.add_argument("id")
    p_up.add_argument("--goal", type=int, metavar="N")
    p_up.add_argument("--deadline", metavar="YYYY-MM-DD")
    p_up.add_argument("--daily-target", type=int, metavar="N")
    p_up.add_argument("--line", help="Railroad line for company projects (e.g. WACR_CRD)")
    p_up.add_argument("--status", choices=["active", "complete", "archived"])

    p_ss = sub.add_parser("set-status", help="Set a project's status (active/complete/archived)")
    p_ss.add_argument("id")
    p_ss.add_argument("status", choices=["active", "complete", "archived"])

    p_ar = sub.add_parser("archive", help="Archive a project or line")
    p_ar.add_argument("id")

    p_ex = sub.add_parser("export", help="Export all data to SQLite")
    p_ex.add_argument("--output", metavar="PATH", help="Output .db file path")
    p_ex.add_argument("--year", type=int, metavar="YEAR", help="Filter to a specific year")

    p_rep = sub.add_parser("report", help="Build the report PDF and email it (the weekly timer runs this same path)")
    p_rep.add_argument("--project", metavar="ID", help="Report one project regardless of status (default: the active one)")
    p_rep.add_argument("--location", metavar="NAME", help="Narrow to one worksite (id or name)")
    p_rep.add_argument("--week", metavar="YYYY-MM-DD", help="Any date in the target week (default: most recent completed week)")
    p_rep.add_argument("--full", action="store_true", help="Whole project span instead of one week")
    p_rep.add_argument("--from", dest="from_date", metavar="YYYY-MM-DD", help="Range start")
    p_rep.add_argument("--to", dest="to_date", metavar="YYYY-MM-DD", help="Range end")
    p_rep.add_argument("--ties", choices=["new", "relay", "both", "none"], help="Which tie counts to include")
    p_rep.add_argument("--detail", choices=["summary", "itemized"], help="Consolidate switches/derails, or draw each")
    for flag in ("no-switches", "no-derails", "no-downtime", "no-charts"):
        p_rep.add_argument(f"--{flag}", action="store_true", help=f"Omit {flag[3:]}")
    p_rep.add_argument("--no-email", action="store_true", help="Generate but do not send")
    p_rep.add_argument("--recipients", metavar="A@X,B@Y",
                       help="Send to these addresses instead of the configured recipients")
    p_rep.add_argument("--output", "-o", metavar="PATH", help="Save the PDF here")

    p_user = sub.add_parser("user", help="Manage login accounts (admin, entry, viewer)")
    us = p_user.add_subparsers(dest="user_cmd", required=True)
    us.add_parser("list", help="List accounts")
    ua = us.add_parser("add", help="Add an account (prompts for the password unless --password)")
    ua.add_argument("email")
    ua.add_argument("name")
    ua.add_argument("--role", choices=["admin", "entry", "viewer"], default="viewer")
    ua.add_argument("--password", help="Set non-interactively (visible in shell history; prefer the prompt)")
    uu = us.add_parser("update", help="Change name, role, or password")
    uu.add_argument("email")
    uu.add_argument("--name")
    uu.add_argument("--role", choices=["admin", "entry", "viewer"])
    uu.add_argument("--password")
    uu.add_argument("--set-password", action="store_true", help="Prompt for a new password")
    ud = us.add_parser("delete", help="Remove an account")
    ud.add_argument("email")

    p_set = sub.add_parser("settings", help="Show or change organisation settings (recipients, mail, schedule)")
    ss = p_set.add_subparsers(dest="settings_cmd", required=True)
    ss.add_parser("show", help="Print the effective settings (password masked)")
    st = ss.add_parser("set", help="Change one or more settings")
    st.add_argument("--recipients", help="Comma-separated addresses that receive the weekly report")
    st.add_argument("--sender", help="From address")
    st.add_argument("--org-name")
    st.add_argument("--app-name")
    st.add_argument("--smtp-host")
    st.add_argument("--smtp-port", type=int)
    st.add_argument("--smtp-user")
    st.add_argument("--smtp-password")
    st.add_argument("--enable", action="store_true", help="Turn the weekly report on")
    st.add_argument("--disable", action="store_true", help="Turn the weekly report off")
    st.add_argument("--day", choices=["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
    st.add_argument("--hour", type=int)
    st.add_argument("--minute", type=int)
    st.add_argument("--timezone", help="e.g. America/New_York")
    te = ss.add_parser("test-email", help="Send a test message to prove mail works")
    te.add_argument("to")

    p_sch = sub.add_parser("schedule", help="Weekly report timer: status, or run it now")
    sc = p_sch.add_subparsers(dest="schedule_cmd", required=True)
    sc.add_parser("status", help="Show the timer state and when it next fires")
    sc.add_parser("run-now", help="Send this week's report immediately")

    p_imp = sub.add_parser("import", help="Copy a data bundle (projects/, archived/, users.json, settings.json) into DATA_DIR")
    p_imp.add_argument("bundle", help="Directory to import from")
    p_imp.add_argument("--overwrite", action="store_true", help="Replace existing users/settings/config files")
    p_imp.add_argument("--replace", action="store_true",
                       help="Remove every existing project first (clears the demo data); accounts are kept")
    sub.add_parser("verify", help="Load every project and print counts")

    p_tok = sub.add_parser("token", help="Per-user tokens for the MCP (AI assistant) server")
    tk = p_tok.add_subparsers(dest="token_cmd", required=True)
    tk.add_parser("list", help="List tokens (never the secrets)")
    tc = tk.add_parser("create", help="Create a token for an account; it is printed once")
    tc.add_argument("email")
    tc.add_argument("label", help="What it is for, e.g. 'Claude on my phone'")
    tc.add_argument("--days", type=int, default=90, help="Days until it expires (default 90)")
    tr = tk.add_parser("revoke", help="Revoke a token by id")
    tr.add_argument("id")

    return ap


def main() -> None:
    args = build_parser().parse_args()
    {
        "list":         cmd_list,
        "summary":      cmd_summary,
        "log":          cmd_log,
        "downtime":     cmd_downtime,
        "add-count":    cmd_add_count,
        "update-count": cmd_update_count,
        "add-downtime":    cmd_add_downtime,
        "update-downtime": cmd_update_downtime,
        "delete-downtime": cmd_delete_downtime,
        "switches":        cmd_switches,
        "add-switch":      cmd_add_switch,
        "update-switch":   cmd_update_switch,
        "delete-switch":   cmd_delete_switch,
        "derails":         cmd_derails,
        "add-derail":      cmd_add_derail,
        "update-derail":   cmd_update_derail,
        "delete-derail":   cmd_delete_derail,
        "locations":        cmd_locations,
        "add-location":     cmd_add_location,
        "update-location":  cmd_update_location,
        "delete-location":  cmd_delete_location,
        "create":       cmd_create,
        "update":       cmd_update,
        "set-status":   cmd_set_status,
        "archive":      cmd_archive,
        "export":       cmd_export,
        "report":       cmd_report,
        "user":         cmd_user,
        "settings":     cmd_settings,
        "schedule":     cmd_schedule,
        "import":       cmd_import,
        "verify":       cmd_verify,
        "token":        cmd_token,
    }[args.command](args)


if __name__ == "__main__":
    main()
