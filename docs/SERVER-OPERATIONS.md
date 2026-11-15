# Server operations

The server owner manages the installation as a whole. Workspace owners and admins manage only their own workspace; the two permission systems are separate.

## First run

`start.ps1` or `start.sh` runs `bottleneck_cli.py setup --if-needed` before Uvicorn starts. A fresh install asks for the initial server owner's name, email, password and primary workspace. On a migrated installation, the CLI uses the migration's owner mapping or asks the operator to verify an existing account before linking it.

## Common commands

Run these from the project directory:

```bash
uv run --python 3.12 python bottleneck_cli.py status
uv run --python 3.12 python bottleneck_cli.py doctor
uv run --python 3.12 python bottleneck_cli.py logs --lines 100
uv run --python 3.12 python bottleneck_cli.py backup
uv run --python 3.12 python bottleneck_cli.py users list
uv run --python 3.12 python bottleneck_cli.py workspaces list
uv run --python 3.12 python bottleneck_cli.py admin list
```

The `doctor` command checks SQLite integrity, foreign keys, owner configuration and write access to runtime directories.

## Server administrator roles

| Role | Scope |
|---|---|
| `owner` | Full installation administration. Created only by first-run setup or verified legacy migration. |
| `operator` | Day-to-day operations, diagnostics, backup creation and permitted data import/export. |
| `auditor` | Read-only installation inventory and audit information. |

Only the owner can grant or revoke server administrators. The owner cannot demote themselves through the regular role-management flow.

## Configuration

```bash
uv run --python 3.12 python bottleneck_cli.py config show
uv run --python 3.12 python bottleneck_cli.py config set bind_host 0.0.0.0
uv run --python 3.12 python bottleneck_cli.py config set bind_port 1939
uv run --python 3.12 python bottleneck_cli.py config set backup_interval_hours 24
uv run --python 3.12 python bottleneck_cli.py config set backup_retention 14
```

Host and port changes apply after a restart. The default deployment binds to all interfaces on port 1939 for a trusted LAN; a reverse-proxy deployment should bind Uvicorn to `127.0.0.1`.

## Backup and restore

Create a full backup:

```bash
uv run --python 3.12 python bottleneck_cli.py backup
```

Restore requires the server to be stopped:

```bash
uv run --python 3.12 python bottleneck_cli.py restore-backup \
  --input ./backups/bottleneck-backup-example.zip \
  --confirm-offline --yes
```

The restore command validates the archive and database before replacing files, creates a pre-restore copy when possible, and keeps rollback files if replacement fails. Restore a copy of the archive during maintenance rehearsals; don't wait for a disk failure to discover that a backup is incomplete.

## Selective import and export

```bash
uv run --python 3.12 python bottleneck_cli.py export workspace \
  --workspace "Workspace Name" --output ./workspace-export.zip

uv run --python 3.12 python bottleneck_cli.py import workspace \
  --input ./workspace-export.zip
```

Tasks and projects can also move as CSV files. Workspace imports create a new workspace and regenerate resource IDs; the import does not create user accounts or carry passwords and sessions. Unknown member references map to the importing owner account. Review the imported workspace before inviting its members.
