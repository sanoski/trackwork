# app/static/CLAUDE.md, the browser app

## Agent instructions: ES modules, one screen per file, no build step

**Module directory:** `app/static/`
**Files:** `index.html` (the shell), `style.css`, `js/*.js`, `vendor/chart.umd.min.js`,
`train.png`, `help-narration.mp3`.

## Scope
A phone-first single page app. `index.html` loads `js/main.js` as a module; everything else
is imported from there. `api.js` is the only fetch layer for `/api` (a 401 raises the
`auth:unauthorized` event, which `auth.js` turns into the sign-in screen). Shared state is the
one `state` object in `state.js`. Screens that are not needed on every visit (`structures`,
`projects_admin`, `admin`) load on demand with `import()`.

## Modules
| File | Owns |
|---|---|
| `main.js` | wiring: init, static event bindings, delegated row actions |
| `state.js`, `util.js`, `api.js` | shared state, helpers, fetch layer |
| `auth.js` | sign in/out, `canWrite()`, `isAdmin()`, sets `body.can-write` / `body.is-admin` |
| `projects.js` | sidebar tree, loading a project, worksite filtering, `refreshProject` |
| `dashboard.js` | cards, tables, entity panels, row action buttons (`.row-act[data-act]`) |
| `charts.js`, `diagrams.js` | Chart.js charts (vendored global `Chart`), switch/derail SVG |
| `reports.js` | Generate Report wizard, live preview, scoped button label |
| `panel.js` | the one side panel: `openScreen(title, html)`, `closeScreen()` |
| `entry.js` | Log Work (any date, relay ties, worksite, track) and Correct a Day |
| `downtime.js` | incident rows in Log Work; Edit Downtime |
| `structures.js` | Switches & Derails list and form (timber rows); Worksites |
| `projects_admin.js` | Projects: status, edit details, create |
| `admin.js` | Users, Email & Names, Weekly Report timer |
| `help.js` | Help & Guide modal and audio tour |

## Notes
- Role gating is CSS driven: `.writer-only`, `.admin-only`, and `.row-act` show only when
  `body.can-write` / `body.is-admin` are present; the server enforces the same rules.
- Assets: `pages.py` versions `js/*.js` + `style.css` with a content hash; modules are also
  served with `Cache-Control: no-cache` because relative imports carry no version token.
- No CDN: Chart.js is vendored and Oswald is served from `/report-assets/fonts`.
- Public text (labels, messages, help) uses no em dashes.
