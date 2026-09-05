# Claude and the MCP server

The app includes an MCP (Model Context Protocol) server. Connect it to Claude and you can
read the dashboard and log work by describing it:

> We put in 412 ties at St. Johnsbury today, 200 of them relay, all on Track 3. The tamper
> was down from 9:15 to 10:40.

Claude calls the same functions the web app and the CLI use, so what it logs is exactly what
you would have typed. It can also answer questions ("how far behind target are we this
week?") from the live data.

## Turning it on

In `.env`:

```
MCP_ENABLED=true
MCP_AUTH_PROVIDER=token
MCP_BASE_URL=https://mow.example.com
```

Restart the app. The endpoint is `https://mow.example.com/mcp`. `MCP_BASE_URL` must be the
public URL clients use; the server refuses other host names.

## Authentication

The MCP endpoint can log work, so it is never open on the internet. `MCP_AUTH_PROVIDER`
picks how clients prove who they are.

### `token` (default): per-user tokens issued by the app

An admin creates a token for a user under **Users & Settings, AI (Claude)** or with
`scripts/cli.py token create <email> "<label>" --days 90`. The token is shown once. It is tied
to that account, expires, and can be revoked from the same screen. This is not a shared
secret: each person has their own.

Works with Claude Code, the Claude desktop app, and any MCP client that can send an
`Authorization: Bearer` header.

**Claude Code** (terminal):

```bash
claude mcp add --transport http mow https://mow.example.com/mcp \
  --header "Authorization: Bearer <token>"
```

**Claude desktop app**: add a remote MCP server with the URL and the same header, following
the app's current connector settings.

### `azure`, `google`, `github`: sign in through an identity provider

claude.ai web connectors register themselves with the server and sign in through OAuth, so
they cannot use a bearer token. For those, register an OAuth application with your provider
and set:

```
MCP_AUTH_PROVIDER=azure          # or google, github
MCP_BASE_URL=https://mow.example.com
MCP_OAUTH_CLIENT_ID=...
MCP_OAUTH_CLIENT_SECRET=...
MCP_OAUTH_TENANT=...             # Azure only: your directory (tenant) id
```

Redirect URI to register with the provider: `https://mow.example.com/auth/callback`.

Then in claude.ai: Settings, Connectors, Add custom connector, with the URL
`https://mow.example.com/mcp`. Claude will send the user to your provider to sign in.

Azure (Microsoft 365) is the natural choice for an organisation already on Microsoft.

### `none`: no authentication

Local development only. Never expose it on a network.

## Tools

Every tool has a web route and a CLI command that do the same thing. Errors come back as
`{"error": "..."}` rather than exceptions.

| Tool | What it does | CLI twin |
|---|---|---|
| `list_projects` | All projects with status, totals, and worksites | `list` |
| `get_project_summary` | Computed stats: totals, progress, projected finish | `summary` |
| `get_daily_log` | Every tie day, with relay and new derived | `log` |
| `get_downtime_log` | Every downtime entry | `downtime` |
| `get_switches`, `get_derails` | Each with its timber breakdown and totals | `switches`, `derails` |
| `get_locations` | Worksites on a line, with how much work references each | `locations` |
| `add_daily_count` | Log a day: ties, relay ties, optional track and worksite. Same date plus a new track adds to the day. | `add-count` |
| `update_daily_count` | Correct a day (or one track of a split day); move it to another worksite | `update-count` |
| `add_downtime`, `update_downtime`, `delete_downtime` | Downtime by machine and date; `down_at` disambiguates | `add-downtime`, `update-downtime`, `delete-downtime` |
| `add_switch`, `update_switch`, `delete_switch` | Switch with `timbers: [{length, planned, actual, head_block}]`; update replaces the timber list | `add-switch`, `update-switch`, `delete-switch` |
| `add_derail`, `update_derail`, `delete_derail` | Same, plus `derail_type` stationary, portable, or switch | `add-derail`, `update-derail`, `delete-derail` |
| `add_location`, `update_location`, `delete_location` | Worksites; rename keeps the id; delete refused while referenced | `add-location`, `update-location`, `delete-location` |
| `create_project` | Sponsored or company; starts active | `create` |
| `update_project` | Goal, deadline, daily target | `update` |
| `set_status` | active, complete, archived | `set-status` |

Rules Claude follows because the service layer enforces them: relay ties are a subset of
ties; a day is worked at one worksite; a worksite must exist before work is tagged to it;
running totals are recalculated on every write; exactly one project is active.

## Tips for talking to it

- Say the project when it is not obvious. Claude reads the project list first and usually
  infers it.
- Give dates plainly ("Thursday the 25th"); Claude knows today's date.
- For a split day, name the tracks and the count on each.
- Ask it to read back what it logged. `get_daily_log` shows exactly what is stored.

## Running the MCP server on its own

For development the server also runs standalone on port 8001:
`python mcp_server/server.py`. In production it is mounted inside the web app at `/mcp`,
sharing one process, one port, and one set of data locks.
