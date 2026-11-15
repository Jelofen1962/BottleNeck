#!/usr/bin/env python3
"""BottleNeck instance operations CLI (v1.0.0).

Run through uv, for example: uv run python bottleneck_cli.py --help
"""
from __future__ import annotations

import argparse
import csv
import getpass
import io
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import main


def out(label: str, value: object = "") -> None:
    print(f"{label}{value}")


def resolve_workspace(value: str) -> dict:
    with main.db() as conn:
        row = conn.execute("SELECT id,name,created_at FROM workspaces WHERE id=?", (value,)).fetchone()
        if not row:
            row = conn.execute("SELECT id,name,created_at FROM workspaces WHERE name=? COLLATE NOCASE ORDER BY created_at LIMIT 1", (value,)).fetchone()
    if not row:
        raise SystemExit(f"Workspace not found: {value}")
    return dict(row)


def current_server_owner_id() -> str:
    with main.db() as conn:
        row = conn.execute("SELECT user_id FROM server_admins WHERE enabled=1 AND role='owner' ORDER BY created_at LIMIT 1").fetchone()
    if not row:
        raise SystemExit("No server owner is configured. Run: uv run python bottleneck_cli.py setup")
    return row["user_id"]


def create_owner_account() -> None:
    print("\nBottleNeck first-run server owner setup")
    print("This account controls the entire installation, not just one workspace.\n")
    name = input("Server owner's display name: ").strip()
    while len(name) < 2:
        name = input("Name must contain at least 2 characters: ").strip()
    email = input("Server owner's email: ").strip().lower()
    while not main.re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        email = input("Enter a valid email address: ").strip().lower()
    with main.db() as conn:
        exists = conn.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
    if exists:
        raise SystemExit("That email already has an account. Sign in to the existing account and run setup with that account, or use the interactive link-existing-account flow described in README.md.")
    password = getpass.getpass("Create a password (at least 8 characters): ")
    while len(password) < 8:
        password = getpass.getpass("Password must contain at least 8 characters: ")
    confirm = getpass.getpass("Confirm password: ")
    while confirm != password:
        print("Passwords do not match.")
        password = getpass.getpass("Create a password: ")
        confirm = getpass.getpass("Confirm password: ")
    workspace_name = input("Primary workspace name [فضای کاری اصلی]: ").strip() or "فضای کاری اصلی"
    user_id, workspace_id, stamp = main.new_id(), main.new_id(), main.now_iso()
    with main.db() as conn:
        conn.execute("INSERT INTO users(id,name,email,password_hash,created_at) VALUES(?,?,?,?,?)",
                     (user_id, name, email, main.password_hash(password), stamp))
        conn.execute("INSERT OR IGNORE INTO notification_preferences(user_id,updated_at) VALUES(?,?)", (user_id, stamp))
        conn.execute("INSERT INTO workspaces(id,name,created_by,created_at) VALUES(?,?,?,?)",
                     (workspace_id, workspace_name, user_id, stamp))
        conn.execute("INSERT INTO memberships(id,workspace_id,user_id,role,joined_at) VALUES(?,?,?,?,?)",
                     (main.new_id(), workspace_id, user_id, "owner", stamp))
        main._create_workspace_defaults(conn, workspace_id, user_id)
        conn.execute("INSERT INTO server_admins(user_id,role,enabled,created_by,created_at) VALUES(?,'owner',1,?,?)",
                     (user_id, user_id, stamp))
        conn.execute("UPDATE server_instance SET owner_user_id=?,initialized_at=?,version=? WHERE id=1",
                     (user_id, stamp, main.APP_VERSION))
        main.server_audit(conn, user_id, "server.install.owner_created", email, {"workspace": workspace_name})
    out("\nServer owner created: ", email)
    out("Primary workspace: ", workspace_name)


