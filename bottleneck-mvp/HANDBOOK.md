# BottleNeck handbook

**Product:** BottleNeck Team Work Tracker  
**Current release:** 0.2.1  
**Interface language:** Persian (RTL)

This handbook explains the purpose of each workspace area, how to perform its main workflows, and what is included in the current MVP.

## 1. Start here

The first person to create an account also creates a workspace and receives the owner role. The workspace is where tasks, projects, members, teams and activity live. It is stored in SQLite on the server.

After registration, the guided tour walks through the main areas. The tour is saved against the account, so it will not automatically repeat after completion. Use the help icon in the top bar or the link at the end of this handbook to run it again.

Recommended setup:

1. Choose a workspace name that your team will recognize.
2. Invite colleagues from the Team page.
3. Create one project for each shared outcome or initiative.
4. Create tasks with a clear deliverable, assignee, status and due date.
5. Review the dashboard and activity page as part of the team's routine.

## 2. Overview

The dashboard summarizes actual workspace records. It displays all tasks, tasks in progress, completed tasks, overdue tasks, the completion share, tasks approaching their due dates, recent activity and open work per member. A newly created workspace correctly starts at zero; the app does not seed fictional metrics or sample records.

Use the top-bar **New task** action to capture work from any screen. Select a task in the upcoming list to inspect it.

## 3. My tasks

This view is filtered to tasks assigned to the currently signed-in account. Use the All / Open / Completed tabs to narrow the list. Sorting is available by due date, priority and creation date. The circular control at the start of a row toggles a task between completed and queued; use the detail view when you need to change to a different status.

A task without an assignee will not appear in anyone's personal list until it is assigned.

## 4. All tasks

This is the workspace-wide task register. It includes status tabs and filters for team and project. Search in the top bar looks through the current task title, description, assignee, project and team. Open any task to read its details and comments.

Task fields:

- **Title:** required, concise and expressed as an outcome or action.
- **Description:** context, expected result and acceptance notes.
- **Assignee:** one workspace member responsible for driving the work.
- **Team:** optional group used to categorize the work.
- **Project:** optional shared outcome the task contributes to.
- **Status:** current stage in the workflow.
- **Priority:** urgency or importance.
- **Due date:** target completion date.
- **Estimate:** optional planned effort in hours.

## 5. Kanban board

The board groups tasks into five columns: Queued, In progress, Review, Blocked and Done. Drag a card to another column to save its new status on the server. If the network request fails, the workspace is reloaded so the visible state returns to the persisted state.

Suggested working agreement:

- Keep the In progress column limited to work someone is actively advancing.
- Move work to Review when its output is ready for inspection.
- Use Blocked only when progress cannot continue without a dependency, answer or decision.
- Add a comment explaining a blocker or the review request.

## 6. Calendar

The calendar is a month view of task due dates. Use the arrows around the month title to move between months. Click a task event to open its detail panel. Tasks without a due date are intentionally absent from the calendar.

## 7. Projects

Projects group tasks around a result. Create a project with a name and a short description, then connect relevant tasks to it. Project progress is calculated as completed tasks divided by all tasks assigned to that project. An empty project displays zero progress because it has no linked tasks.

Project names and descriptions can be edited. Owners and admins can delete a project; related tasks remain in the workspace and become unassigned from that project.

## 8. Team and invitations

The member directory displays account name, email, role and the number of open tasks assigned to each member. Teams are workspace-level labels that can be selected on tasks.

Owners and admins can create teams and invitation links. An invitation:

1. Is generated for one email address.
2. Has either Member or Admin access.
3. Expires after seven days.
4. Can be accepted once.
5. Requires registration with the same email address as the invitation.

The invite link is displayed only after creation. Copy it immediately and share it yourself. This MVP does not send email. An administrator can revoke an unused invitation from the Team page.

Current team limitation: team creation and task-level team assignment are available, but a full many-to-many team membership editor is not part of this MVP.

## 9. Activity

Activity records key actions such as task creation, task edits, status changes, comments, project changes, member joins and invitation creation. It is a useful shared timeline, not a full immutable compliance audit system.

## 10. Task details and comments

Open a task from a list, board or calendar to see its metadata and description. The discussion area allows workspace members to add notes. Comments are stored on the server and appear to other members in the same workspace.

## 11. Account settings

A member can update their display name and sign out. Sign-out deletes the current server session and browser cookie. It does not delete workspace data. Email address changes and password resets are not available in this release.

## 12. Keyboard shortcuts

- `N`: open the new-task dialog (when focus is not inside a form field).
- `Ctrl + K` / `⌘ + K`: focus global search.
- `1` to `5`: navigate Overview, My tasks, All tasks, Board and Calendar.
- `Esc`: close open dialogs or dismiss the guided tour.

## 13. Server, database and safety

The FastAPI server serves both the SPA and its API. SQLite is created at `data/bottleneck.sqlite3` unless `BOTTLENECK_DB` points to another file. Passwords are stored using PBKDF2-SHA256 hashes. Session tokens are random values; only token hashes are stored in SQLite. The browser cookie is HttpOnly and SameSite=Lax.

For a trusted LAN, bind to `0.0.0.0` only when access from other devices is needed. For internet-facing use, deploy behind an HTTPS reverse proxy, set `BOTTLENECK_COOKIE_SECURE=1`, configure backups and rate limiting, and provide a secure account recovery path. Do not expose the development server as a production edge server.

## 14. Version history

### 0.2.1 · Windows launcher and dependency hotfix · 14 November 2026

- Uses Python 3.12 by default for a consistent local setup.
- Drops unused `uvicorn[standard]` extras to avoid unnecessary PyYAML/native compilation on Windows.
- Updates launch scripts and troubleshooting steps.

### 0.2.0 · Server-backed MVP · 14 November 2026

- Server-side account creation, authentication and session management.
- Workspace isolation and owner/admin/member roles.
- Seven-day invitation links with one-time acceptance.
- SQL persistence for tasks, projects, teams, comments and activity.
- Guided first-run tour and this handbook inside the app.
- Responsive Persian RTL workspace with dashboard, lists, Kanban, calendar and team pages.

### 0.1.0 · UI preview · 14 November 2026

- Initial Persian RTL front-end preview.
- Dashboard, tasks, Kanban, calendar, projects, team and activity layouts.
- Browser-only localStorage sample data and a preliminary SQL schema.

## 15. Current limitations

No automatic invitation email, password recovery, MFA, multiple workspace switching, team member assignment editor, attachments, task checklist, recurring tasks, dependencies, time tracking, push notifications, real-time collaboration or production deployment setup. These are future development candidates, not silently simulated features.
