# BottleNeck v0.4.0

BottleNeck is a Persian RTL team workspace served by FastAPI and backed by SQLite. It runs on a trusted local network on TCP port **1939**. The desktop interface is scaled to approximately **120%**; the scale returns to 100% on narrow/mobile screens.

## Start on Windows

1. Extract the ZIP.
2. Open PowerShell in the `bottleneck-mvp` folder.
3. Run:

   ```powershell
   .\start.ps1
   ```

The launcher uses Python 3.12 through `uv`, installs the small FastAPI/Uvicorn dependency set, and starts the server at `0.0.0.0:1939`.

Open BottleNeck on the host at `http://127.0.0.1:1939`. Other devices on the same trusted LAN use `http://<host-LAN-IP>:1939`; the exact detected URLs are printed by the launcher and shown in **Settings → Local network access**.

If a device cannot connect, make sure the Windows network profile is Private and run `allow-lan-firewall.ps1` once from an elevated PowerShell. The helper creates an inbound rule for TCP 1939 scoped to the local subnet and Private profile. Do not port-forward this app or expose the development server to the public internet.

## Start on Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

Or manually:

```bash
uv sync --python 3.12
BOTTLENECK_PORT=1939 uv run --python 3.12 uvicorn main:app --host 0.0.0.0 --port 1939
```

## Features in v0.4.0

### Workspace and collaboration

- Server-side accounts, password hashing, HttpOnly sessions, workspace membership and invitations.
- Owner, admin and member roles.
- Multiple assignees, team membership, project grouping, comments, checklists, private attachments (10 MB per file), in-app notifications and activity history.
- LAN collaboration through a workspace event feed polled every 3.5 seconds.

### Productivity and workflow

- **Time tracking:** start/stop a personal timer on a task. A user can have one active timer at a time. Completed entries are stored with user, task, start, end and duration.
- **Reports:** daily and Persian-weekly summaries for tasks created/completed, overdue/open work and time tracked by member and project. Weekly reports run Saturday–Friday. Report date boundaries are evaluated in UTC.
- **Recurring work:** daily, weekly and monthly rules with an interval, initial execution date, optional due-date offset and default assignees. Due work is generated when a workspace is opened. The host server therefore needs to be running and a member needs to open the workspace for the scheduler catch-up to run; this release does not run a separate background scheduler.
- **Task templates:** reusable task title, description, priority, estimate, default assignees, project/team and starter checklist. Members can create tasks from templates; admins can create and remove templates.
- **Dependencies:** tasks can depend on other tasks in the same workspace. The API blocks dependency cycles and prevents a task from being marked complete until all prerequisites are complete.
- **Approval workflow:** members can send a task for review. Owners/admins can approve it (which completes the task) or reject it (which returns it to in-progress with an optional comment).
- **Custom status presentation:** owners/admins can customize labels and colors for the five built-in workflow states. The underlying five state keys remain fixed for this MVP.
- **120% desktop scale:** the application uses a 1.2 page zoom on desktop Chromium browsers and resets to normal scale on narrow screens.

## First run

1. Open the host URL.
2. Select **ساخت فضای کار** and register the first account. This account becomes the workspace owner.
3. Complete the guided tour, or revisit it using the help icon.
4. Create projects and teams, then invite colleagues from **تیم‌ها و اعضا**. Invitations are manually shared links valid for seven days.
5. Create tasks or task templates, define dependencies, add checklists and start timers as work begins.
6. Use **گزارش‌های عملکرد** for daily/weekly summaries and **درخواست‌های تأیید** for pending reviews.

## Recurring task behavior

Rules are evaluated whenever a signed-in user requests the workspace bootstrap data. If a rule is due, the server creates each missed occurrence up to 24 catch-up instances per rule in one pass, then advances its next date. Further overdue instances are generated on subsequent workspace loads. For continuous scheduled creation even when nobody opens the app, a future release should add a dedicated scheduler service.

## Database and file storage

Default locations:

```text
data/
├── bottleneck.sqlite3
└── uploads/
    └── <workspace-id>/
```

The database uses SQLite WAL mode. **Back up the complete `data/` directory**, including uploads. For a simple offline backup, stop BottleNeck first and then copy `data/`. Do not copy only the `.sqlite3` file while the server is writing.

On startup, `schema.sql` creates the new v0.4 tables. Existing v0.2/v0.3 user, workspace, task, project, comment, checklist, attachment and activity data is retained. Existing workspace status labels are initialized with the default five statuses. Back up `data/` before upgrading any existing installation.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `BOTTLENECK_DB` | `./data/bottleneck.sqlite3` | SQLite database path |
| `BOTTLENECK_UPLOAD_DIR` | `./data/uploads` | Uploaded file directory |
| `BOTTLENECK_SESSION_DAYS` | `14` | Session lifetime |
| `BOTTLENECK_COOKIE_SECURE` | `0` | Set to `1` behind HTTPS |
| `BOTTLENECK_PORT` | `1939` | Port used for LAN and invite URLs |

## Role overview

| Feature | Owner | Admin | Member |
|---|:---:|:---:|:---:|
| View workspace tasks, projects and teams | Yes | Yes | Yes |
| Create/edit tasks, comments and checklists | Yes | Yes | Yes |
| Use task timers and view reports | Yes | Yes | Yes |
| Set dependencies and request approval | Yes | Yes | Yes |
| Create tasks from templates | Yes | Yes | Yes |
| Manage teams, invitations and memberships | Yes | Yes | No |
| Create/manage recurring rules | Yes | Yes | No |
| Create/delete templates | Yes | Yes | No |
| Customize status labels/colors | Yes | Yes | No |
| Approve/reject task approvals | Yes | Yes | No |

## API endpoints

- `GET /api/health` – server/version health.
- `GET /api/bootstrap` – workspace snapshot.
- `GET /api/network` – detected LAN URLs.
- `GET /api/docs` – interactive API documentation.
- `GET /api/reports?period=daily|weekly` – reports.
- `GET /api/recurring` / `POST /api/recurring` – recurring rules.
- `GET /api/templates` / `POST /api/templates` – task templates.
- `GET /api/tasks/{id}/time` – task time entries.
- `GET /api/tasks/{id}/dependencies` – dependency configuration.
- `GET /api/tasks/{id}/approvals` – task approval history.

## Known MVP boundaries

- No automatic email delivery, password reset or two-factor authentication.
- Each account still has one workspace.
- Collaboration uses polling, not WebSockets.
- Recurring tasks are generated on workspace loads, not by a continuously running scheduler.
- Only the five built-in status states are supported; their labels and colors are customizable, but adding/removing workflow states is not supported.
- Reports use UTC boundaries. A later release can add configurable workspace timezone and export formats.
- No attachment virus scanning. Use only with trusted team members and uploads.
- No HTTPS is configured for LAN HTTP. Do not expose this development server directly to the internet.

## Project structure

```text
bottleneck-mvp/
├── main.py
├── index.html
├── schema.sql
├── static/
│   ├── app.js
│   └── styles.css
├── data/                       # created on first run
├── README.md
├── HANDBOOK.md
├── CHANGELOG.md
├── pyproject.toml
├── start.ps1
├── start.sh
└── allow-lan-firewall.ps1
```
