# User guide

For the crew: what the dashboard shows and how to log a day's work. Everything here works on
a phone.

## Signing in

Open the app and sign in with the email and password your admin gave you. What you can do
depends on your role:

- **viewer**: read the dashboard and generate reports.
- **entry**: everything a viewer can, plus log and correct work.
- **admin**: everything, plus Projects and Users & Settings.

Buttons you are not allowed to use are not shown.

## The sidebar

The sidebar lists your work.

- **Company lines** (for example a railroad division) are ongoing work. They can have
  **worksites** beneath them: a yard, a siding, a town. Tap the line for the whole line, all
  worksites combined. Tap a worksite to focus on that site alone.
- **Sponsored projects** are funded jobs with a tie goal and a deadline.

Whatever is selected in the sidebar is what the dashboard shows and what a report covers by
default.

## The dashboard

**Company line**: leads with **Total Timbers Installed**, then cards for switch timbers,
switches, derails, new ties, relay ties, and days worked. Charts show weekly production,
cumulative totals, and the mix of work. Below are the switches and derails (tabbed diagrams
beside their planned versus actual tables), the tie log, and the downtime log.

**Sponsored project**: leads with goal progress (remaining, percent complete, projected
finish), a progress bar, this week's output against the daily target, and the daily log.

Rows in the tie log and downtime log have an **Edit** button for entry users and admins.

## Log Work

Tap **Log Work** in the sidebar. One screen logs a day:

- **Date**: defaults to today. Any date works, so you can catch up on last week.
- **Ties installed**: the day's total.
- **Of those, relay (reclaimed) ties**: how many of the total were relay ties. Leave at 0 if
  all were new. Relay ties are always a part of the total, never added on top.
- **Track**: optional. If the day was split across tracks, log it once per track with the
  same date. The second entry adds to the first.
- **Worksite**: on a company line, which site the ties went in at. A day belongs to one
  worksite.
- **Equipment downtime**: add a row per machine that went down, with the time down and the
  time back in service. The duration is worked out for you. You can submit downtime without
  a tie count (a switch-only day, for instance).

The running total and the comparison to the daily target are recalculated by the app. You
never type those.

## Correct a day

Tap **Edit** on the row in the tie log. You can change the ties, the relay ties, the track
portion on a split day, or move the day to another worksite. Every downstream total is
recalculated.

Downtime rows work the same way: Edit opens the entry, where you can change the times and
notes or delete it.

## Switches and derails

Under **Manage**, tap **Switches & Derails**. Each is a named, dated record with a timber
breakdown: for each length, how many were planned and how many went in, and whether the
length is a head block. Tap **+ Add Switch** or **+ Add Derail**, name it, pick the date it
was completed and the worksite, add a row per timber length, and save.

Derails have a type: **stationary** (with head block timbers), **portable** (no timbers), or
**switch** (a switch-to-nowhere derail).

The diagrams show only timbers that were actually installed. The tables keep the whole
planned versus actual record. Switch and derail timbers count toward Total Timbers Installed
but are tracked separately from the daily tie count.

## Worksites

Under **Manage**, tap **Worksites** (company lines only). Add a site before logging work to
it. Renaming a site keeps its history: work is tied to the site's id, not its name. A site
that still has work logged against it cannot be deleted.

## Generating a report

The **Report** button in the header shows what it will cover ("Full line" or a worksite
name). Tap it to open the wizard, which has a live preview.

- **Worksite**: whole line or one site.
- **Time period**: the most recent reported week, a chosen week, the full project, or a date
  range.
- **What to include**: ties (new and relay, new only, relay only, none), switches, derails,
  charts, downtime, and whether to itemize every switch and derail or sum them up.
- **Download PDF**: saves the report to your device (phones open it in the PDF viewer). Needs
  no email setup.
- **Send**: type the recipient's email and tap **Generate & Send**.

[reports.md](reports.md) explains every section of the PDF.

## Help & Guide

The **Help & Guide** bar under the header opens a walkthrough of the app, with a spoken
audio tour.
