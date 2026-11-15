# Architecture

BottleNeck uses a single FastAPI application and a browser-based frontend. The default installation runs one Uvicorn process against one local SQLite database; this keeps deployment and backup straightforward, but it also defines the current scaling boundary.

## Runtime map

```text
Browser
  ├── index.html
  ├── static/styles.css
  └── static/app.js
        │ REST + authenticated WebSocket events
        ▼
FastAPI application (main.py)
  ├── authentication and sessions
  ├── workspace membership and permissions
  ├── tasks, projects, notes, boards and chat
  ├── server administration endpoints
  └── recurring / backup / mail background tasks
        │
        ├── SQLite database
        ├── data/uploads
        ├── data/shared
        ├── data/chat_uploads
        ├── backups
        └── logs
```

## Frontend

The client uses HTML, CSS and vanilla JavaScript. `index.html` provides the shell; `static/styles.css` defines the visual system; `static/app.js` handles navigation, API calls, dialogs, presence and workspace interactions. The UI is Persian-first, uses RTL layout and supports a Jalali display calendar while the database stores sortable ISO timestamps.

## Backend

`main.py` contains the FastAPI routes and SQLite access helpers. API handlers resolve the current session and check workspace or server-level permissions before returning or mutating data. Uploaded files live outside the static directory; download routes check access before returning them.

`bottleneck_cli.py` handles first-run server-owner setup, serving, diagnostics, logs, backups, restore and selective import/export. The server owner is distinct from a workspace owner.

## Data and background work

SQLite runs in WAL mode with foreign keys enabled. Background tasks handle recurring work, backup scheduling and optional notification email. Run one application process: multiple Uvicorn workers would duplicate those jobs and can contend over SQLite writes.

The `data/` directory contains the database and user content. `backups/` contains full installation archives, while `logs/` contains rotating operational logs. All three are runtime data and must stay out of Git.

## Design constraints

- API handlers enforce permissions; frontend visibility is only a convenience.
- Workspace IDs scope business data. Server administration uses a separate role table.
- Full-system backups contain data from every workspace and need stricter access than workspace exports.
- SQLite should stay on local storage, not a network filesystem.
- The current release does not provide a multi-node deployment model or conflict-free collaborative document editing.
