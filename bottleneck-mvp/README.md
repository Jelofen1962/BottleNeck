# BottleNeck · Team Work Tracker

**Version:** 0.2.1 · **Status:** runnable server-backed MVP · **Interface:** Persian / RTL

BottleNeck is a compact team workspace for creating and assigning work, tracking status, coordinating projects, and keeping a shared activity trail. Unlike the 0.1.0 visual preview, this release stores accounts and workspace data on the server in SQLite. Multiple people can sign in from separate browsers and work in the same invited workspace.

## What is included

- Server-side account registration, sign-in and sign-out.
- PBKDF2-SHA256 password hashing. Plain-text passwords are never stored.
- HttpOnly, SameSite session cookies with configurable expiry.
- Workspace creation and workspace-scoped data access.
- Owner, admin and member roles.
- Invitation links for teammates. Links expire after 7 days; the invited person must register with the invited email address. Email delivery is not configured, so copy and send the link yourself.
- Tasks with status, priority, assignee, team, project, due date and estimated hours.
- Task editing, completion, deletion rules, task comments and Kanban drag-and-drop.
- Projects with progress calculated from their tasks.
- Team creation and a member directory.
- Calendar, dashboard, task lists, team workload and activity history.
- First-login product tour, restartable from the help icon.
- In-app handbook covering each screen, workflows, account security and version changes.
- SQLite persistence and a standalone `schema.sql`.
- Responsive RTL layout with Vazirmatn, Roboto and Lucide icons.

## Requirements

- Python 3.12 (installed automatically by `uv` when needed).
- [uv](https://docs.astral.sh/uv/).
- An internet connection on first dependency installation, and for Google Fonts / Lucide CDN assets.

## Run on Windows (PowerShell)

1. Extract `BottleNeck-MVP.zip`.
2. Open PowerShell in the extracted `bottleneck-mvp` folder.
3. Run:

   ```powershell
   uv sync --python 3.12
   uv run --python 3.12 uvicorn main:app --host 127.0.0.1 --port 8000
   ```

4. Open **http://127.0.0.1:8000**.
5. Choose **ساخت فضای کار** and create the first owner account.

You can also run `./start.ps1` (PowerShell also accepts `\.\start.ps1`) from PowerShell. The script creates a Python 3.12 environment, installs only the required pure-Python Uvicorn dependencies, and starts the server. Python 3.12 is downloaded by `uv` if it is not already installed.

## Run on macOS / Linux

```bash
uv sync --python 3.12
uv run --python 3.12 uvicorn main:app --host 127.0.0.1 --port 8000
```

Or run `./start.sh` after making it executable (`chmod +x start.sh`).

## First-time setup and inviting your team

1. The first person who registers creates the workspace and becomes its **owner**.
2. Complete the guided tour. It can be restarted at any time using the question-mark icon in the top bar, or from the handbook.
3. Open **اعضای فضای کار** and choose **دعوت عضو**.
4. Enter the teammate's email and choose `عضو` or `مدیر`.
5. Copy the invitation URL from the result dialog and send it to the teammate using your usual messaging or email app.
6. The teammate opens the URL and registers with the same email address. The account joins the existing workspace rather than creating a new one.
7. Create projects and tasks, then assign a task to a workspace member.

An invitation link is valid for seven days and may be used once. In this MVP, invitations are not emailed automatically.

## Data location and backups

By default, SQLite is created automatically at:

```text
data/bottleneck.sqlite3
```

The `data/` folder is created on first server startup. Stop the server before manually copying the database file. For a live environment, use SQLite's online backup API or a scheduled consistent backup rather than copying an actively-written database. The database path can be changed with `BOTTLENECK_DB`.

## Configuration

Environment variables are optional:

| Variable | Default | Purpose |
|---|---|---|
| `BOTTLENECK_DB` | `./data/bottleneck.sqlite3` | SQLite database file path |
| `BOTTLENECK_SESSION_DAYS` | `14` | Session-cookie lifetime in days |
| `BOTTLENECK_COOKIE_SECURE` | `0` | Set to `1` when serving over HTTPS |

Example PowerShell configuration:

```powershell
$env:BOTTLENECK_DB = "D:\BottleNeckData\bottleneck.sqlite3"
$env:BOTTLENECK_SESSION_DAYS = "14"
$env:BOTTLENECK_COOKIE_SECURE = "1"
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

For access from other devices on your trusted LAN, bind to `0.0.0.0` and connect using the host computer's LAN IP. Do not expose the development server directly to the public internet.

## API and developer notes

- Health check: `GET /api/health`
- Interactive API reference: `GET /docs`
- OpenAPI schema: `GET /openapi.json`
- The browser interface is served by FastAPI from the same origin. API requests use the HttpOnly session cookie.
- All task, project, team, invitation and activity reads/writes are scoped to the signed-in user's workspace.
- The server initializes missing tables at startup. `schema.sql` documents the SQLite schema.
- Front-end files are plain HTML, CSS and JavaScript. There is no Node, npm, bundler or frontend build step.

## Roles and permissions

| Capability | Owner | Admin | Member |
|---|:---:|:---:|:---:|
| View workspace data | Yes | Yes | Yes |
| Create and edit tasks | Yes | Yes | Yes |
| Comment on tasks | Yes | Yes | Yes |
| Delete tasks | Any task | Any task | Tasks they created |
| Create projects | Yes | Yes | Yes |
| Delete projects | Yes | Yes | No |
| Create teams | Yes | Yes | No |
| Invite teammates | Yes | Yes | No |

## Windows dependency troubleshooting

BottleNeck uses the base `uvicorn` package, not `uvicorn[standard]`. The optional `standard` extras include packages that may need native compilation on some Python/Windows combinations. This app does not use those extras. If you previously ran the older launcher and it created a partial environment, remove it before retrying:

```powershell
Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue
Remove-Item -Force uv.lock -ErrorAction SilentlyContinue
uv sync --python 3.12
uv run --python 3.12 uvicorn main:app --host 127.0.0.1 --port 8000
```

No Microsoft C++ Build Tools are required for the BottleNeck dependency set.

## MVP boundaries

This is a functional MVP, not a finished enterprise deployment. The following are deliberately outside this release:

- Automatic email delivery, password reset and multi-factor authentication.
- Multiple workspaces per user and workspace switching.
- Fine-grained project/team membership and multiple assignees per task.
- File uploads, task checklists, recurring tasks, dependency graphs and time-entry timers.
- Push / email notifications, real-time sockets and native mobile apps.
- Automated tests, production reverse proxy, HTTPS certificate and deployment orchestration.

For a public deployment, place the app behind HTTPS, set `BOTTLENECK_COOKIE_SECURE=1`, configure backups, add rate limiting and account-recovery processes, and review the server's operational security.

## Project files

```text
bottleneck-mvp/
├── main.py          # FastAPI app, auth, API and SQLite access
├── index.html       # RTL SPA and in-app handbook
├── styles.css       # Design system and responsive layout
├── app.js           # SPA interactions and API client
├── schema.sql       # SQLite schema reference
├── HANDBOOK.md      # Full product and workflow handbook
├── CHANGELOG.md     # Release history
├── pyproject.toml   # uv project dependencies
├── start.ps1        # Windows launcher
└── start.sh         # macOS / Linux launcher
```
