# BottleNeck v0.6.0 — MVP Release

BottleNeck is a Persian-first, RTL team workspace built with FastAPI, SQLite, HTML, CSS and vanilla JavaScript. It combines task and project management, productivity tracking, shared concept boards, shared files/folders, Markdown notes, team chat, multi-workspace accounts, configurable workspace permissions, TOTP two-factor authentication and automated backups.

The desktop UI keeps the project's approximately 120% scale; narrow screens return to normal scale. The launcher binds to `0.0.0.0:1939` by default for trusted LAN access.

## 1. Requirements

- Windows 10/11, Linux or macOS.
- [uv](https://docs.astral.sh/uv/).
- Python 3.12 is installed/managed by uv during setup.
- For LAN use on Windows, set the network profile to **Private**.

The project deliberately uses plain `uvicorn` plus the pure-Python `websockets` package, not `uvicorn[standard]`; the WebSocket protocol is installed explicitly while PyYAML and Microsoft C++ Build Tools are not required by the launcher.

## 2. Start on Windows

1. Extract the ZIP.
2. Open PowerShell in the `bottleneck-mvp` folder.
3. Run:

   ```powershell
   .\start.ps1
   ```

The launcher runs `uv sync --python 3.12` and starts Uvicorn on `0.0.0.0:1939`.

- Host computer: `http://127.0.0.1:1939`
- Other devices on the same LAN: `http://<host-LAN-IP>:1939`
- API reference: `http://<host-LAN-IP>:1939/api/docs`

The launcher prints detected LAN URLs. They are also listed in **Settings → Local network access**. If Windows Firewall blocks other devices, set the network profile to Private and run `allow-lan-firewall.ps1` once from an elevated PowerShell window. The helper creates a TCP 1939 rule limited to the Private profile and local subnet.

## 3. Start on Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

Manual equivalent:

```bash
uv sync --python 3.12
uv run --python 3.12 uvicorn main:app --host 0.0.0.0 --port 1939
```

Stop the server with `Ctrl+C`. The host computer must remain on and the BottleNeck process must remain running for other devices to use the workspace.

## 4. First-run setup

1. Open BottleNeck on the host computer.
2. Register the first account and create the first workspace. That account becomes the initial installation owner.
3. Invite colleagues from **Teams and Members**. Invitation links are email-specific and expire after seven days. Share them manually unless you separately configure an email system.
4. Create teams and assign members to them.
5. Use the workspace selector in the top bar to switch between workspaces or create another workspace.
6. Use **Settings** to review account security, email preferences, role permissions and backup status.

A signed-in user can belong to more than one workspace. Workspace data is scoped to the active membership/session.

## 5. What is in v0.6.0

### Tasks and productivity

- Tasks, projects, teams, Kanban, calendar, multi-assignee tasks, comments, checklists and private task attachments (10 MB per task attachment).
- Dependencies with cycle validation and a completion guard while prerequisites remain open.
- Time tracking with one active timer per user, estimates versus tracked time and daily/weekly reports.
- Reusable task templates, recurring-task rules and task approval requests.
- Workspace-specific labels/colors for the five built-in task statuses.
- In-app notifications, activity history and team presence.

### Shared workspace

- Shared concept boards with movable sticky notes, plain-text cards, links and task links.
- Shared drive with nested folders, Markdown notes and file uploads (50 MB per shared file).
- Workspace-wide, team-only and password-protected sharing.
- Per-role read/write ACL settings for shared folders/files; parent-folder restrictions are inherited by descendants.
- XHR upload progress and authenticated, permission-checked file downloads.
- GFM Markdown preview (headings, lists, task lists, tables, links, quotes and fenced code) sanitized with DOMPurify.
- Workspace chat and team-specific chat channels.
- Authenticated WebSocket event stream for shared workspace updates. Presence refresh remains periodic (about 12 seconds).

### v0.6.0 administration and security

- Multiple workspaces per account, workspace creation and workspace switching.
- Configurable permission matrix for the `admin` and `member` roles. The workspace owner always has full access within their workspace.
- Shared-drive role-level read/write rules.
- TOTP two-factor authentication with ten single-use recovery codes. Each login challenge expires after five minutes and allows up to five failed code attempts.
- Password reset links expire after 30 minutes and are single-use. Public self-service email delivery requires SMTP. A workspace admin can also create a reset link for a member and share it manually over a trusted channel.
- Optional SMTP delivery for notification emails and password reset messages.
- Automatic backup scheduler (24-hour default interval; 14 retained copies by default) plus manual backup creation and download.
- Backups include the SQLite database, task uploads, shared files and a manifest. They are ZIP archives saved under `backups/`.
- Optional HTTPS directly through Uvicorn certificate/key settings in the launch scripts.
- Authenticated WebSocket connections are checked against the server-side session during the connection lifetime.

## 6. Multi-workspace roles and permissions

Each workspace has `owner`, `admin` and `member` memberships. The owner can configure the admin/member permission matrix in Settings. The owner has full permissions inside that workspace. Examples of configurable permissions include workspace management, member invitations/management, team management, report viewing, deleting tasks/projects and managing shared items.

The backup archive contains the database and files for the entire BottleNeck installation, not just one workspace. For this reason, backup listing, creation and download are restricted to the **initial installation owner** (the account that created the first workspace). A later workspace owner does not automatically become the instance-wide backup administrator.

## 7. Account security

### Two-factor authentication

In **Settings → Account security**:

1. Start TOTP setup.
2. Add the secret key or `otpauth` URI to an authenticator app.
3. Store the ten recovery codes somewhere safe. They are shown only during setup.
4. Enter the current six-digit TOTP code to enable two-factor authentication.

A recovery code is eight hexadecimal characters and can be used only once in place of a TOTP code. Keep the server's `data/` directory private; it contains the TOTP secret needed to verify sign-ins. If the authenticator is lost, use a recovery code. If both the authenticator and all recovery codes are lost, an administrator must perform an out-of-band account recovery; there is no self-service TOTP reset endpoint in this MVP.

### Password reset

The public **Forgot password** action sends a reset email only when SMTP is configured. The response does not reveal whether an email address exists. Reset links are single-use and expire after 30 minutes; completing a reset revokes that account's existing sessions.

If SMTP is not configured, the public form cannot deliver the link. A workspace admin can generate a member reset link from the member-management interface and give it to the person through a trusted channel. Do not paste reset links into public chats.

## 8. Email configuration (optional)

Set environment variables before running the launcher:

| Variable | Default | Description |
|---|---:|---|
| `BOTTLENECK_SMTP_HOST` | unset | SMTP server hostname |
| `BOTTLENECK_SMTP_PORT` | `587` | SMTP server port |
| `BOTTLENECK_SMTP_FROM` | unset | Sender address |
| `BOTTLENECK_SMTP_STARTTLS` | `1` | Use STARTTLS when `1` |
| `BOTTLENECK_SMTP_USER` | unset | Optional SMTP username |
| `BOTTLENECK_SMTP_PASSWORD` | unset | Optional SMTP password |

PowerShell example (replace values with your SMTP provider's settings):

```powershell
$env:BOTTLENECK_SMTP_HOST = "smtp.example.com"
$env:BOTTLENECK_SMTP_PORT = "587"
$env:BOTTLENECK_SMTP_FROM = "bottleneck@example.com"
$env:BOTTLENECK_SMTP_STARTTLS = "1"
$env:BOTTLENECK_SMTP_USER = "bottleneck@example.com"
$env:BOTTLENECK_SMTP_PASSWORD = "YOUR_SMTP_PASSWORD"
.\start.ps1
```

Users must enable email notifications in their own notification preferences. SMTP is used for the notification queue and public password-reset email. Verify sender authentication and delivery with your provider; BottleNeck does not include a mail-provider setup wizard.

## 9. HTTPS configuration (optional)

For a trusted LAN MVP, the launcher defaults to HTTP. To enable Uvicorn HTTPS, provide a certificate and private key before starting:

```powershell
$env:BOTTLENECK_SSL_CERTFILE = "C:\certs\bottleneck.crt"
$env:BOTTLENECK_SSL_KEYFILE = "C:\certs\bottleneck.key"
.\start.ps1
```

The launcher then enables secure session cookies. Use a certificate trusted by the devices that will connect. Do not use an untrusted self-signed certificate for public access. For a public release, use a properly maintained reverse proxy, a valid certificate, access controls, firewall rules and a security review; this package is not a hardened public-internet deployment by itself.

## 10. Backups and restore

Environment variables:

| Variable | Default | Description |
|---|---:|---|
| `BOTTLENECK_BACKUP_INTERVAL_HOURS` | `24` | Automatic backup interval (minimum 1 hour) |
| `BOTTLENECK_BACKUP_RETENTION` | `14` | Number of recent backups to retain (minimum 2) |
| `BOTTLENECK_BACKUP_DIR` | `./backups` | Backup archive directory |

Automatic backups begin after the first account exists. The initial installation owner can create a manual backup from Settings. Each ZIP includes:

```text
manifest.json
data/
├── bottleneck.sqlite3
├── uploads/          # task attachments
└── shared/           # shared-drive files
```

To restore:

1. Stop BottleNeck.
2. Copy the current `data/` folder and `backups/` folder somewhere safe before changing anything.
3. Extract the selected backup ZIP into the BottleNeck installation directory, allowing its `data/` paths to be restored.
4. Confirm the archive contains `data/bottleneck.sqlite3`, `data/uploads/` and `data/shared/` as appropriate.
5. Start BottleNeck and verify login, tasks and shared files.

Backups are stored on the same host by default. They are not automatically copied off-device or to cloud storage. Keep a separate off-device copy for disaster recovery. Stop the application before a manual folder-level restore.

## 11. Runtime data layout

```text
bottleneck-mvp/
├── main.py
├── index.html
├── schema.sql
├── static/
│   ├── app.js
│   └── styles.css
├── data/                         # created on first start
│   ├── bottleneck.sqlite3
│   ├── uploads/
│   └── shared/
└── backups/                      # created when first backup is made
```

SQLite uses WAL mode. The entire `data/` directory is operational data and must not be placed on a public static web path. Do not delete or replace it when installing a new release.

## 12. Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `BOTTLENECK_DB` | `./data/bottleneck.sqlite3` | SQLite database location |
| `BOTTLENECK_UPLOAD_DIR` | `./data/uploads` | Task attachment storage |
| `BOTTLENECK_SHARED_DIR` | `<DB parent>/shared` | Shared-drive file storage |
| `BOTTLENECK_BACKUP_DIR` | `./backups` | Backup ZIP location |
| `BOTTLENECK_SESSION_DAYS` | `14` | Session lifetime in days |
| `BOTTLENECK_COOKIE_SECURE` | `0` | Set automatically by launcher for HTTPS; `1` for secure cookies |
| `BOTTLENECK_HOST` | `0.0.0.0` | Uvicorn bind host |
| `BOTTLENECK_PORT` | `1939` | HTTP/HTTPS port |
| `BOTTLENECK_SSL_CERTFILE` | unset | Optional TLS certificate path |
| `BOTTLENECK_SSL_KEYFILE` | unset | Optional TLS private key path |

## 13. Useful endpoints

- `GET /api/health` — application/version health.
- `GET /api/bootstrap` — active workspace snapshot.
- `GET/POST /api/workspaces` and `POST /api/workspaces/switch` — workspace listing/creation/switching.
- `GET/PUT /api/permissions` — role permission matrix.
- `GET /api/security` — current account security status.
- `POST /api/security/totp/setup`, `/enable`, `/disable` — TOTP management.
- `POST /api/auth/password-reset/request` and `/complete` — password reset.
- `GET/POST /api/backups` — list/create instance backups (initial installation owner only).
- `GET /api/backups/{id}/download` — download a backup archive (initial installation owner only).
- `WS /ws` — authenticated workspace event stream.
- `GET /api/docs` — interactive API documentation.

## 14. Upgrade from v0.5.0

1. Stop the old server with `Ctrl+C`.
2. Make a separate copy of the complete `data/` directory, including uploads and shared files.
3. Extract v0.6.0 into a new directory.
4. Copy the old `data/` directory into the new `bottleneck-mvp/` directory.
5. Start with `start.ps1` or `start.sh`.

The v0.6 schema adds the security, multi-workspace permissions, recovery code, email queue and backup tables. Existing users, workspaces, tasks, projects, task assignments, time entries, boards, files, notes and chats remain in the database. The upgrade was integration-tested against a populated v0.5.0 schema. Do not run `schema.sql` manually against the live database; the application applies it on startup.

## 15. Known MVP limitations and security notes

- BottleNeck is designed for a trusted LAN/private network MVP. Do not expose port 1939 directly to the public internet or port-forward it on your router.
- HTTP is the default. Use HTTPS for any network where traffic cannot be trusted.
- Login password attempts and public password-reset requests do not have a configurable global IP rate limiter in this MVP. Use it on a trusted network and avoid publishing the login endpoint to the internet.
- TOTP secrets are stored in the host's SQLite database; protect the entire `data/` directory and host account.
- Email delivery depends on the SMTP provider and correct environment variables. No email verification or bounce-management system is included.
- Backups are local to the host unless an operator copies them elsewhere. Protect backup ZIPs: they contain the full database and private files.
- Shared files are not scanned for malware. Only allow trusted users to upload files and scan files externally if required by your organization.
- Shared file uploads have a 50 MB cap; task attachments have a 10 MB cap.
- Rich Markdown preview and some visual assets use external CDNs. Offline browsers retain the Markdown source but may not render a rich preview or remote fonts/icons.
- Simultaneous edits to the exact same note use last-write-wins behavior; there is no character-level collaborative editor or note revision history.
- WebSocket delivers workspace events. Presence still refreshes periodically, and updates require a live server connection.
- Task recurrence and report date boundaries use UTC. Workspace-specific time zones are not configurable.
- A browser-level automated walkthrough was not available in the build environment; release verification used API integration tests, database migration tests, Python/JavaScript syntax checks and archive integrity checks.

## Creator credit

The application includes a compact popup with **«ساخته شده با عشق توسط ژلوفن»**, Telegram `https://t.me/jelofen1962` and phone link `tel:+989109721962`.
