# BottleNeck changelog

## v0.4.0 – Productivity and workflow

- Added persistent task time entries and one-active-timer-per-user enforcement.
- Added daily and Saturday–Friday weekly reports with time totals by member and project.
- Added recurring rules for daily, weekly and monthly task generation, including catch-up on workspace load.
- Added reusable task templates with checklists and default assignments.
- Added task dependency management, cycle detection and completion guards.
- Added approval requests with owner/admin decision flow and decision comments.
- Added workspace-specific labels and color choices for the five built-in statuses.
- Added new navigation areas for reports, approvals, recurring rules and templates.
- Increased desktop interface scale to approximately 120%; mobile layout stays at normal scale.
- Preserved LAN port 1939, existing user sessions, creator credit and the previous v0.2/v0.3 database records.
- Added database migration tables and expanded handbook / setup instructions.

## v0.3.0 – Team collaboration and LAN

- Multiple task assignees, checklists, private attachments, notifications, team membership management and LAN access on port 1939.
- Added a guided tour, handbook, version history and creator credit popup.

## v0.2.1 – Windows install fix

- Pinned setup to Python 3.12 and removed Uvicorn's optional standard extras to avoid unnecessary PyYAML native builds.

## v0.2.0 – Server foundation

- Introduced FastAPI, SQLite, server-side accounts/sessions, workspaces, invitations, tasks, projects and activity history.
