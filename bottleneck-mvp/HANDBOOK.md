# BottleNeck user handbook – v0.4.0

BottleNeck is a Persian RTL workspace for planning tasks, coordinating teams and reviewing actual work. The host machine stores the SQLite database and uploaded files. Teammates on the same trusted LAN open the host's IP address on port 1939.

## 1. First login and workspace

The first registered account becomes the owner and creates the workspace. Use **تیم‌ها و اعضا** to create teams and invite colleagues. Invitations are manually shared, email-specific and valid for seven days. The invited person must register with the invited email.

## 2. Dashboard and task views

- **نمای کلی:** current workload, overdue tasks, progress, latest activity and member workload.
- **کارهای من:** tasks where your account is assigned.
- **همه کارها:** the workspace task table with status/team filters.
- **برد کانبان:** drag a task card to another workflow column. The status change is persisted on the server.
- **تقویم:** tasks with due dates, in a Saturday-first calendar.

Use `N` to open the new-task form. Use `Ctrl + K` to focus global search.

## 3. Task details

A task may have multiple assignees, a team, project, priority, due date and estimated hours. Open a task to manage its checklist, private attachments and discussion.

### Checklists

Add a short action item, check it when finished, reopen it if needed, or remove it. The checklist completion count is visible in task lists and on Kanban cards.

### Attachments

Upload PDF, common images, Office documents, CSV, TXT or ZIP files. Maximum size is 10 MB per file. Files are stored outside the static web directory and downloads require a valid session and membership in the same workspace. Admins can remove any attachment; members can remove files they uploaded.

### Time tracking

Open task details and select **شروع زمان‌سنج** when you begin working. Select **توقف زمان‌سنج** when you finish. Each user can have one active timer in the workspace at a time. A timer belongs to the user and task that started it. Stopping it stores the duration and adds an activity event. Reports aggregate finished and currently active entries.

A timer is not stopped automatically when a browser is closed. Reopen the task or active timer's task and stop the timer when the work session ends.

### Dependencies

In task details, select the prerequisite tasks and save. A task cannot be marked complete until every prerequisite is complete. The server rejects self-dependencies, cross-workspace IDs and dependency cycles. Remove dependencies by saving an empty selection.

### Approval workflow

When the output is ready, select **ارسال برای تأیید**. The task enters the review state and creates a pending approval request. Owners and admins can approve or reject it. Approval marks the task complete, provided its prerequisites are complete. Rejection returns it to in-progress and stores an optional review comment. The **درخواست‌های تأیید** page lists pending requests.

## 4. Projects and teams

Projects group tasks around a result. Teams represent department/group membership. Team membership does not automatically assign every team member to its tasks. Select task assignees explicitly.

## 5. Task templates

Open **قالب‌های کار**. Owners and admins can create a template with a template name, default task title and description, priority, estimate, project/team, default assignees and checklist items. Any member can use an existing template to create a new task. The task and its checklist are copied; later edits to the task do not change the template.

## 6. Recurring tasks

Open **کارهای تکرارشونده**. Owners and admins can create rules with:

- Daily, weekly or monthly cadence.
- An interval (for example every 2 weeks).
- First execution date.
- Optional due-date offset.
- Default project and assignees.

The server checks active rules when someone opens the workspace. Due instances are created as new tasks. Up to 24 missed occurrences per rule are generated in one pass; any remaining missed instances are caught up on later workspace loads. The server must be running and someone must access the workspace. There is no independent background scheduler in this MVP. Pausing a rule stops new task generation without deleting already-created tasks.

## 7. Reports

Open **گزارش‌های عملکرد** and choose daily or weekly. Reports show tasks created, tasks completed, currently overdue/open task counts and time tracked. Work time is grouped by member and project. The weekly range is Saturday through Friday. Date boundaries are calculated in UTC, not a configurable local timezone.

## 8. Status labels

Owners and admins can change the displayed label and color for the five built-in statuses in **تنظیمات → نام‌گذاری وضعیت‌ها**. The underlying status keys and number of workflow states remain fixed in this version so task records and Kanban logic remain stable.

## 9. Teams, invitations and permissions

- **Owner:** full workspace administration.
- **Admin:** can administer teams, invitations, recurring rules, templates, status labels and approvals.
- **Member:** can work with tasks, comments, checklists, attachments, time tracking, dependencies, template-based task creation and approval requests.

Team membership is configured from the **تیم‌ها و اعضا** section. The member list is shared across the workspace.

## 10. Notifications and synchronization

Notifications are shown behind the bell icon. The app polls the workspace event feed every 3.5 seconds and refreshes the workspace snapshot when another team member changes data. This is near-real-time polling, not WebSocket push. Email and browser push notifications are not included.

## 11. LAN access

The server binds to `0.0.0.0:1939`. The host uses `http://127.0.0.1:1939`; other LAN devices use the host's IPv4 address. The launcher and Settings page display detected addresses. If necessary, set Windows network profile to Private and allow inbound TCP 1939 for the local subnet with the included firewall helper. Do not add router port forwarding or expose the development server to the public internet.

## 12. Upgrade and backup

Before upgrading, stop BottleNeck and copy the entire `data/` folder. The v0.4 startup creates the new productivity tables and initializes status labels for existing workspaces. Existing task/user/project/collaboration records are preserved. Keep both `bottleneck.sqlite3` and `uploads/` together.

## 13. Creator credit

The app includes a small creator popup with the signature «ساخته شده با عشق توسط ژلوفن», Telegram `https://t.me/jelofen1962` and phone link `tel:+989109721962`.

## 14. Version history

### v0.4.0

Time tracking, daily/weekly reports, recurring rules, task templates, dependencies, approval workflow, editable status labels and 120% desktop UI scale.

### v0.3.0

Multi-assignee tasks, checklists, private attachments, notifications, team membership editor, LAN port 1939, guided tour and creator popup.

### v0.2.1

Windows dependency resolution fix using Python 3.12 and lean Uvicorn installation.

### v0.2.0

Server-side account foundation, SQLite workspace, task/project management and activity logging.

## 15. Current limitations

No password reset, two-factor authentication, email delivery, multiple workspaces per account, WebSocket push, external scheduler, configurable workflow-state count, time zone setting, report exports or file virus scanning. Use BottleNeck only on a trusted LAN and back up `data/` regularly.
