# Admin guide

What the admin does, in the app or from the command line. The two are interchangeable: every
screen under Users & Settings has a `scripts/cli.py` command ([cli-reference.md](cli-reference.md)).

## Users

**Users & Settings, Users tab.** Add a user with a name, email, role, and password (at least
8 characters). Change a role or reset a password from the row. The last admin cannot be
demoted or deleted, so there is always someone who can get in.

Roles: `admin` (everything), `entry` (log and correct work, switches, derails, worksites,
downtime), `viewer` (read only).

CLI: `user list`, `user add`, `user update`, `user delete`.

## Email & Names

**Users & Settings, Email & Names tab.**

- **Organisation** and **App name** appear on the report header and in the email subject.
- **Recipients**: who gets the weekly report, comma separated. On-demand reports from the
  wizard go to whatever address the sender types, not to this list.
- **From address** and the **SMTP server, port, username, password**. Port 587 with STARTTLS.
  A saved password is never shown again; leaving the field blank on a later save keeps it.
- **Send Test** sends a short message to an address you choose and reports the exact SMTP
  error if it fails.
- Mail is optional. With no server configured, Generate & Send and the weekly timer report
  a clear error, and Download PDF in the wizard still works for everyone.

CLI: `settings show`, `settings set`, `settings test-email`.

## Weekly report

**Users & Settings, Weekly Report tab.** Turn the timer on or off, choose the day, time, and
time zone. The screen shows the next run, the last run, and the last error.

How the timer behaves:

- It runs inside the app. No cron job to maintain.
- It reports on the most recently completed Sunday-to-Saturday week. Sunday morning is the
  natural time.
- It sends once per week. If the app restarts after the run it does not send again. **Send
  This Week's Report Now** bypasses that guard for a deliberate resend.
- If nothing was logged in that week for the active project, it sends nothing and records
  "nothing to report".

CLI: `schedule status`, `schedule run-now`, `report` (for one-off reports with options).

## AI (Claude)

**Users & Settings, AI (Claude) tab.** Only visible when `MCP_ENABLED=true`. Create a token
for a user with a label and a lifetime (default 90 days, maximum a year). The token is shown
once. Revoke it from the list at any time. Tokens are tied to the account and expire on their
own. See [mcp-and-claude.md](mcp-and-claude.md) for connecting a client.

CLI: `token list`, `token create`, `token revoke`.

## Projects

**Manage, Projects.** Create a project, edit its details, and set its status.

- **Kind**: `sponsored` (a funded job: goal, deadline, daily target, code-name id such as
  `942`) or `company` (railroad-line work: a line id such as `WACR_CRD`, usually no goal).
- **Status**: `active`, `complete`, or `archived`. Exactly one project is active at a time;
  activating one demotes the previous active project to complete. Complete projects stay
  visible and reportable. Archived projects are moved out of the sidebar into
  `DATA_DIR/archived/`.
- The weekly timer always reports on the active project.

CLI: `create`, `update`, `set-status`, `archive`, `list`, `summary`.

## Equipment list

The machines offered in the downtime form live in `DATA_DIR/config.json`. Add one with
`POST /api/equipment` or by editing the file. The default list: Tie Inserter, Broom, Plate
Setter, Tamper, Spiker/Gauger, Other.

## Backups and data

Everything is under `DATA_DIR`. Back that directory up ([setup.md](setup.md) has the
commands). `scripts/cli.py export --output mow.db` writes a SQLite copy of every project for
spreadsheets or analysis. `scripts/cli.py verify` loads every project and prints counts, a
quick check after a restore.

Project files are plain JSON, one per project. Avoid editing them by hand; every write
through the app recalculates running totals, and hand edits do not.

## Public read

`PUBLIC_READ=true` in `.env` lets anyone with the URL see the dashboard and reports without
signing in. Writes still require an account. Off by default.
