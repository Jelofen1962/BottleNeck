# Changelog

All notable BottleNeck changes are documented here.

## [0.2.1] - 2026-11-14

### Fixed
- Removed the unnecessary `uvicorn[standard]` extras, which pulled in PyYAML and could trigger a Microsoft C++ Build Tools error on Windows.
- Pinned the project launcher to Python 3.12 for a predictable Windows setup.
- Updated Windows and macOS/Linux launch scripts and setup documentation.

## [0.2.0] - 2026-11-14

### Added
- FastAPI server and SQLite persistence.
- Account registration, sign-in, sign-out and server-side sessions.
- PBKDF2-SHA256 password hashing and HttpOnly session cookies.
- Workspace creation, workspace data isolation and owner/admin/member roles.
- One-time invitation codes with seven-day expiry.
- Tasks, task updates, task comments, projects, teams and activity history APIs.
- First-run product tour saved to the user account.
- In-app full handbook and release notes.
- uv project configuration and platform launch scripts.

### Changed
- Replaced browser localStorage as the source of truth with authenticated API requests.
- Dashboard figures now derive from real workspace data. Empty workspaces start with zero records.
- Updated settings and team pages for server-backed accounts and invitations.

## [0.1.0] - 2026-11-14

### Added
- First visual preview of the Persian RTL BottleNeck workspace.
- Dashboard, task list, Kanban, calendar, projects, team and activity screens.
- Local browser interactions and preliminary SQLite schema.
