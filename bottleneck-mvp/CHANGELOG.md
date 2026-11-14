# BottleNeck changelog

## v0.6.0 — MVP administration, account security and reliability

- Added multiple workspaces per account, workspace creation and in-app workspace switching.
- Added a workspace-scoped permission matrix for admin/member roles; owners retain full access within their workspace.
- Added per-role read/write ACLs for shared drive folders and files, inherited through parent folders.
- Added TOTP two-factor authentication and ten hashed, single-use recovery codes shown only during setup.
- Added five-attempt limits per TOTP login challenge and five-minute challenge expiry.
- Added one-time password reset links with a 30-minute expiry, SMTP password-reset email delivery and an admin-generated manual reset link.
- Added optional SMTP notification delivery with per-user email/category preferences and a retry queue.
- Added authenticated WebSocket events for workspace collaboration, with session revocation checks during an open connection.
- Added automatic ZIP backups (24-hour default interval, 14-copy default retention) and manual backup create/list/download.
- Restricted global backup archives to the initial installation owner because each archive contains the whole instance database and file stores.
- Added backup manifest and restore guidance; archives include SQLite, task uploads and shared-drive files.
- Added optional Uvicorn HTTPS startup through certificate/key environment variables and secure session cookies.
- Avoids creating empty automatic backups before the first account exists.
- Preserved Persian RTL UI, Vazirmatn/Roboto typography, approximately 120% desktop scale, responsive mobile scale, LAN port 1939 and creator credit.
- Updated the in-app handbook, external README and installation scripts.

## v0.5.0 — Shared space, knowledge and collaboration

- Added workspace concept boards with movable sticky-note, text, link and task cards.
- Added shared drive folders, files and Markdown text nodes.
- Added workspace-wide, team-only and password-protected share modes.
- Added upload progress, streamed server writes and a 50 MB shared-file limit.
- Added authenticated downloads and folder permission inheritance.
- Added Markdown source editor with GFM preview and HTML sanitization.
- Added workspace and team chat channels, presence and shared activity events.

## v0.4.0 — Productivity and workflow

- Added time entries and one-active-timer-per-user enforcement.
- Added daily/weekly reports with task and time summaries.
- Added recurring rules, reusable task templates and checklists.
- Added task dependencies, cycle validation and completion guards.
- Added approval requests and owner/admin decisions.
- Added workspace status labels/colors and 120% desktop scale.

## v0.3.0 — Team collaboration and LAN

- Added multiple task assignees, checklists, task attachments, in-app notifications and team membership management.
- Added LAN access on port 1939, guided tour, in-app handbook, activity history and creator credit popup.

## v0.2.1 — Windows installation fix

- Pinned launch setup to Python 3.12.
- Removed optional Uvicorn extras that pulled in unnecessary PyYAML compilation on Windows.

## v0.2.0 — Server foundation

- Introduced FastAPI, SQLite, server-side authentication/session storage, workspaces, invitations, tasks, projects and activity history.