def link_existing_owner() -> None:
    print("\nLink an existing BottleNeck account as the server owner.")
    email = input("Account email: ").strip().lower()
    password = getpass.getpass("Account password: ")
    with main.db() as conn:
        user = conn.execute("SELECT id,email,password_hash FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        if not user or not main.verify_password(password, user["password_hash"]):
            raise SystemExit("Account not found or password is incorrect.")
        if conn.execute("SELECT 1 FROM server_admins WHERE role='owner' AND enabled=1").fetchone():
            raise SystemExit("A server owner is already configured.")
        stamp = main.now_iso()
        conn.execute("INSERT INTO server_admins(user_id,role,enabled,created_by,created_at) VALUES(?,'owner',1,?,?)",
                     (user["id"], user["id"], stamp))
        conn.execute("UPDATE server_instance SET owner_user_id=?,initialized_at=?,version=? WHERE id=1",
                     (user["id"], stamp, main.APP_VERSION))
        main.server_audit(conn, user["id"], "server.install.owner_linked", email, {})
    out("Server owner linked to existing account: ", email)


def cmd_setup(args) -> None:
    main.init_db()
    with main.db() as conn:
        owner = conn.execute("SELECT u.email FROM server_admins sa JOIN users u ON u.id=sa.user_id WHERE sa.role='owner' AND sa.enabled=1 LIMIT 1").fetchone()
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        workspace_count = conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
    if owner:
        out("BottleNeck server owner is already configured: ", owner["email"])
        return
    if user_count:
        # For legacy installs, migration should already have promoted the first workspace creator.
        # If the installation has users but no workspace owner, require an explicit credential check.
        link_existing_owner()
    else:
        create_owner_account()
    out("\nSetup complete. Start BottleNeck with: uv run python bottleneck_cli.py serve")


def cmd_serve(args) -> None:
    main.init_db()
    with main.db() as conn:
        owner = conn.execute("SELECT 1 FROM server_admins WHERE role='owner' AND enabled=1").fetchone()
    if not owner:
        raise SystemExit("Server owner setup is required. Run: uv run python bottleneck_cli.py setup")
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("Uvicorn is not installed. Run: uv sync") from exc
    host = args.host or os.getenv("BOTTLENECK_HOST") or main._server_setting("bind_host", "0.0.0.0")
    port = args.port or int(os.getenv("BOTTLENECK_PORT") or main._server_setting("bind_port", "1939"))
    cert = os.getenv("BOTTLENECK_SSL_CERTFILE") or None
    key = os.getenv("BOTTLENECK_SSL_KEYFILE") or None
    if bool(cert) != bool(key):
        raise SystemExit("Set both BOTTLENECK_SSL_CERTFILE and BOTTLENECK_SSL_KEYFILE for HTTPS.")
    scheme = 'https' if cert else 'http'
    print(f"\nBottleNeck v{main.APP_VERSION} listening on {host}:{port}")
    print(f"Local URL: {scheme}://127.0.0.1:{port}")
    if host in {"0.0.0.0", "::"}:
        ips = main.discover_lan_ips()
        if ips:
            print("LAN URLs:")
            for ip in ips:
                print(f"  {scheme}://{ip}:{port}")
    print("\nStop the server with Ctrl+C. This CLI does not daemonize or hide the process.")
    _server_logger = main._server_logger
    _server_logger.info("server_start host=%s port=%s https=%s", host, port, bool(cert))
    uvicorn.run("main:app", host=host, port=port, ssl_certfile=cert, ssl_keyfile=key, log_level="info")


def cmd_status(args) -> None:
    main.init_db()
    info = main._server_overview()
    print("BottleNeck server status")
    for key, label in [("version","Version"),("status","Health"),("databaseIntegrity","Database integrity"),("databasePath","Database path"),
                       ("users","Accounts"),("workspaces","Workspaces"),("activeSessions","Active sessions"),("serverAdmins","Server administrators"),
                       ("backups","Backups"),("databaseBytes","Database bytes"),("dataBytes","Data bytes"),("freeBytes","Free disk bytes"),("uptimeSeconds","Process uptime seconds")]:
        out(f"{label:26}: ", info.get(key))


def cmd_doctor(args) -> None:
    main.init_db()
    checks = []
    with main.db() as conn:
        checks.append(("SQLite integrity", conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", conn.execute("PRAGMA integrity_check").fetchone()[0]))
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        checks.append(("Foreign key check", not fk, f"{len(fk)} violations"))
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        checks.append(("Server operations schema", {"server_instance","server_admins","server_settings","server_audit_logs"}.issubset(tables), "required tables present"))
        owner = conn.execute("SELECT COUNT(*) FROM server_admins WHERE role='owner' AND enabled=1").fetchone()[0]
        checks.append(("Server owner configured", owner == 1, f"{owner} active owner(s)"))
    for path, label in [(main.DB_PATH.parent,"Database directory"),(main.BACKUP_DIR,"Backup directory"),(main.UPLOAD_DIR,"Upload directory"),(main.SHARED_DIR,"Shared files directory"),(main.CHAT_DIR,"Chat files directory"),(main.SERVER_LOG_DIR,"Server logs directory")]:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".bottleneck-write-test"
            probe.write_text("ok", encoding="utf-8"); probe.unlink()
            checks.append((label, True, str(path)))
        except OSError as exc:
            checks.append((label, False, str(exc)))
    failed = 0
    for label, ok, detail in checks:
        print(f"{'[OK]  ' if ok else '[FAIL]'} {label}: {detail}")
        failed += not ok
    if failed: raise SystemExit(2)
    print("All diagnostics passed.")


def cmd_logs(args) -> None:
    main.init_db()
    with main.db() as conn:
        rows = conn.execute("""SELECT l.created_at,l.action,l.target,l.details_json,u.email FROM server_audit_logs l
            LEFT JOIN users u ON u.id=l.actor_user_id ORDER BY l.id DESC LIMIT ?""", (max(1,min(args.lines,500)),)).fetchall()
    if rows:
        print("Database audit events:")
        for row in reversed(rows):
            print(f"{row['created_at']}  {row['action']}  actor={row['email'] or 'cli'}  target={row['target']}  {row['details_json']}")
    else:
        print("No server audit events yet.")
    if main.SERVER_LOG_PATH.exists():
        print("\nOperational server log:")
        for line in main.SERVER_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1,min(args.lines,500)):]:
            print(line)


def cmd_backup(args) -> None:
    main.init_db()
    result = main._build_backup(None, False)
    with main.db() as conn: main.server_audit(conn, None, "cli.backup.create", result["filename"], {"bytes": result["sizeBytes"]})
    out("Backup created: ", main.BACKUP_DIR / result["filename"])
    out("Size: ", f"{result['sizeBytes']:,} bytes")


def export_csv(workspace_id: str, kind: str, output: Path) -> None:
    with main.db() as conn:
        if kind == "tasks":
            rows = conn.execute("""SELECT t.id,t.title,t.description,t.status,t.priority,t.due_date,t.estimate,
                COALESCE(p.name,'') AS project,COALESCE(tm.name,'') AS team,
                COALESCE((SELECT GROUP_CONCAT(u.email,';') FROM task_assignees ta JOIN users u ON u.id=ta.user_id WHERE ta.task_id=t.id),'') AS assignee_emails
                FROM tasks t LEFT JOIN projects p ON p.id=t.project_id LEFT JOIN teams tm ON tm.id=t.team_id WHERE t.workspace_id=? ORDER BY t.created_at DESC""", (workspace_id,)).fetchall()
            fields = ["id","title","description","status","priority","due_date","estimate","project","team","assignee_emails"]
        else:
            rows = conn.execute("SELECT name,description,color,status FROM projects WHERE workspace_id=? ORDER BY name", (workspace_id,)).fetchall()
            fields = ["name","description","color","status"]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows([dict(r) for r in rows])
    out(f"Exported {len(rows)} {kind}: ", output)


def cmd_export(args) -> None:
    main.init_db(); workspace = resolve_workspace(args.workspace)
    if args.kind == "workspace":
        manifest = main.build_workspace_export(workspace["id"], args.output)
        with main.db() as conn: main.server_audit(conn, None, "cli.workspace.export", workspace["id"], {"output": str(args.output)})
        out("Workspace package exported: ", args.output)
        out("Included tables: ", ", ".join(manifest["tables"]))
    else:
        export_csv(workspace["id"], args.kind, args.output)


def cmd_import(args) -> None:
    main.init_db()
    if args.kind == "workspace":
        owner_id = current_server_owner_id()
        result = main.import_workspace_package(args.input.read_bytes(), {"user_id": owner_id})
        out("Imported workspace: ", result["workspaceName"])
        out("New workspace ID: ", result["workspaceId"])
        return
    if not args.workspace:
        raise SystemExit("--workspace is required for task/project CSV imports.")
    workspace = resolve_workspace(args.workspace)
    owner_id = current_server_owner_id(); stamp = main.now_iso()
    with args.input.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        with main.db() as conn:
            if args.kind == "tasks":
                if not reader.fieldnames or "title" not in reader.fieldnames: raise SystemExit("CSV must contain a 'title' column.")
                created = skipped = 0
                for item in reader:
                    title = (item.get("title") or "").strip()
                    if len(title) < 2: skipped += 1; continue
                    status = item.get("status") or "todo"; priority = item.get("priority") or "medium"
                    if status not in main.STATUSES: status="todo"
                    if priority not in main.PRIORITIES: priority="medium"
                    team = conn.execute("SELECT id FROM teams WHERE workspace_id=? AND name=? COLLATE NOCASE", (workspace["id"],(item.get("team") or "").strip())).fetchone() if item.get("team") else None
                    project = conn.execute("SELECT id FROM projects WHERE workspace_id=? AND name=? COLLATE NOCASE", (workspace["id"],(item.get("project") or "").strip())).fetchone() if item.get("project") else None
                    task_id=main.new_id(); due=(item.get("due_date") or "").strip() or None
                    if due and not main.re.fullmatch(r"\d{4}-\d{2}-\d{2}",due): due=None
                    try: estimate=float(item.get("estimate")) if item.get("estimate") else None
                    except ValueError: estimate=None
                    conn.execute("INSERT INTO tasks(id,workspace_id,title,description,status,priority,team_id,project_id,due_date,estimate,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (task_id,workspace["id"],title,(item.get("description") or "")[:12000],status,priority,team["id"] if team else None,project["id"] if project else None,due,estimate,owner_id,stamp,stamp))
                    for email in (item.get("assignee_emails") or "").split(";"):
                        member=conn.execute("SELECT u.id FROM users u JOIN memberships m ON m.user_id=u.id WHERE m.workspace_id=? AND u.email=? COLLATE NOCASE",(workspace["id"],email.strip())).fetchone() if email.strip() else None
                        if member: conn.execute("INSERT OR IGNORE INTO task_assignees(task_id,user_id,assigned_by,created_at) VALUES(?,?,?,?)",(task_id,member["id"],owner_id,stamp))
                    created+=1
                main.server_audit(conn,None,"cli.tasks.import",workspace["id"],{"created":created,"skipped":skipped})
                out("Tasks created: ", created); out("Rows skipped: ", skipped)
            else:
                if not reader.fieldnames or "name" not in reader.fieldnames: raise SystemExit("CSV must contain a 'name' column.")
                created=updated=skipped=0
                for item in reader:
                    name=(item.get("name") or "").strip()
                    if len(name)<2: skipped+=1; continue
                    status=item.get("status") or "active"
                    if status not in {"active","completed","archived"}: status="active"
                    old=conn.execute("SELECT id FROM projects WHERE workspace_id=? AND name=? COLLATE NOCASE",(workspace["id"],name)).fetchone()
                    if old:
                        conn.execute("UPDATE projects SET description=?,color=?,status=?,updated_at=? WHERE id=?",((item.get("description") or "")[:4000],(item.get("color") or "rust")[:32],status,stamp,old["id"])); updated+=1
                    else:
                        conn.execute("INSERT INTO projects(id,workspace_id,name,description,color,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",(main.new_id(),workspace["id"],name,(item.get("description") or "")[:4000],(item.get("color") or "rust")[:32],status,owner_id,stamp,stamp)); created+=1
                main.server_audit(conn,None,"cli.projects.import",workspace["id"],{"created":created,"updated":updated,"skipped":skipped})
                out("Projects created: ", created); out("Projects updated: ", updated); out("Rows skipped: ", skipped)


def cmd_restore(args) -> None:
    if not args.confirm_offline or not args.yes:
        raise SystemExit("Restore requires --confirm-offline and --yes. Stop BottleNeck first and back up the current data directory.")
    # Read persisted bind settings without initializing or mutating the database first.
    port_value = os.getenv("BOTTLENECK_PORT")
    host_value = os.getenv("BOTTLENECK_HOST")
    if main.DB_PATH.exists():
        try:
            probe = sqlite3.connect(main.DB_PATH)
            if not port_value:
                setting = probe.execute("SELECT setting_value FROM server_settings WHERE setting_key='bind_port'").fetchone()
                port_value = setting[0] if setting else None
            if not host_value:
                setting = probe.execute("SELECT setting_value FROM server_settings WHERE setting_key='bind_host'").fetchone()
                host_value = setting[0] if setting else None
            probe.close()
        except sqlite3.Error:
            pass
    port = int(port_value or "1939")
    configured_host = host_value or "0.0.0.0"
    check_hosts = {"127.0.0.1", "::1"}
    if configured_host not in {"0.0.0.0", "::", "localhost"}:
        check_hosts.add(configured_host)
    ports_to_check = sorted({port, 1939})
    for check_host in sorted(check_hosts):
        family = socket.AF_INET6 if ":" in check_host else socket.AF_INET
        for check_port in ports_to_check:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.4)
                try:
                    listening = sock.connect_ex((check_host, check_port)) == 0
                except OSError:
                    listening = False
                if listening:
                    raise SystemExit(f"A service is listening on {check_host}:{check_port}. Stop BottleNeck before restoring.")
    main.init_db()
    if not args.input.is_file(): raise SystemExit("Backup archive not found.")
    try:
        with zipfile.ZipFile(args.input) as zf:
            infos = zf.infolist()
            total = sum(x.file_size for x in infos)
            if total > 8 * 1024 * 1024 * 1024: raise ValueError("archive too large")
            for info in infos:
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts: raise ValueError("unsafe archive path")
                if info.filename != "manifest.json" and not (info.filename == "data/bottleneck.sqlite3" or info.filename.startswith(("data/uploads/","data/shared/","data/chat_uploads/"))):
                    raise ValueError(f"unexpected archive member: {info.filename}")
            manifest = json.loads(zf.read("manifest.json"))
            if manifest.get("application") != "BottleNeck" or not any(x.filename == "data/bottleneck.sqlite3" for x in infos):
                raise ValueError("invalid BottleNeck backup")
            bad = zf.testzip()
            if bad: raise ValueError(f"checksum failed: {bad}")
            with tempfile.TemporaryDirectory(prefix="bottleneck-restore-") as tmp:
                stage = Path(tmp)
                for info in infos:
                    if info.is_dir(): continue
                    dest = stage.joinpath(*PurePosixPath(info.filename).parts)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, dest.open("wb") as out_file: shutil.copyfileobj(src, out_file)
                candidate = stage / "data" / "bottleneck.sqlite3"
                check = sqlite3.connect(candidate)
                try:
                    integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
                    fk = check.execute("PRAGMA foreign_key_check").fetchall()
                finally: check.close()
                if integrity != "ok" or fk: raise ValueError("database integrity check failed")
                # Create a pre-restore backup if a current database exists.
                if main.DB_PATH.exists():
                    try: main._build_backup(None, False)
                    except Exception as exc: raise SystemExit(f"Could not create pre-restore backup: {exc}")
                rollback = stage / "rollback"; rollback.mkdir()
                targets = [(candidate, main.DB_PATH)]
                folder_pairs = [(stage / "data" / "uploads", main.UPLOAD_DIR),(stage / "data" / "shared", main.SHARED_DIR),(stage / "data" / "chat_uploads", main.CHAT_DIR)]
                for folder, target in folder_pairs:
                    if folder.exists(): targets.append((folder,target))
                moved=[]
                try:
                    for idx,(source,target) in enumerate(targets):
                        target.parent.mkdir(parents=True,exist_ok=True)
                        if target == main.DB_PATH:
                            Path(str(target) + "-wal").unlink(missing_ok=True)
                            Path(str(target) + "-shm").unlink(missing_ok=True)
                        old = rollback / f"old-{idx}"
                        if target.exists(): target.replace(old); moved.append((old,target))
                        shutil.copytree(source,target) if source.is_dir() else shutil.copy2(source,target)
                except Exception:
                    for _,target in reversed(targets):
                        if target.is_dir(): shutil.rmtree(target,ignore_errors=True)
                        elif target.exists(): target.unlink(missing_ok=True)
                    for old,target in reversed(moved):
                        if old.exists(): old.replace(target)
                    raise
    except SystemExit: raise
    except Exception as exc: raise SystemExit(f"Restore failed safely: {exc}") from exc
    out("Backup restored successfully: ", args.input)
    out("Start BottleNeck again with: ", "uv run python bottleneck_cli.py serve")



def cmd_config_show(args) -> None:
    main.init_db()
    print("BottleNeck server configuration")
    rows = {
        "bind_host": main._server_setting("bind_host", "0.0.0.0"),
        "bind_port": main._server_setting("bind_port", "1939"),
        "backup_interval_hours": main._server_setting("backup_interval_hours", "24"),
        "backup_retention": main._server_setting("backup_retention", "14"),
    }
    for key, value in rows.items(): print(f"{key:24} {value}")
    print("Note: bind host and port changes apply after the next server restart.")


def cmd_config_set(args) -> None:
    main.init_db()
    allowed = {"bind_host", "bind_port", "backup_interval_hours", "backup_retention"}
    if args.key not in allowed: raise SystemExit(f"Unsupported setting: {args.key}")
    value = args.value.strip()
    if args.key == "bind_host":
        try: main.ipaddress.ip_address(value)
        except ValueError:
            if value != "localhost": raise SystemExit("bind_host must be a valid IP address or localhost")
    elif args.key == "bind_port":
        try: number = int(value)
        except ValueError: raise SystemExit("bind_port must be an integer")
        if not 1024 <= number <= 65535: raise SystemExit("bind_port must be between 1024 and 65535")
        value = str(number)
    elif args.key == "backup_interval_hours":
        number = int(value)
        if not 1 <= number <= 720: raise SystemExit("backup interval must be between 1 and 720 hours")
        value = str(number)
    elif args.key == "backup_retention":
        number = int(value)
        if not 2 <= number <= 100: raise SystemExit("backup retention must be between 2 and 100")
        value = str(number)
    stamp = main.now_iso()
    with main.db() as conn:
        conn.execute("INSERT INTO server_settings(setting_key,setting_value,updated_at) VALUES(?,?,?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,updated_at=excluded.updated_at",
                     (args.key, value, stamp))
        main.server_audit(conn, None, "cli.config.set", args.key, {"value": value})
    out(f"Saved {args.key}: ", value)
    if args.key in {"bind_host", "bind_port"}: print("Restart BottleNeck for this setting to take effect.")


def cmd_admin_list(args) -> None:
    main.init_db()
    with main.db() as conn:
        rows = conn.execute("""SELECT u.name,u.email,sa.role,sa.enabled,sa.created_at FROM server_admins sa
            JOIN users u ON u.id=sa.user_id ORDER BY CASE sa.role WHEN 'owner' THEN 0 WHEN 'operator' THEN 1 ELSE 2 END,u.name""").fetchall()
    if not rows: print("No server administrators configured."); return
    print(f"{'ROLE':10} {'ENABLED':8} {'NAME':24} EMAIL")
    for r in rows: print(f"{r['role']:10} {str(bool(r['enabled'])):8} {r['name'][:23]:24} {r['email']}")


def cmd_admin_grant(args) -> None:
    main.init_db()
    email = main.valid_email(args.email)
    if args.role not in {"operator", "auditor"}: raise SystemExit("Server admin role must be operator or auditor; owner is assigned only during installation.")
    with main.db() as conn:
        target = conn.execute("SELECT id,email FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        if not target: raise SystemExit("User account not found. They must register in BottleNeck first.")
        existing = conn.execute("SELECT role FROM server_admins WHERE user_id=? AND enabled=1", (target["id"],)).fetchone()
        if existing and existing["role"] == "owner": raise SystemExit("The installation owner cannot be demoted to operator/auditor.")
        conn.execute("INSERT INTO server_admins(user_id,role,enabled,created_by,created_at) VALUES(?,?,1,?,?) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,enabled=1,created_by=excluded.created_by",
                     (target["id"], args.role, current_server_owner_id(), main.now_iso()))
        main.server_audit(conn, current_server_owner_id(), "cli.server_admin.grant", email, {"role": args.role})
    out("Granted server role: ", f"{args.role} to {email}")


def cmd_admin_revoke(args) -> None:
    main.init_db(); email=main.valid_email(args.email)
    with main.db() as conn:
        target=conn.execute("SELECT sa.user_id,sa.role FROM server_admins sa JOIN users u ON u.id=sa.user_id WHERE u.email=? COLLATE NOCASE",(email,)).fetchone()
        if not target: raise SystemExit("Server administrator not found.")
        if target["role"] == "owner": raise SystemExit("The installation owner cannot be revoked by this command. Use an explicit recovery/transfer process.")
        conn.execute("DELETE FROM server_admins WHERE user_id=?",(target["user_id"],))
        main.server_audit(conn,current_server_owner_id(),"cli.server_admin.revoke",email,{})
    out("Revoked server administration for: ", email)


def cmd_users_list(args) -> None:
    main.init_db()
    with main.db() as conn:
        rows=conn.execute("SELECT u.name,u.email,u.created_at,(SELECT COUNT(*) FROM memberships m WHERE m.user_id=u.id) AS workspaces FROM users u ORDER BY u.created_at DESC LIMIT 500").fetchall()
    print(f"{'NAME':24} {'WORKSPACES':12} EMAIL")
    for r in rows: print(f"{r['name'][:23]:24} {r['workspaces']:<12} {r['email']}")


def cmd_workspaces_list(args) -> None:
    main.init_db()
    with main.db() as conn:
        rows=conn.execute("SELECT w.id,w.name,u.email,(SELECT COUNT(*) FROM memberships m WHERE m.workspace_id=w.id) AS members,(SELECT COUNT(*) FROM tasks t WHERE t.workspace_id=w.id) AS tasks FROM workspaces w JOIN users u ON u.id=w.created_by ORDER BY w.created_at DESC").fetchall()
    print(f"{'NAME':28} {'MEMBERS':9} {'TASKS':8} ID")
    for r in rows: print(f"{r['name'][:27]:28} {r['members']:<9} {r['tasks']:<8} {r['id']}")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bottleneck", description="BottleNeck server operations CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("setup", help="First-run server owner setup")
    setup.add_argument("--if-needed", action="store_true", help="Only run setup if no server owner exists")
    setup.set_defaults(func=cmd_setup)
    serve = sub.add_parser("serve", help="Run the BottleNeck web server")
    serve.add_argument("--host", default=None); serve.add_argument("--port", type=int, default=None); serve.set_defaults(func=cmd_serve)
    status = sub.add_parser("status", help="Show server status and storage metrics"); status.set_defaults(func=cmd_status)
    doctor = sub.add_parser("doctor", help="Run database and filesystem diagnostics"); doctor.set_defaults(func=cmd_doctor)
    logs = sub.add_parser("logs", help="Show server audit history"); logs.add_argument("--lines", type=int, default=80); logs.set_defaults(func=cmd_logs)
    backup = sub.add_parser("backup", help="Create a full database and files backup"); backup.set_defaults(func=cmd_backup)
    export = sub.add_parser("export", help="Export a workspace or selected data")
    export.add_argument("kind", choices=["workspace","tasks","projects"]); export.add_argument("--workspace", required=True); export.add_argument("--output", type=Path, required=True); export.set_defaults(func=cmd_export)
    imp = sub.add_parser("import", help="Import a workspace package or selected CSV data")
    imp.add_argument("kind", choices=["workspace","tasks","projects"]); imp.add_argument("--workspace", required=False); imp.add_argument("--input", type=Path, required=True); imp.set_defaults(func=cmd_import)
    restore = sub.add_parser("restore-backup", help="Restore a full backup while the server is stopped")
    restore.add_argument("--input", type=Path, required=True); restore.add_argument("--confirm-offline", action="store_true"); restore.add_argument("--yes", action="store_true"); restore.set_defaults(func=cmd_restore)
    config = sub.add_parser("config", help="View or update server configuration")
    config_sub = config.add_subparsers(dest="config_action", required=True)
    config_show = config_sub.add_parser("show", help="Show effective persisted configuration"); config_show.set_defaults(func=cmd_config_show)
    config_set = config_sub.add_parser("set", help="Set a server configuration value")
    config_set.add_argument("key", choices=["bind_host","bind_port","backup_interval_hours","backup_retention"]); config_set.add_argument("value"); config_set.set_defaults(func=cmd_config_set)
    admin = sub.add_parser("admin", help="Manage server administrators")
    admin_sub = admin.add_subparsers(dest="admin_action", required=True)
    admin_list = admin_sub.add_parser("list"); admin_list.set_defaults(func=cmd_admin_list)
    admin_grant = admin_sub.add_parser("grant"); admin_grant.add_argument("--email", required=True); admin_grant.add_argument("--role", choices=["operator","auditor"], required=True); admin_grant.set_defaults(func=cmd_admin_grant)
    admin_revoke = admin_sub.add_parser("revoke"); admin_revoke.add_argument("--email", required=True); admin_revoke.set_defaults(func=cmd_admin_revoke)
    users = sub.add_parser("users", help="Inspect server accounts")
    users_sub = users.add_subparsers(dest="users_action", required=True)
    users_list = users_sub.add_parser("list"); users_list.set_defaults(func=cmd_users_list)
    workspaces = sub.add_parser("workspaces", help="Inspect workspaces on this installation")
    workspaces_sub = workspaces.add_subparsers(dest="workspaces_action", required=True)
    workspaces_list = workspaces_sub.add_parser("list"); workspaces_list.set_defaults(func=cmd_workspaces_list)
    return parser


def main_cli() -> None:
    parser = build_parser(); args = parser.parse_args()
    if args.command in {"export","import"} and args.kind != "workspace" and not args.workspace:
        parser.error("--workspace is required for CSV import/export")
    args.func(args)


if __name__ == "__main__":
    main_cli()
