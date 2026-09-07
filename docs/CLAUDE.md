# docs/CLAUDE.md, human documentation

## Agent instructions: one audience per page, keep it current with the code

**Module directory:** `docs/`

| File | Audience | Must stay in step with |
|---|---|---|
| `setup.md` | the IT person installing it | `deploy/`, `.env.example`, `app/config.py` |
| `setup-with-ai.md` | the same person, using Claude as a guide | `setup.md` |
| `user-guide.md` | the crew | `app/static/` screens and labels |
| `admin-guide.md` | the admin | `app/routes/admin.py`, `app/static/js/admin.js`, `projects_admin.js` |
| `reports.md` | anyone reading the PDF | `app/reporting/` |
| `mcp-and-claude.md` | whoever connects Claude | `mcp_server/` |
| `cli-reference.md` | command line users | `scripts/cli.py` (every command listed) |
| `architecture.md` | developers | the directory CLAUDE.md files |
| `troubleshooting.md` | anyone stuck | error strings in the services and routes |
| `help-audio-narration.md` | whoever re-records the in-app audio tour | `app/static/index.html` help modal |

## Rules
- Plain sentences, no em dashes, no real names or hosts (use example.com for hosts and addresses).
- Say "worksite" for a location, "relay" for reclaimed ties, "company line" and "sponsored
  project" for the two kinds.
- A new route, tool, or command is not done until it appears in its reference page.
- Commands in fenced blocks; nothing a reader must type lives only in prose.

`images/` holds the README screenshots and `sample-report*.pdf` the demo-data PDFs. Regenerate them from a demo instance (never from real data) when the screens change.
