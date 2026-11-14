from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import calendar
import mimetypes
import os
import re
import secrets
import shutil
import socket
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("BOTTLENECK_DB", BASE_DIR / "data" / "bottleneck.sqlite3"))
UPLOAD_DIR = Path(os.getenv("BOTTLENECK_UPLOAD_DIR", BASE_DIR / "data" / "uploads"))
COOKIE_NAME = "bottleneck_session"
SESSION_DAYS = int(os.getenv("BOTTLENECK_SESSION_DAYS", "14"))
COOKIE_SECURE = os.getenv("BOTTLENECK_COOKIE_SECURE", "0") == "1"
PBKDF2_ITERATIONS = 310_000
APP_VERSION = "0.4.0"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".txt", ".csv", ".doc", ".docx", ".xls", ".xlsx", ".zip"}
STATUSES = {"todo", "in-progress", "review", "blocked", "done"}
PRIORITIES = {"low", "medium", "high", "urgent"}
ROLES = {"owner", "admin", "member"}
SCHEMA = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")


@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=25)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 25000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)).hex()
        return hmac.compare_digest(actual, digest_hex)
    except (ValueError, TypeError):
        return False


def init_db() -> None:
    with db() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        # v0.2.x compatibility: backfill the old single-assignee column.
        conn.execute("""INSERT OR IGNORE INTO task_assignees(task_id,user_id,assigned_by,created_at)
                        SELECT id,assignee_id,created_by,created_at FROM tasks WHERE assignee_id IS NOT NULL""")
        status_defaults = [("todo", "در صف", "neutral", 0), ("in-progress", "در حال انجام", "blue", 1),
                           ("review", "در بررسی", "gold", 2), ("blocked", "متوقف‌شده", "red", 3),
                           ("done", "تکمیل‌شده", "green", 4)]
        for workspace in conn.execute("SELECT id FROM workspaces").fetchall():
            for key, label, color, position in status_defaults:
                conn.execute("""INSERT OR IGNORE INTO workspace_status_labels
                    (workspace_id,status_key,label,color,position,updated_at) VALUES(?,?,?,?,?,?)""",
                    (workspace["id"], key, label, color, position, now_iso()))
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def log_activity(conn: sqlite3.Connection, workspace_id: str, user_id: str | None,
                 entity_type: str, entity_id: str | None, action: str, message: str) -> None:
    stamp = now_iso()
    conn.execute(
        "INSERT INTO activity_logs(id,workspace_id,user_id,entity_type,entity_id,action,message,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (new_id(), workspace_id, user_id, entity_type, entity_id, action, message, stamp),
    )
    conn.execute(
        "INSERT INTO workspace_events(workspace_id,user_id,kind,message,created_at) VALUES(?,?,?,?,?)",
        (workspace_id, user_id, action, message, stamp),
    )


def create_notification(conn: sqlite3.Connection, workspace_id: str, recipient_id: str,
                        actor_id: str | None, kind: str, title: str, body: str = "",
                        entity_type: str | None = None, entity_id: str | None = None) -> None:
    if actor_id and recipient_id == actor_id:
        return
    conn.execute(
        """INSERT INTO notifications(id,workspace_id,user_id,actor_id,kind,title,body,entity_type,entity_id,is_read,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,0,?)""",
        (new_id(), workspace_id, recipient_id, actor_id, kind, title, body, entity_type, entity_id, now_iso()),
    )


class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=200)
    workspace_name: str | None = Field(default=None, max_length=100)
    invite_code: str | None = None


class LoginInput(BaseModel):
    email: str
    password: str


class TaskInput(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=12000)
    status: str = "todo"
    priority: str = "medium"
    assignee_id: str | None = None
    assignee_ids: list[str] = Field(default_factory=list, max_length=100)
    team_id: str | None = None
    project_id: str | None = None
    due_date: str | None = None
    estimate: float | None = Field(default=None, ge=0, le=100000)


class ProjectInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=3000)
    color: str = Field(default="rust", max_length=20)


class TeamInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=1000)


class TeamMembersInput(BaseModel):
    member_ids: list[str] = Field(default_factory=list, max_length=500)


class InviteInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    role: str = "member"


class CommentInput(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class ProfileInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class OnboardingInput(BaseModel):
    completed: bool = True


class ChecklistInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)


class ChecklistToggleInput(BaseModel):
    is_done: bool


class TimeStopInput(BaseModel):
    entry_id: str | None = None
    note: str = Field(default="", max_length=1000)


class DependencyInput(BaseModel):
    dependency_ids: list[str] = Field(default_factory=list, max_length=200)


class RecurringInput(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=12000)
    priority: str = "medium"
    assignee_ids: list[str] = Field(default_factory=list, max_length=100)
    team_id: str | None = None
    project_id: str | None = None
    cadence: str = "weekly"
    interval_count: int = Field(default=1, ge=1, le=90)
    next_run_on: str
    due_offset_days: int = Field(default=0, ge=0, le=365)


class TemplateInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=2, max_length=180)
    description: str = Field(default="", max_length=12000)
    priority: str = "medium"
    estimate: float | None = Field(default=None, ge=0, le=100000)
    checklist: list[str] = Field(default_factory=list, max_length=80)
    assignee_ids: list[str] = Field(default_factory=list, max_length=100)
    team_id: str | None = None
    project_id: str | None = None


class ApprovalDecisionInput(BaseModel):
    status: str
    comment: str = Field(default="", max_length=3000)


class StatusLabelItem(BaseModel):
    key: str
    label: str = Field(min_length=1, max_length=32)
    color: str = "neutral"


class StatusLabelsInput(BaseModel):
    items: list[StatusLabelItem] = Field(min_length=5, max_length=5)


app = FastAPI(title="BottleNeck API", version=APP_VERSION)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def create_session(response: Response, user_id: str, workspace_id: str) -> None:
    token = secrets.token_urlsafe(40)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    with db() as conn:
        conn.execute(
            "INSERT INTO sessions(id,user_id,workspace_id,token_hash,expires_at,created_at) VALUES(?,?,?,?,?,?)",
            (new_id(), user_id, workspace_id, hash_token(token), expires.isoformat(), now_iso()),
        )
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_DAYS * 86400, httponly=True,
                        secure=COOKIE_SECURE, samesite="lax", path="/")


def get_context(request: Request) -> dict[str, Any]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="برای ادامه وارد حساب کاربری شوید.")
    with db() as conn:
        row = conn.execute(
            """SELECT s.id AS session_id,s.user_id,s.workspace_id,s.expires_at,
                      u.name,u.email,u.onboarding_completed,w.name AS workspace_name,m.role
               FROM sessions s JOIN users u ON u.id=s.user_id
               JOIN workspaces w ON w.id=s.workspace_id
               JOIN memberships m ON m.user_id=s.user_id AND m.workspace_id=s.workspace_id
               WHERE s.token_hash=?""", (hash_token(token),)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="نشست معتبر نیست. دوباره وارد شوید.")
        try:
            expiry = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            expiry = datetime.min.replace(tzinfo=timezone.utc)
        if expiry < datetime.now(timezone.utc):
            conn.execute("DELETE FROM sessions WHERE id=?", (row["session_id"],))
            raise HTTPException(status_code=401, detail="نشست شما منقضی شده است.")
        return dict(row)


def current_user(request: Request) -> dict[str, Any]:
    return get_context(request)


def require_admin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if user["role"] not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="این عملیات به دسترسی مدیر فضای کار نیاز دارد.")
    return user


def valid_email(email: str) -> str:
    email = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=422, detail="ساختار ایمیل معتبر نیست.")
    return email


def ensure_workspace_users(conn: sqlite3.Connection, workspace_id: str, candidate_ids: list[str]) -> list[str]:
    cleaned = list(dict.fromkeys(x for x in candidate_ids if x))
    if not cleaned:
        return []
    placeholders = ",".join("?" for _ in cleaned)
    rows = conn.execute(
        f"SELECT user_id FROM memberships WHERE workspace_id=? AND user_id IN ({placeholders})",
        [workspace_id, *cleaned],
    ).fetchall()
    found = {r["user_id"] for r in rows}
    if found != set(cleaned):
        raise HTTPException(status_code=422, detail="یکی از مسئولان انتخاب‌شده عضو این فضای کاری نیست.")
    return cleaned


def ensure_workspace_user(conn: sqlite3.Connection, workspace_id: str, candidate_id: str | None) -> None:
    if candidate_id:
        ensure_workspace_users(conn, workspace_id, [candidate_id])


def task_assignees(conn: sqlite3.Connection, task_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT u.id,u.name,u.email FROM task_assignees ta JOIN users u ON u.id=ta.user_id
           WHERE ta.task_id=? ORDER BY u.name""", (task_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def task_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    assignees = task_assignees(conn, row["id"])
    item = {
        "id": row["id"], "title": row["title"], "description": row["description"],
        "status": row["status"], "priority": row["priority"],
        "assigneeId": assignees[0]["id"] if assignees else row["assignee_id"],
        "assigneeIds": [a["id"] for a in assignees], "assignees": assignees,
        "teamId": row["team_id"], "projectId": row["project_id"],
        "dueDate": row["due_date"], "estimate": row["estimate"],
        "createdBy": row["created_by"], "createdAt": row["created_at"],
        "updatedAt": row["updated_at"], "completedAt": row["completed_at"],
        "assigneeName": ", ".join(a["name"] for a in assignees) or row["assignee_name"],
        "teamName": row["team_name"], "projectName": row["project_name"],
    }
    item["checklist"] = conn.execute(
        "SELECT COUNT(*) AS total,SUM(is_done) AS done FROM task_checklists WHERE task_id=?", (row["id"],)
    ).fetchone()["total"] or 0
    item["checklistDone"] = conn.execute(
        "SELECT COALESCE(SUM(is_done),0) FROM task_checklists WHERE task_id=?", (row["id"],)
    ).fetchone()[0]
    item["attachmentCount"] = conn.execute("SELECT COUNT(*) FROM task_attachments WHERE task_id=?", (row["id"],)).fetchone()[0]
    item["trackedSeconds"] = conn.execute("SELECT COALESCE(SUM(COALESCE(duration_seconds,CAST((julianday('now')-julianday(started_at))*86400 AS INTEGER))),0) FROM time_entries WHERE task_id=?", (row["id"],)).fetchone()[0]
    return item


def get_task_row(conn: sqlite3.Connection, workspace_id: str, task_id: str) -> sqlite3.Row:
    row = conn.execute(
        """SELECT t.*,u.name AS assignee_name,tm.name AS team_name,p.name AS project_name
           FROM tasks t LEFT JOIN users u ON u.id=t.assignee_id
           LEFT JOIN teams tm ON tm.id=t.team_id LEFT JOIN projects p ON p.id=t.project_id
           WHERE t.id=? AND t.workspace_id=?""", (task_id, workspace_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="کار موردنظر پیدا نشد.")
    return row


def create_task_notifications(conn: sqlite3.Connection, workspace_id: str, task_id: str,
                               title: str, recipient_ids: list[str], actor_id: str, kind: str = "assignment") -> None:
    for recipient_id in recipient_ids:
        if recipient_id != actor_id:
            create_notification(conn, workspace_id, recipient_id, actor_id, kind,
                                "یک کار به شما واگذار شد", title, "task", task_id)


def advance_recurring_date(value: date, cadence: str, interval_count: int) -> date:
    if cadence == "daily":
        return value + timedelta(days=interval_count)
    if cadence == "weekly":
        return value + timedelta(days=7 * interval_count)
    month_index = value.month - 1 + interval_count
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def generate_due_recurring(workspace_id: str) -> None:
    """Create scheduled tasks when the workspace is opened; cap catch-up per rule."""
    today = datetime.now(timezone.utc).date()
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rules = conn.execute("SELECT * FROM recurring_rules WHERE workspace_id=? AND is_active=1 AND next_run_on<=?",
                             (workspace_id, today.isoformat())).fetchall()
        for rule in rules:
            try:
                next_run = date.fromisoformat(rule["next_run_on"])
            except ValueError:
                continue
            try:
                assignee_ids = json.loads(rule["assignee_ids"] or "[]")
            except (TypeError, json.JSONDecodeError):
                assignee_ids = []
            assignee_ids = [r["user_id"] for r in conn.execute(
                "SELECT user_id FROM memberships WHERE workspace_id=? AND user_id IN (%s)" % (",".join("?" for _ in assignee_ids) or "NULL"),
                [workspace_id, *assignee_ids]).fetchall()] if assignee_ids else []
            created = 0
            while next_run <= today and created < 24:
                task_id, stamp = new_id(), now_iso()
                due_date = (next_run + timedelta(days=int(rule["due_offset_days"] or 0))).isoformat()
                conn.execute("""INSERT INTO tasks(id,workspace_id,title,description,status,priority,assignee_id,team_id,project_id,
                    due_date,estimate,created_by,created_at,updated_at,completed_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,NULL,?,?,?,NULL)""",
                    (task_id, workspace_id, rule["title"], rule["description"], "todo", rule["priority"],
                     assignee_ids[0] if assignee_ids else None, rule["team_id"], rule["project_id"], due_date,
                     rule["created_by"], stamp, stamp))
                for uid in assignee_ids:
                    conn.execute("INSERT OR IGNORE INTO task_assignees(task_id,user_id,assigned_by,created_at) VALUES(?,?,?,?)",
                                 (task_id, uid, rule["created_by"], stamp))
                    create_notification(conn, workspace_id, uid, rule["created_by"], "recurring", "کار تکرارشونده ایجاد شد", rule["title"], "task", task_id)
                log_activity(conn, workspace_id, rule["created_by"], "recurring", rule["id"], "generated",
                             f"کار تکرارشونده «{rule['title']}» برای {due_date} ساخته شد.")
                next_run = advance_recurring_date(next_run, rule["cadence"], int(rule["interval_count"]))
                created += 1
            conn.execute("UPDATE recurring_rules SET next_run_on=?,updated_at=? WHERE id=?",
                         (next_run.isoformat(), now_iso(), rule["id"]))


def workspace_snapshot(workspace_id: str, current_user_id: str) -> dict[str, Any]:
    with db() as conn:
        task_rows = conn.execute(
            """SELECT t.*,u.name AS assignee_name,tm.name AS team_name,p.name AS project_name
               FROM tasks t LEFT JOIN users u ON u.id=t.assignee_id
               LEFT JOIN teams tm ON tm.id=t.team_id LEFT JOIN projects p ON p.id=t.project_id
               WHERE t.workspace_id=? ORDER BY CASE WHEN t.due_date IS NULL THEN 1 ELSE 0 END,t.due_date,t.created_at DESC""",
            (workspace_id,),
        ).fetchall()
        tasks = [task_dict(conn, r) for r in task_rows]
        users = conn.execute(
            """SELECT u.id,u.name,u.email,m.role,m.joined_at,
               (SELECT COUNT(DISTINCT ta.task_id) FROM task_assignees ta JOIN tasks t ON t.id=ta.task_id
                 WHERE ta.user_id=u.id AND t.workspace_id=? AND t.status!='done') AS open_tasks
               FROM users u JOIN memberships m ON m.user_id=u.id
               WHERE m.workspace_id=? ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,u.name""",
            (workspace_id, workspace_id),
        ).fetchall()
        user_ids = [r["id"] for r in users]
        team_rows = conn.execute("SELECT * FROM teams WHERE workspace_id=? ORDER BY name", (workspace_id,)).fetchall()
        teams = []
        for team in team_rows:
            member_rows = conn.execute(
                """SELECT u.id,u.name,u.email FROM team_members tm JOIN users u ON u.id=tm.user_id
                   JOIN memberships m ON m.user_id=u.id AND m.workspace_id=? WHERE tm.team_id=? ORDER BY u.name""",
                (workspace_id, team["id"]),
            ).fetchall()
            teams.append({**dict(team), "members": [dict(x) for x in member_rows], "memberIds": [x["id"] for x in member_rows]})
        projects = conn.execute("SELECT * FROM projects WHERE workspace_id=? ORDER BY created_at DESC", (workspace_id,)).fetchall()
        activity = conn.execute(
            """SELECT a.*,u.name AS user_name FROM activity_logs a LEFT JOIN users u ON u.id=a.user_id
               WHERE a.workspace_id=? ORDER BY a.created_at DESC LIMIT 100""", (workspace_id,)
        ).fetchall()
        invitations = conn.execute(
            """SELECT id,email,role,expires_at,created_at FROM invitations WHERE workspace_id=?
               AND accepted_at IS NULL AND expires_at>? ORDER BY created_at DESC""", (workspace_id, now_iso())
        ).fetchall()
        notifications = conn.execute(
            """SELECT n.*,u.name AS actor_name FROM notifications n LEFT JOIN users u ON u.id=n.actor_id
               WHERE n.workspace_id=? AND n.user_id=? ORDER BY n.created_at DESC LIMIT 80""",
            (workspace_id, current_user_id),
        ).fetchall()
        unread = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE workspace_id=? AND user_id=? AND is_read=0",
            (workspace_id, current_user_id),
        ).fetchone()[0]
        cursor = conn.execute("SELECT COALESCE(MAX(id),0) FROM workspace_events WHERE workspace_id=?", (workspace_id,)).fetchone()[0]
        recurring = conn.execute("SELECT * FROM recurring_rules WHERE workspace_id=? ORDER BY is_active DESC,next_run_on", (workspace_id,)).fetchall()
        templates = conn.execute("SELECT * FROM task_templates WHERE workspace_id=? ORDER BY name", (workspace_id,)).fetchall()
        labels = conn.execute("SELECT status_key AS key,label,color,position FROM workspace_status_labels WHERE workspace_id=? ORDER BY position", (workspace_id,)).fetchall()
        active_timer = conn.execute("""SELECT te.*,t.title AS task_title FROM time_entries te JOIN tasks t ON t.id=te.task_id
            WHERE te.workspace_id=? AND te.user_id=? AND te.ended_at IS NULL ORDER BY te.started_at DESC LIMIT 1""",
            (workspace_id, current_user_id)).fetchone()
        pending_approvals = conn.execute("""SELECT a.*,t.title AS task_title,u.name AS requester_name FROM task_approvals a
            JOIN tasks t ON t.id=a.task_id JOIN users u ON u.id=a.requested_by
            WHERE a.workspace_id=? AND a.status='pending' ORDER BY a.requested_at DESC""", (workspace_id,)).fetchall()
        return {
            "tasks": tasks,
            "users": [dict(r) for r in users],
            "teams": teams,
            "projects": [dict(r) for r in projects],
            "activity": [dict(r) for r in activity],
            "invitations": [dict(r) for r in invitations],
            "notifications": [dict(r) for r in notifications],
            "unreadNotifications": unread,
            "eventCursor": cursor,
            "recurringRules": [dict(r) for r in recurring],
            "templates": [dict(r) for r in templates],
            "statusLabels": [dict(r) for r in labels],
            "activeTimer": dict(active_timer) if active_timer else None,
            "pendingApprovals": [dict(r) for r in pending_approvals],
        }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "application": "BottleNeck", "version": APP_VERSION}


def discover_lan_ips() -> list[str]:
    candidates: set[str] = set()
    primary: str | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("192.0.2.1", 80))
        primary = sock.getsockname()[0]
        candidates.add(primary)
        sock.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            candidates.add(info[4][0])
    except OSError:
        pass
    valid = {ip for ip in candidates if ipaddress.ip_address(ip).is_private and not ip.startswith("127.") and not ip.startswith("169.254.")}
    ordered = ([primary] if primary in valid else []) + sorted(valid - ({primary} if primary else set()))
    return ordered


@app.get("/api/network")
def network_info(request: Request) -> dict[str, Any]:
    ips = discover_lan_ips()
    host = request.url.hostname or "127.0.0.1"
    port = int(os.getenv("BOTTLENECK_PORT", "1939"))
    return {"host": host, "port": port, "lanIps": ips, "urls": [f"http://{ip}:{port}" for ip in ips]}


@app.post("/api/auth/register")
def register(payload: RegisterInput, response: Response) -> dict[str, Any]:
    email = valid_email(payload.email)
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="نام باید دست‌کم دو نویسه باشد.")
    user_id, workspace_id = new_id(), new_id()
    now = now_iso()
    with db() as conn:
        if conn.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone():
            raise HTTPException(status_code=409, detail="با این ایمیل قبلاً حساب ساخته شده است.")
        if payload.invite_code:
            invite = conn.execute(
                "SELECT * FROM invitations WHERE token_hash=? AND accepted_at IS NULL AND expires_at>?",
                (hash_token(payload.invite_code), now),
            ).fetchone()
            if not invite:
                raise HTTPException(status_code=400, detail="لینک دعوت معتبر نیست یا زمان آن به پایان رسیده است.")
            if invite["email"].lower() != email:
                raise HTTPException(status_code=400, detail="ایمیل ثبت‌نام باید با ایمیل دعوت‌شده یکسان باشد.")
            workspace_id = invite["workspace_id"]
            conn.execute("INSERT INTO users(id,name,email,password_hash,created_at) VALUES(?,?,?,?,?)",
                         (user_id, name, email, password_hash(payload.password), now))
            conn.execute("INSERT INTO memberships(id,workspace_id,user_id,role,joined_at) VALUES(?,?,?,?,?)",
                         (new_id(), workspace_id, user_id, invite["role"], now))
            conn.execute("UPDATE invitations SET accepted_at=? WHERE id=?", (now, invite["id"]))
            default_team = conn.execute("SELECT id FROM teams WHERE workspace_id=? ORDER BY created_at LIMIT 1", (workspace_id,)).fetchone()
            if default_team:
                conn.execute("INSERT OR IGNORE INTO team_members(team_id,user_id,created_at) VALUES(?,?,?)", (default_team["id"], user_id, now))
            log_activity(conn, workspace_id, user_id, "member", user_id, "joined", f"{name} به فضای کار پیوست.")
            owner = conn.execute("SELECT created_by FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
            if owner:
                create_notification(conn, workspace_id, owner["created_by"], user_id, "member", "عضو جدید به فضای کار پیوست", name, "member", user_id)
        else:
            workspace_name = (payload.workspace_name or "فضای کاری من").strip()
            if len(workspace_name) < 2:
                raise HTTPException(status_code=422, detail="نام فضای کار باید دست‌کم دو نویسه باشد.")
            conn.execute("INSERT INTO users(id,name,email,password_hash,created_at) VALUES(?,?,?,?,?)",
                         (user_id, name, email, password_hash(payload.password), now))
            conn.execute("INSERT INTO workspaces(id,name,created_by,created_at) VALUES(?,?,?,?)", (workspace_id, workspace_name, user_id, now))
            conn.execute("INSERT INTO memberships(id,workspace_id,user_id,role,joined_at) VALUES(?,?,?,?,?)", (new_id(), workspace_id, user_id, "owner", now))
            conn.execute("INSERT INTO workspace_settings(workspace_id,created_at) VALUES(?,?)", (workspace_id, now))
            for key, label, color, position in [("todo", "در صف", "neutral", 0), ("in-progress", "در حال انجام", "blue", 1),
                ("review", "در بررسی", "gold", 2), ("blocked", "متوقف‌شده", "red", 3), ("done", "تکمیل‌شده", "green", 4)]:
                conn.execute("INSERT INTO workspace_status_labels(workspace_id,status_key,label,color,position,updated_at) VALUES(?,?,?,?,?,?)",
                             (workspace_id,key,label,color,position,now))
            team_id = new_id()
            conn.execute("INSERT INTO teams(id,workspace_id,name,description,created_at) VALUES(?,?,?,?,?)",
                         (team_id, workspace_id, "عمومی", "تیم پیش‌فرض فضای کاری", now))
            conn.execute("INSERT INTO team_members(team_id,user_id,created_at) VALUES(?,?,?)", (team_id, user_id, now))
            log_activity(conn, workspace_id, user_id, "workspace", workspace_id, "created", f"فضای کاری «{workspace_name}» ساخته شد.")
    create_session(response, user_id, workspace_id)
    return {"ok": True, "workspaceId": workspace_id}


@app.post("/api/auth/login")
def login(payload: LoginInput, response: Response) -> dict[str, bool]:
    email = valid_email(payload.email)
    with db() as conn:
        row = conn.execute(
            """SELECT u.id,u.password_hash,m.workspace_id FROM users u JOIN memberships m ON m.user_id=u.id
               WHERE u.email=? COLLATE NOCASE ORDER BY CASE m.role WHEN 'owner' THEN 0 ELSE 1 END LIMIT 1""", (email,)
        ).fetchone()
        if not row or not verify_password(payload.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="ایمیل یا گذرواژه درست نیست.")
        conn.execute("DELETE FROM sessions WHERE expires_at<?", (now_iso(),))
        user_id, workspace_id = row["id"], row["workspace_id"]
    create_session(response, user_id, workspace_id)
    return {"ok": True}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        with db() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (hash_token(token),))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"id": user["user_id"], "name": user["name"], "email": user["email"], "role": user["role"],
            "workspaceId": user["workspace_id"], "workspaceName": user["workspace_name"],
            "onboardingCompleted": bool(user["onboarding_completed"])}


@app.patch("/api/me")
def update_me(payload: ProfileInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        conn.execute("UPDATE users SET name=? WHERE id=?", (payload.name.strip(), user["user_id"]))
        log_activity(conn, user["workspace_id"], user["user_id"], "profile", user["user_id"], "updated", "نام حساب کاربری به‌روزرسانی شد.")
    return {"ok": True}


@app.post("/api/me/onboarding")
def update_onboarding(payload: OnboardingInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        conn.execute("UPDATE users SET onboarding_completed=? WHERE id=?", (1 if payload.completed else 0, user["user_id"]))
    return {"ok": True}


@app.get("/api/bootstrap")
def bootstrap(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    me_data = {"id": user["user_id"], "name": user["name"], "email": user["email"], "role": user["role"],
               "workspaceId": user["workspace_id"], "workspaceName": user["workspace_name"],
               "onboardingCompleted": bool(user["onboarding_completed"])}
    generate_due_recurring(user["workspace_id"])
    return {"me": me_data, **workspace_snapshot(user["workspace_id"], user["user_id"])}


@app.get("/api/updates")
def updates(after_id: int = 0, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute(
            """SELECT id,user_id,kind,message,created_at FROM workspace_events
               WHERE workspace_id=? AND id>? ORDER BY id LIMIT 120""", (user["workspace_id"], max(0, after_id))
        ).fetchall()
        cursor = conn.execute("SELECT COALESCE(MAX(id),0) FROM workspace_events WHERE workspace_id=?", (user["workspace_id"],)).fetchone()[0]
    return {"events": [dict(r) for r in rows], "cursor": cursor}


@app.post("/api/tasks")
def create_task(payload: TaskInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if payload.status not in STATUSES or payload.priority not in PRIORITIES:
        raise HTTPException(status_code=422, detail="وضعیت یا اولویت انتخاب‌شده معتبر نیست.")
    task_id, now = new_id(), now_iso()
    ids = list(dict.fromkeys(payload.assignee_ids or ([payload.assignee_id] if payload.assignee_id else [])))
    with db() as conn:
        ids = ensure_workspace_users(conn, user["workspace_id"], ids)
        if payload.team_id and not conn.execute("SELECT id FROM teams WHERE id=? AND workspace_id=?", (payload.team_id, user["workspace_id"])).fetchone():
            raise HTTPException(status_code=422, detail="تیم انتخاب‌شده معتبر نیست.")
        if payload.project_id and not conn.execute("SELECT id FROM projects WHERE id=? AND workspace_id=?", (payload.project_id, user["workspace_id"])).fetchone():
            raise HTTPException(status_code=422, detail="پروژه انتخاب‌شده معتبر نیست.")
        conn.execute(
            """INSERT INTO tasks(id,workspace_id,title,description,status,priority,assignee_id,team_id,project_id,due_date,estimate,created_by,created_at,updated_at,completed_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (task_id,user["workspace_id"],payload.title.strip(),payload.description.strip(),payload.status,payload.priority,
             ids[0] if ids else None,payload.team_id or None,payload.project_id or None,payload.due_date or None,payload.estimate,
             user["user_id"],now,now,now if payload.status == "done" else None),
        )
        for uid in ids:
            conn.execute("INSERT INTO task_assignees(task_id,user_id,assigned_by,created_at) VALUES(?,?,?,?)", (task_id,uid,user["user_id"],now))
        create_task_notifications(conn,user["workspace_id"],task_id,payload.title.strip(),ids,user["user_id"])
        log_activity(conn,user["workspace_id"],user["user_id"],"task",task_id,"created",f"کار «{payload.title.strip()}» ایجاد شد.")
        row = get_task_row(conn,user["workspace_id"],task_id)
        return task_dict(conn,row)


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, payload: TaskInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if payload.status not in STATUSES or payload.priority not in PRIORITIES:
        raise HTTPException(status_code=422, detail="وضعیت یا اولویت انتخاب‌شده معتبر نیست.")
    now = now_iso()
    ids = list(dict.fromkeys(payload.assignee_ids or ([payload.assignee_id] if payload.assignee_id else [])))
    with db() as conn:
        old = get_task_row(conn,user["workspace_id"],task_id)
        ids = ensure_workspace_users(conn,user["workspace_id"],ids)
        if payload.team_id and not conn.execute("SELECT id FROM teams WHERE id=? AND workspace_id=?", (payload.team_id,user["workspace_id"])).fetchone():
            raise HTTPException(status_code=422, detail="تیم انتخاب‌شده معتبر نیست.")
        if payload.project_id and not conn.execute("SELECT id FROM projects WHERE id=? AND workspace_id=?", (payload.project_id,user["workspace_id"])).fetchone():
            raise HTTPException(status_code=422, detail="پروژه انتخاب‌شده معتبر نیست.")
        previous = {r["user_id"] for r in conn.execute("SELECT user_id FROM task_assignees WHERE task_id=?", (task_id,)).fetchall()}
        if payload.status == "done":
            blockers = conn.execute("""SELECT t.title FROM task_dependencies d JOIN tasks t ON t.id=d.depends_on_task_id
                WHERE d.task_id=? AND t.status!='done'""", (task_id,)).fetchall()
            if blockers:
                names = "، ".join(r["title"] for r in blockers[:4])
                raise HTTPException(status_code=409, detail=f"ابتدا پیش‌نیازها را تکمیل کنید: {names}")
        completed = old["completed_at"]
        if payload.status == "done" and not completed: completed = now
        elif payload.status != "done": completed = None
        conn.execute(
            """UPDATE tasks SET title=?,description=?,status=?,priority=?,assignee_id=?,team_id=?,project_id=?,due_date=?,estimate=?,updated_at=?,completed_at=?
               WHERE id=? AND workspace_id=?""",
            (payload.title.strip(),payload.description.strip(),payload.status,payload.priority,ids[0] if ids else None,
             payload.team_id or None,payload.project_id or None,payload.due_date or None,payload.estimate,now,completed,task_id,user["workspace_id"]),
        )
        conn.execute("DELETE FROM task_assignees WHERE task_id=?", (task_id,))
        for uid in ids:
            conn.execute("INSERT INTO task_assignees(task_id,user_id,assigned_by,created_at) VALUES(?,?,?,?)", (task_id,uid,user["user_id"],now))
        added = [uid for uid in ids if uid not in previous]
        create_task_notifications(conn,user["workspace_id"],task_id,payload.title.strip(),added,user["user_id"])
        action = "status_changed" if old["status"] != payload.status else "updated"
        msg = f"وضعیت کار «{payload.title.strip()}» تغییر کرد." if action == "status_changed" else f"کار «{payload.title.strip()}» ویرایش شد."
        log_activity(conn,user["workspace_id"],user["user_id"],"task",task_id,action,msg)
        return task_dict(conn,get_task_row(conn,user["workspace_id"],task_id))


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        row = get_task_row(conn,user["workspace_id"],task_id)
        if user["role"] == "member" and row["created_by"] != user["user_id"]:
            raise HTTPException(status_code=403, detail="فقط سازنده کار یا مدیر می‌تواند آن را حذف کند.")
        files = conn.execute("SELECT stored_name FROM task_attachments WHERE task_id=?", (task_id,)).fetchall()
        conn.execute("DELETE FROM tasks WHERE id=? AND workspace_id=?", (task_id,user["workspace_id"]))
        log_activity(conn,user["workspace_id"],user["user_id"],"task",task_id,"deleted",f"کار «{row['title']}» حذف شد.")
    for record in files:
        (UPLOAD_DIR / user["workspace_id"] / record["stored_name"]).unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/tasks/{task_id}/comments")
def list_comments(task_id: str, user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as conn:
        get_task_row(conn,user["workspace_id"],task_id)
        rows = conn.execute(
            """SELECT c.id,c.body,c.created_at,u.id AS user_id,u.name AS user_name
               FROM task_comments c JOIN users u ON u.id=c.user_id WHERE c.task_id=? ORDER BY c.created_at""", (task_id,)
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/tasks/{task_id}/comments")
def add_comment(task_id: str, payload: CommentInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        task = get_task_row(conn,user["workspace_id"],task_id)
        comment_id, now = new_id(), now_iso()
        body = payload.body.strip()
        conn.execute("INSERT INTO task_comments(id,task_id,user_id,body,created_at) VALUES(?,?,?,?,?)", (comment_id,task_id,user["user_id"],body,now))
        assigned = [r["user_id"] for r in conn.execute("SELECT user_id FROM task_assignees WHERE task_id=?", (task_id,)).fetchall()]
        for uid in assigned:
            create_notification(conn,user["workspace_id"],uid,user["user_id"],"comment","یادداشت تازه در یک کار",task["title"],"task",task_id)
        log_activity(conn,user["workspace_id"],user["user_id"],"task",task_id,"commented",f"برای کار «{task['title']}» یادداشتی ثبت شد.")
        return {"id":comment_id,"body":body,"created_at":now,"user_id":user["user_id"],"user_name":user["name"]}


@app.get("/api/tasks/{task_id}/checklist")
def get_checklist(task_id: str, user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as conn:
        get_task_row(conn,user["workspace_id"],task_id)
        rows = conn.execute("SELECT * FROM task_checklists WHERE task_id=? ORDER BY position,created_at", (task_id,)).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/tasks/{task_id}/checklist")
def add_checklist(task_id: str, payload: ChecklistInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        task = get_task_row(conn,user["workspace_id"],task_id)
        pos = conn.execute("SELECT COALESCE(MAX(position),0)+1 FROM task_checklists WHERE task_id=?", (task_id,)).fetchone()[0]
        item_id, now = new_id(), now_iso()
        conn.execute("INSERT INTO task_checklists(id,task_id,title,is_done,position,created_by,created_at) VALUES(?,?,?,0,?,?,?)",
                     (item_id,task_id,payload.title.strip(),pos,user["user_id"],now))
        log_activity(conn,user["workspace_id"],user["user_id"],"checklist",item_id,"created",f"یک مورد به چک‌لیست «{task['title']}» اضافه شد.")
        return dict(conn.execute("SELECT * FROM task_checklists WHERE id=?", (item_id,)).fetchone())


@app.patch("/api/tasks/{task_id}/checklist/{item_id}")
def toggle_checklist(task_id: str, item_id: str, payload: ChecklistToggleInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        task = get_task_row(conn,user["workspace_id"],task_id)
        row = conn.execute("SELECT * FROM task_checklists WHERE id=? AND task_id=?", (item_id,task_id)).fetchone()
        if not row: raise HTTPException(status_code=404, detail="مورد چک‌لیست پیدا نشد.")
        conn.execute("UPDATE task_checklists SET is_done=?,completed_at=? WHERE id=?",
                     (1 if payload.is_done else 0,now_iso() if payload.is_done else None,item_id))
        log_activity(conn,user["workspace_id"],user["user_id"],"checklist",item_id,"completed" if payload.is_done else "reopened",
                     f"موردی از چک‌لیست «{task['title']}» {'تکمیل شد' if payload.is_done else 'باز شد'}.")
        return dict(conn.execute("SELECT * FROM task_checklists WHERE id=?", (item_id,)).fetchone())


@app.delete("/api/tasks/{task_id}/checklist/{item_id}")
def delete_checklist(task_id: str, item_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        task = get_task_row(conn,user["workspace_id"],task_id)
        cur = conn.execute("DELETE FROM task_checklists WHERE id=? AND task_id=?", (item_id,task_id))
        if not cur.rowcount: raise HTTPException(status_code=404, detail="مورد چک‌لیست پیدا نشد.")
        log_activity(conn,user["workspace_id"],user["user_id"],"checklist",item_id,"deleted",f"موردی از چک‌لیست «{task['title']}» حذف شد.")
    return {"ok": True}


@app.get("/api/tasks/{task_id}/attachments")
def list_attachments(task_id: str, user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as conn:
        get_task_row(conn,user["workspace_id"],task_id)
        rows = conn.execute(
            """SELECT a.id,a.original_name,a.content_type,a.size_bytes,a.created_at,a.uploaded_by,u.name AS uploader_name
               FROM task_attachments a JOIN users u ON u.id=a.uploaded_by WHERE a.task_id=? ORDER BY a.created_at DESC""", (task_id,)
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/tasks/{task_id}/attachments")
async def upload_attachment(task_id: str, request: Request, x_filename: str = Header(default="attachment"), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    raw_name = unquote(x_filename).replace("\\", "/").split("/")[-1].strip()
    suffix = Path(raw_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="نوع فایل پشتیبانی نمی‌شود. PDF، تصویر، فایل‌های Office، CSV، TXT و ZIP مجاز هستند.")
    body = await request.body()
    if not body: raise HTTPException(status_code=400, detail="فایل خالی است.")
    if len(body) > MAX_UPLOAD_BYTES: raise HTTPException(status_code=413, detail="حجم هر فایل حداکثر ۱۰ مگابایت است.")
    with db() as conn:
        get_task_row(conn,user["workspace_id"],task_id)
        attachment_id = new_id()
        stored = f"{attachment_id}{suffix}"
        folder = UPLOAD_DIR / user["workspace_id"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / stored).write_bytes(body)
        mime = request.headers.get("content-type") or mimetypes.guess_type(raw_name)[0] or "application/octet-stream"
        now = now_iso()
        conn.execute(
            """INSERT INTO task_attachments(id,task_id,workspace_id,uploaded_by,original_name,stored_name,content_type,size_bytes,created_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (attachment_id,task_id,user["workspace_id"],user["user_id"],raw_name[:255],stored,mime,len(body),now),
        )
        log_activity(conn,user["workspace_id"],user["user_id"],"attachment",attachment_id,"uploaded",f"فایل «{raw_name[:100]}» به یک کار پیوست شد.")
        return {"id":attachment_id,"original_name":raw_name[:255],"content_type":mime,"size_bytes":len(body),"created_at":now}


@app.get("/api/attachments/{attachment_id}/download")
def download_attachment(attachment_id: str, user: dict[str, Any] = Depends(current_user)) -> FileResponse:
    with db() as conn:
        row = conn.execute("SELECT * FROM task_attachments WHERE id=? AND workspace_id=?", (attachment_id,user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404, detail="پیوست پیدا نشد.")
        path = UPLOAD_DIR / user["workspace_id"] / row["stored_name"]
        if not path.is_file(): raise HTTPException(status_code=404, detail="فایل روی سرور پیدا نشد.")
        return FileResponse(path, media_type=row["content_type"], filename=row["original_name"])


@app.delete("/api/attachments/{attachment_id}")
def delete_attachment(attachment_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        row = conn.execute("SELECT * FROM task_attachments WHERE id=? AND workspace_id=?", (attachment_id,user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404, detail="پیوست پیدا نشد.")
        if user["role"] == "member" and row["uploaded_by"] != user["user_id"]:
            raise HTTPException(status_code=403, detail="فقط بارگذار فایل یا مدیر می‌تواند آن را حذف کند.")
        conn.execute("DELETE FROM task_attachments WHERE id=?", (attachment_id,))
        log_activity(conn,user["workspace_id"],user["user_id"],"attachment",attachment_id,"deleted",f"پیوست «{row['original_name']}» حذف شد.")
        path = UPLOAD_DIR / user["workspace_id"] / row["stored_name"]
    path.unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/tasks/{task_id}/time")
def list_task_time(task_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        get_task_row(conn, user["workspace_id"], task_id)
        rows = conn.execute("""SELECT te.*,u.name AS user_name FROM time_entries te JOIN users u ON u.id=te.user_id
            WHERE te.task_id=? AND te.workspace_id=? ORDER BY te.started_at DESC LIMIT 100""",
            (task_id, user["workspace_id"])).fetchall()
        total = conn.execute("SELECT COALESCE(SUM(COALESCE(duration_seconds,CAST((julianday('now')-julianday(started_at))*86400 AS INTEGER))),0) FROM time_entries WHERE task_id=?", (task_id,)).fetchone()[0]
        active = conn.execute("SELECT id,started_at,user_id FROM time_entries WHERE task_id=? AND ended_at IS NULL", (task_id,)).fetchall()
    return {"items": [dict(r) for r in rows], "totalSeconds": int(total or 0), "active": [dict(r) for r in active]}


@app.post("/api/tasks/{task_id}/time/start")
def start_task_timer(task_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        task = get_task_row(conn, user["workspace_id"], task_id)
        existing = conn.execute("SELECT id FROM time_entries WHERE workspace_id=? AND user_id=? AND ended_at IS NULL",
                                (user["workspace_id"], user["user_id"])).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="ابتدا زمان‌سنج فعال فعلی را متوقف کنید.")
        entry_id, stamp = new_id(), now_iso()
        conn.execute("INSERT INTO time_entries(id,workspace_id,task_id,user_id,started_at,created_at) VALUES(?,?,?,?,?,?)",
                     (entry_id, user["workspace_id"], task_id, user["user_id"], stamp, stamp))
        log_activity(conn, user["workspace_id"], user["user_id"], "time", entry_id, "started", f"زمان‌سنج کار «{task['title']}» شروع شد.")
        return dict(conn.execute("SELECT * FROM time_entries WHERE id=?", (entry_id,)).fetchone())


@app.post("/api/time/stop")
def stop_task_timer(payload: TimeStopInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        if payload.entry_id:
            row = conn.execute("SELECT * FROM time_entries WHERE id=? AND workspace_id=? AND user_id=? AND ended_at IS NULL",
                               (payload.entry_id, user["workspace_id"], user["user_id"])).fetchone()
        else:
            row = conn.execute("SELECT * FROM time_entries WHERE workspace_id=? AND user_id=? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1",
                               (user["workspace_id"], user["user_id"])).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="زمان‌سنج فعالی برای توقف پیدا نشد.")
        ended = datetime.now(timezone.utc)
        started = datetime.fromisoformat(row["started_at"])
        seconds = max(0, int((ended - started).total_seconds()))
        stamp = ended.replace(microsecond=0).isoformat()
        conn.execute("UPDATE time_entries SET ended_at=?,duration_seconds=?,note=? WHERE id=?",
                     (stamp, seconds, payload.note.strip(), row["id"]))
        task = get_task_row(conn, user["workspace_id"], row["task_id"])
        log_activity(conn, user["workspace_id"], user["user_id"], "time", row["id"], "stopped", f"زمان‌سنج کار «{task['title']}» متوقف شد.")
        return {"id": row["id"], "durationSeconds": seconds, "endedAt": stamp}


@app.get("/api/reports")
def workspace_reports(period: str = "weekly", user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if period not in {"daily", "weekly"}:
        raise HTTPException(status_code=422, detail="بازه گزارش باید روزانه یا هفتگی باشد.")
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "weekly":
        # Persian work week: Saturday through Friday.
        start -= timedelta(days=(start.weekday() + 2) % 7)
    since = start.isoformat()
    with db() as conn:
        summary = conn.execute("""SELECT
            SUM(CASE WHEN created_at>=? THEN 1 ELSE 0 END) AS created,
            SUM(CASE WHEN completed_at>=? THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN status!='done' AND due_date<? THEN 1 ELSE 0 END) AS overdue,
            SUM(CASE WHEN status!='done' THEN 1 ELSE 0 END) AS open_tasks
            FROM tasks WHERE workspace_id=?""", (since, since, now.date().isoformat(), user["workspace_id"])).fetchone()
        seconds = conn.execute("""SELECT COALESCE(SUM(COALESCE(duration_seconds,CAST((julianday('now')-julianday(started_at))*86400 AS INTEGER))),0)
            FROM time_entries WHERE workspace_id=? AND started_at>=?""", (user["workspace_id"], since)).fetchone()[0]
        by_user = conn.execute("""SELECT u.id,u.name,COALESCE(SUM(COALESCE(te.duration_seconds,CAST((julianday('now')-julianday(te.started_at))*86400 AS INTEGER))),0) AS seconds,
            COUNT(DISTINCT te.task_id) AS tasks FROM users u LEFT JOIN time_entries te ON te.user_id=u.id AND te.workspace_id=? AND te.started_at>=?
            JOIN memberships m ON m.user_id=u.id AND m.workspace_id=? GROUP BY u.id ORDER BY seconds DESC,u.name""",
            (user["workspace_id"], since, user["workspace_id"])).fetchall()
        by_project = conn.execute("""SELECT COALESCE(p.name,'بدون پروژه') AS name,COALESCE(SUM(COALESCE(te.duration_seconds,CAST((julianday('now')-julianday(te.started_at))*86400 AS INTEGER))),0) AS seconds
            FROM time_entries te JOIN tasks t ON t.id=te.task_id LEFT JOIN projects p ON p.id=t.project_id
            WHERE te.workspace_id=? AND te.started_at>=? GROUP BY p.id ORDER BY seconds DESC LIMIT 12""",
            (user["workspace_id"], since)).fetchall()
    return {"period": period, "from": since, "to": now.isoformat(), "summary": {k: int(summary[k] or 0) for k in ("created", "completed", "overdue", "open_tasks")},
            "trackedSeconds": int(seconds or 0), "byUser": [dict(r) for r in by_user], "byProject": [dict(r) for r in by_project]}


@app.get("/api/tasks/{task_id}/dependencies")
def get_task_dependencies(task_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        get_task_row(conn, user["workspace_id"], task_id)
        rows = conn.execute("""SELECT t.id,t.title,t.status FROM task_dependencies d JOIN tasks t ON t.id=d.depends_on_task_id
            WHERE d.task_id=? AND t.workspace_id=? ORDER BY t.created_at""", (task_id, user["workspace_id"])).fetchall()
        options = conn.execute("SELECT id,title,status FROM tasks WHERE workspace_id=? AND id<>? ORDER BY created_at DESC LIMIT 500",
                               (user["workspace_id"], task_id)).fetchall()
    return {"items": [dict(r) for r in rows], "options": [dict(r) for r in options]}


@app.put("/api/tasks/{task_id}/dependencies")
def set_task_dependencies(task_id: str, payload: DependencyInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    dep_ids = list(dict.fromkeys(x for x in payload.dependency_ids if x))
    if task_id in dep_ids:
        raise HTTPException(status_code=422, detail="یک کار نمی‌تواند پیش‌نیاز خودش باشد.")
    with db() as conn:
        get_task_row(conn, user["workspace_id"], task_id)
        if dep_ids:
            placeholders = ",".join("?" for _ in dep_ids)
            found = {r["id"] for r in conn.execute(f"SELECT id FROM tasks WHERE workspace_id=? AND id IN ({placeholders})",
                                                  [user["workspace_id"], *dep_ids]).fetchall()}
            if found != set(dep_ids):
                raise HTTPException(status_code=422, detail="یکی از پیش‌نیازها در فضای کاری شما وجود ندارد.")
            for dep_id in dep_ids:
                cycle = conn.execute("""WITH RECURSIVE chain(id) AS (
                    SELECT depends_on_task_id FROM task_dependencies WHERE task_id=?
                    UNION SELECT d.depends_on_task_id FROM task_dependencies d JOIN chain c ON d.task_id=c.id
                    ) SELECT 1 FROM chain WHERE id=? LIMIT 1""", (dep_id, task_id)).fetchone()
                if cycle:
                    raise HTTPException(status_code=409, detail="این ارتباط باعث ایجاد چرخه در پیش‌نیازها می‌شود.")
        conn.execute("DELETE FROM task_dependencies WHERE task_id=?", (task_id,))
        stamp = now_iso()
        for dep_id in dep_ids:
            conn.execute("INSERT INTO task_dependencies(task_id,depends_on_task_id,created_by,created_at) VALUES(?,?,?,?)",
                         (task_id, dep_id, user["user_id"], stamp))
        log_activity(conn, user["workspace_id"], user["user_id"], "task", task_id, "dependencies_updated", "پیش‌نیازهای یک کار به‌روزرسانی شدند.")
    return {"ok": True, "dependencyIds": dep_ids}


@app.get("/api/recurring")
def list_recurring(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM recurring_rules WHERE workspace_id=? ORDER BY is_active DESC,next_run_on",
                                              (user["workspace_id"],)).fetchall()]


@app.post("/api/recurring")
def create_recurring(payload: RecurringInput, user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    if payload.priority not in PRIORITIES or payload.cadence not in {"daily", "weekly", "monthly"}:
        raise HTTPException(status_code=422, detail="اولویت یا تناوب تکرار معتبر نیست.")
    try:
        first_date = date.fromisoformat(payload.next_run_on)
    except ValueError:
        raise HTTPException(status_code=422, detail="تاریخ شروع معتبر نیست.")
    if payload.team_id:
        with db() as conn:
            if not conn.execute("SELECT id FROM teams WHERE id=? AND workspace_id=?", (payload.team_id, user["workspace_id"])).fetchone():
                raise HTTPException(status_code=422, detail="تیم انتخاب‌شده معتبر نیست.")
            if payload.project_id and not conn.execute("SELECT id FROM projects WHERE id=? AND workspace_id=?", (payload.project_id, user["workspace_id"])).fetchone():
                raise HTTPException(status_code=422, detail="پروژه انتخاب‌شده معتبر نیست.")
            ids = ensure_workspace_users(conn, user["workspace_id"], payload.assignee_ids)
            rule_id, stamp = new_id(), now_iso()
            conn.execute("""INSERT INTO recurring_rules(id,workspace_id,title,description,priority,assignee_ids,team_id,project_id,cadence,
                interval_count,next_run_on,due_offset_days,is_active,created_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?, ?,1,?,?,?)""",
                (rule_id,user["workspace_id"],payload.title.strip(),payload.description.strip(),payload.priority,json.dumps(ids),payload.team_id,
                 payload.project_id,payload.cadence,payload.interval_count,first_date.isoformat(),payload.due_offset_days,user["user_id"],stamp,stamp))
            log_activity(conn,user["workspace_id"],user["user_id"],"recurring",rule_id,"created",f"الگوی تکرار «{payload.title.strip()}» ساخته شد.")
            return dict(conn.execute("SELECT * FROM recurring_rules WHERE id=?", (rule_id,)).fetchone())
    with db() as conn:
        if payload.project_id and not conn.execute("SELECT id FROM projects WHERE id=? AND workspace_id=?", (payload.project_id, user["workspace_id"])).fetchone():
            raise HTTPException(status_code=422, detail="پروژه انتخاب‌شده معتبر نیست.")
        ids = ensure_workspace_users(conn, user["workspace_id"], payload.assignee_ids)
        rule_id, stamp = new_id(), now_iso()
        conn.execute("""INSERT INTO recurring_rules(id,workspace_id,title,description,priority,assignee_ids,team_id,project_id,cadence,
            interval_count,next_run_on,due_offset_days,is_active,created_by,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?)""",
            (rule_id,user["workspace_id"],payload.title.strip(),payload.description.strip(),payload.priority,json.dumps(ids),None,
             payload.project_id,payload.cadence,payload.interval_count,first_date.isoformat(),payload.due_offset_days,user["user_id"],stamp,stamp))
        log_activity(conn,user["workspace_id"],user["user_id"],"recurring",rule_id,"created",f"الگوی تکرار «{payload.title.strip()}» ساخته شد.")
        return dict(conn.execute("SELECT * FROM recurring_rules WHERE id=?", (rule_id,)).fetchone())


@app.patch("/api/recurring/{rule_id}/toggle")
def toggle_recurring(rule_id: str, user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    with db() as conn:
        rule = conn.execute("SELECT * FROM recurring_rules WHERE id=? AND workspace_id=?", (rule_id,user["workspace_id"])).fetchone()
        if not rule: raise HTTPException(status_code=404, detail="الگوی تکرار پیدا نشد.")
        active = 0 if rule["is_active"] else 1
        conn.execute("UPDATE recurring_rules SET is_active=?,updated_at=? WHERE id=?", (active,now_iso(),rule_id))
        log_activity(conn,user["workspace_id"],user["user_id"],"recurring",rule_id,"toggled",f"الگوی «{rule['title']}» {'فعال' if active else 'متوقف'} شد.")
        return {"id":rule_id,"is_active":active}


@app.delete("/api/recurring/{rule_id}")
def delete_recurring(rule_id: str, user: dict[str, Any] = Depends(require_admin)) -> dict[str, bool]:
    with db() as conn:
        rule = conn.execute("SELECT title FROM recurring_rules WHERE id=? AND workspace_id=?", (rule_id,user["workspace_id"])).fetchone()
        if not rule: raise HTTPException(status_code=404, detail="الگوی تکرار پیدا نشد.")
        conn.execute("DELETE FROM recurring_rules WHERE id=?", (rule_id,))
        log_activity(conn,user["workspace_id"],user["user_id"],"recurring",rule_id,"deleted",f"الگوی «{rule['title']}» حذف شد.")
    return {"ok": True}


@app.get("/api/templates")
def list_templates(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM task_templates WHERE workspace_id=? ORDER BY name", (user["workspace_id"],)).fetchall()
        result=[]
        for r in rows:
            item=dict(r)
            try: item["checklist"] = json.loads(item.pop("checklist_json") or "[]")
            except (TypeError,json.JSONDecodeError): item["checklist"]=[]
            try: item["assigneeIds"] = json.loads(item.pop("assignee_ids") or "[]")
            except (TypeError,json.JSONDecodeError): item["assigneeIds"]=[]
            result.append(item)
        return result


@app.post("/api/templates")
def create_template(payload: TemplateInput, user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    if payload.priority not in PRIORITIES:
        raise HTTPException(status_code=422, detail="اولویت معتبر نیست.")
    with db() as conn:
        ids=ensure_workspace_users(conn,user["workspace_id"],payload.assignee_ids)
        if payload.team_id and not conn.execute("SELECT id FROM teams WHERE id=? AND workspace_id=?", (payload.team_id,user["workspace_id"])).fetchone():
            raise HTTPException(status_code=422, detail="تیم انتخاب‌شده معتبر نیست.")
        if payload.project_id and not conn.execute("SELECT id FROM projects WHERE id=? AND workspace_id=?", (payload.project_id,user["workspace_id"])).fetchone():
            raise HTTPException(status_code=422, detail="پروژه انتخاب‌شده معتبر نیست.")
        template_id,stamp=new_id(),now_iso()
        conn.execute("""INSERT INTO task_templates(id,workspace_id,name,title,description,priority,estimate,checklist_json,assignee_ids,team_id,project_id,created_by,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(template_id,user["workspace_id"],payload.name.strip(),payload.title.strip(),payload.description.strip(),payload.priority,
            payload.estimate,json.dumps([x.strip() for x in payload.checklist if x.strip()]),json.dumps(ids),payload.team_id,payload.project_id,user["user_id"],stamp,stamp))
        log_activity(conn,user["workspace_id"],user["user_id"],"template",template_id,"created",f"قالب «{payload.name.strip()}» ساخته شد.")
        row=dict(conn.execute("SELECT * FROM task_templates WHERE id=?",(template_id,)).fetchone())
        row["checklist"] = json.loads(row.pop("checklist_json")); row["assigneeIds"] = json.loads(row.pop("assignee_ids"))
        return row


@app.post("/api/templates/{template_id}/create-task")
def create_task_from_template(template_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        t=conn.execute("SELECT * FROM task_templates WHERE id=? AND workspace_id=?",(template_id,user["workspace_id"])).fetchone()
        if not t: raise HTTPException(status_code=404,detail="قالب پیدا نشد.")
        try: assignee_ids=json.loads(t["assignee_ids"] or "[]")
        except (TypeError,json.JSONDecodeError): assignee_ids=[]
        ids=ensure_workspace_users(conn,user["workspace_id"],assignee_ids)
        task_id,stamp=new_id(),now_iso()
        conn.execute("""INSERT INTO tasks(id,workspace_id,title,description,status,priority,assignee_id,team_id,project_id,due_date,estimate,created_by,created_at,updated_at,completed_at)
            VALUES(?,?,?,?,?,?,?,?,?,NULL,?,?,?,?,NULL)""",(task_id,user["workspace_id"],t["title"],t["description"],"todo",t["priority"],ids[0] if ids else None,
            t["team_id"],t["project_id"],t["estimate"],user["user_id"],stamp,stamp))
        for uid in ids:
            conn.execute("INSERT INTO task_assignees(task_id,user_id,assigned_by,created_at) VALUES(?,?,?,?)",(task_id,uid,user["user_id"],stamp))
        try: checklist=json.loads(t["checklist_json"] or "[]")
        except (TypeError,json.JSONDecodeError): checklist=[]
        for pos,title in enumerate(checklist,1):
            conn.execute("INSERT INTO task_checklists(id,task_id,title,is_done,position,created_by,created_at) VALUES(?,?,?,0,?,?,?)",
                         (new_id(),task_id,title,pos,user["user_id"],stamp))
        create_task_notifications(conn,user["workspace_id"],task_id,t["title"],ids,user["user_id"])
        log_activity(conn,user["workspace_id"],user["user_id"],"task",task_id,"created_from_template",f"کار «{t['title']}» از قالب «{t['name']}» ساخته شد.")
        return task_dict(conn,get_task_row(conn,user["workspace_id"],task_id))


@app.delete("/api/templates/{template_id}")
def delete_template(template_id: str, user: dict[str, Any] = Depends(require_admin)) -> dict[str, bool]:
    with db() as conn:
        row=conn.execute("SELECT name FROM task_templates WHERE id=? AND workspace_id=?",(template_id,user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404,detail="قالب پیدا نشد.")
        conn.execute("DELETE FROM task_templates WHERE id=?",(template_id,))
        log_activity(conn,user["workspace_id"],user["user_id"],"template",template_id,"deleted",f"قالب «{row['name']}» حذف شد.")
    return {"ok":True}


@app.get("/api/tasks/{task_id}/approvals")
def list_task_approvals(task_id: str, user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as conn:
        get_task_row(conn,user["workspace_id"],task_id)
        return [dict(r) for r in conn.execute("""SELECT a.*,u.name AS requester_name,r.name AS reviewer_name FROM task_approvals a
            JOIN users u ON u.id=a.requested_by LEFT JOIN users r ON r.id=a.reviewer_id WHERE a.task_id=? ORDER BY a.requested_at DESC""",
            (task_id,)).fetchall()]


@app.post("/api/tasks/{task_id}/approvals")
def request_task_approval(task_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        task=get_task_row(conn,user["workspace_id"],task_id)
        pending=conn.execute("SELECT id FROM task_approvals WHERE task_id=? AND status='pending'",(task_id,)).fetchone()
        if pending: raise HTTPException(status_code=409,detail="برای این کار درخواست بازبینی در انتظار پاسخ وجود دارد.")
        reviewer=conn.execute("""SELECT user_id FROM memberships WHERE workspace_id=? AND role IN ('owner','admin') AND user_id<>? ORDER BY CASE role WHEN 'owner' THEN 0 ELSE 1 END LIMIT 1""",
            (user["workspace_id"],user["user_id"])).fetchone()
        approval_id,stamp=new_id(),now_iso()
        conn.execute("INSERT INTO task_approvals(id,workspace_id,task_id,requested_by,reviewer_id,status,requested_at) VALUES(?,?,?,?,?,'pending',?)",
                     (approval_id,user["workspace_id"],task_id,user["user_id"],reviewer["user_id"] if reviewer else None,stamp))
        admins=conn.execute("SELECT user_id FROM memberships WHERE workspace_id=? AND role IN ('owner','admin')",(user["workspace_id"],)).fetchall()
        for admin in admins: create_notification(conn,user["workspace_id"],admin["user_id"],user["user_id"],"approval","درخواست تأیید کار",task["title"],"task",task_id)
        conn.execute("UPDATE tasks SET status='review',updated_at=? WHERE id=?",(stamp,task_id))
        log_activity(conn,user["workspace_id"],user["user_id"],"approval",approval_id,"requested",f"برای کار «{task['title']}» درخواست تأیید ثبت شد.")
        return dict(conn.execute("SELECT * FROM task_approvals WHERE id=?",(approval_id,)).fetchone())


@app.patch("/api/approvals/{approval_id}")
def decide_approval(approval_id: str, payload: ApprovalDecisionInput, user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    if payload.status not in {"approved","rejected"}:
        raise HTTPException(status_code=422,detail="تصمیم باید تأیید یا رد باشد.")
    with db() as conn:
        approval=conn.execute("SELECT * FROM task_approvals WHERE id=? AND workspace_id=?",(approval_id,user["workspace_id"])).fetchone()
        if not approval: raise HTTPException(status_code=404,detail="درخواست بازبینی پیدا نشد.")
        if approval["status"]!='pending': raise HTTPException(status_code=409,detail="این درخواست قبلاً بررسی شده است.")
        if payload.status=='approved':
            blockers=conn.execute("SELECT t.title FROM task_dependencies d JOIN tasks t ON t.id=d.depends_on_task_id WHERE d.task_id=? AND t.status!='done'",(approval["task_id"],)).fetchall()
            if blockers: raise HTTPException(status_code=409,detail="پیش‌نیازهای این کار هنوز تکمیل نشده‌اند.")
        stamp=now_iso()
        conn.execute("UPDATE task_approvals SET status=?,comment=?,reviewer_id=?,reviewed_at=? WHERE id=?",
                     (payload.status,payload.comment.strip(),user["user_id"],stamp,approval_id))
        task=get_task_row(conn,user["workspace_id"],approval["task_id"])
        new_status='done' if payload.status=='approved' else 'in-progress'
        conn.execute("UPDATE tasks SET status=?,completed_at=?,updated_at=? WHERE id=?",
                     (new_status,stamp if new_status=='done' else None,stamp,approval["task_id"]))
        create_notification(conn,user["workspace_id"],approval["requested_by"],user["user_id"],"approval_result",
            "درخواست کار تأیید شد" if payload.status=='approved' else "درخواست کار نیاز به اصلاح دارد",payload.comment.strip() or task["title"],"task",approval["task_id"])
        log_activity(conn,user["workspace_id"],user["user_id"],"approval",approval_id,payload.status,
                     f"درخواست بازبینی کار «{task['title']}» {'تأیید' if payload.status=='approved' else 'رد'} شد.")
        return dict(conn.execute("SELECT * FROM task_approvals WHERE id=?",(approval_id,)).fetchone())


@app.put("/api/status-labels")
def update_status_labels(payload: StatusLabelsInput, user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    allowed={"todo","in-progress","review","blocked","done"}
    colors={"neutral","blue","gold","red","green","purple"}
    items=payload.items
    if {x.key for x in items}!=allowed or any(x.color not in colors for x in items):
        raise HTTPException(status_code=422,detail="هر پنج وضعیت اصلی با رنگ معتبر باید ارسال شوند.")
    with db() as conn:
        for position,item in enumerate(items):
            conn.execute("""INSERT INTO workspace_status_labels(workspace_id,status_key,label,color,position,updated_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(workspace_id,status_key) DO UPDATE SET label=excluded.label,color=excluded.color,position=excluded.position,updated_at=excluded.updated_at""",
                (user["workspace_id"],item.key,item.label.strip(),item.color,position,now_iso()))
        log_activity(conn,user["workspace_id"],user["user_id"],"settings",user["workspace_id"],"statuses_updated","نام و رنگ وضعیت‌های کاری تغییر کرد.")
        rows=conn.execute("SELECT status_key AS key,label,color,position FROM workspace_status_labels WHERE workspace_id=? ORDER BY position",(user["workspace_id"],)).fetchall()
    return {"items":[dict(r) for r in rows]}


@app.get("/api/projects")
def list_projects(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM projects WHERE workspace_id=? ORDER BY created_at DESC", (user["workspace_id"],)).fetchall()]


@app.post("/api/projects")
def create_project(payload: ProjectInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    project_id, now = new_id(), now_iso()
    with db() as conn:
        conn.execute("INSERT INTO projects(id,workspace_id,name,description,color,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                     (project_id,user["workspace_id"],payload.name.strip(),payload.description.strip(),payload.color,user["user_id"],now,now))
        log_activity(conn,user["workspace_id"],user["user_id"],"project",project_id,"created",f"پروژه «{payload.name.strip()}» ایجاد شد.")
        return dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())


@app.patch("/api/projects/{project_id}")
def update_project(project_id: str, payload: ProjectInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    now = now_iso()
    with db() as conn:
        exists = conn.execute("SELECT id FROM projects WHERE id=? AND workspace_id=?", (project_id,user["workspace_id"])).fetchone()
        if not exists: raise HTTPException(status_code=404, detail="پروژه پیدا نشد.")
        conn.execute("UPDATE projects SET name=?,description=?,color=?,updated_at=? WHERE id=?", (payload.name.strip(),payload.description.strip(),payload.color,now,project_id))
        log_activity(conn,user["workspace_id"],user["user_id"],"project",project_id,"updated",f"پروژه «{payload.name.strip()}» ویرایش شد.")
        return dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, user: dict[str, Any] = Depends(require_admin)) -> dict[str, bool]:
    with db() as conn:
        row = conn.execute("SELECT name FROM projects WHERE id=? AND workspace_id=?", (project_id,user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404, detail="پروژه پیدا نشد.")
        conn.execute("UPDATE tasks SET project_id=NULL WHERE project_id=?", (project_id,))
        conn.execute("UPDATE task_templates SET project_id=NULL WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        log_activity(conn,user["workspace_id"],user["user_id"],"project",project_id,"deleted",f"پروژه «{row['name']}» حذف شد.")
    return {"ok": True}


@app.post("/api/teams")
def create_team(payload: TeamInput, user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    team_id, now = new_id(), now_iso()
    with db() as conn:
        conn.execute("INSERT INTO teams(id,workspace_id,name,description,created_at) VALUES(?,?,?,?,?)",
                     (team_id,user["workspace_id"],payload.name.strip(),payload.description.strip(),now))
        conn.execute("INSERT INTO team_members(team_id,user_id,created_at) VALUES(?,?,?)", (team_id,user["user_id"],now))
        log_activity(conn,user["workspace_id"],user["user_id"],"team",team_id,"created",f"تیم «{payload.name.strip()}» ایجاد شد.")
        return {**dict(conn.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()), "members": [{"id":user["user_id"],"name":user["name"]}], "memberIds": [user["user_id"]]}


@app.put("/api/teams/{team_id}/members")
def update_team_members(team_id: str, payload: TeamMembersInput, user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    with db() as conn:
        team = conn.execute("SELECT * FROM teams WHERE id=? AND workspace_id=?", (team_id,user["workspace_id"])).fetchone()
        if not team: raise HTTPException(status_code=404, detail="تیم پیدا نشد.")
        members = ensure_workspace_users(conn,user["workspace_id"],payload.member_ids)
        conn.execute("DELETE FROM team_members WHERE team_id=?", (team_id,))
        now = now_iso()
        for uid in members:
            conn.execute("INSERT INTO team_members(team_id,user_id,created_at) VALUES(?,?,?)", (team_id,uid,now))
        log_activity(conn,user["workspace_id"],user["user_id"],"team",team_id,"members_updated",f"اعضای تیم «{team['name']}» به‌روزرسانی شدند.")
    return {"ok": True, "memberIds": members}


@app.delete("/api/teams/{team_id}")
def delete_team(team_id: str, user: dict[str, Any] = Depends(require_admin)) -> dict[str, bool]:
    with db() as conn:
        team = conn.execute("SELECT name FROM teams WHERE id=? AND workspace_id=?", (team_id,user["workspace_id"])).fetchone()
        if not team: raise HTTPException(status_code=404, detail="تیم پیدا نشد.")
        conn.execute("UPDATE tasks SET team_id=NULL WHERE team_id=?", (team_id,))
        conn.execute("UPDATE task_templates SET team_id=NULL WHERE team_id=?", (team_id,))
        conn.execute("DELETE FROM teams WHERE id=?", (team_id,))
        log_activity(conn,user["workspace_id"],user["user_id"],"team",team_id,"deleted",f"تیم «{team['name']}» حذف شد.")
    return {"ok": True}


@app.post("/api/invitations")
def create_invitation(payload: InviteInput, request: Request, user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    email = valid_email(payload.email)
    role = payload.role if payload.role in {"admin", "member"} else "member"
    with db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        if existing:
            already = conn.execute("SELECT id FROM memberships WHERE user_id=? AND workspace_id=?", (existing["id"],user["workspace_id"])).fetchone()
            if already: raise HTTPException(status_code=409, detail="این کاربر هم‌اکنون عضو فضای کار است.")
            raise HTTPException(status_code=409, detail="این ایمیل از قبل حساب دارد و در این نسخه نمی‌تواند با دعوت‌نامه به فضای دیگری منتقل شود.")
        invite = conn.execute("SELECT id FROM invitations WHERE workspace_id=? AND email=? COLLATE NOCASE AND accepted_at IS NULL AND expires_at>?",
                              (user["workspace_id"],email,now_iso())).fetchone()
        if invite: raise HTTPException(status_code=409, detail="برای این ایمیل دعوت فعال وجود دارد.")
        raw_token = secrets.token_urlsafe(28)
        invite_id, now = new_id(), now_iso()
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0).isoformat()
        conn.execute("INSERT INTO invitations(id,workspace_id,email,role,token_hash,invited_by,expires_at,created_at) VALUES(?,?,?,?,?,?,?,?)",
                     (invite_id,user["workspace_id"],email,role,hash_token(raw_token),user["user_id"],expires,now))
        log_activity(conn,user["workspace_id"],user["user_id"],"invitation",invite_id,"created",f"دعوت‌نامه‌ای برای {email} ایجاد شد.")
    request_host = request.url.hostname or "127.0.0.1"
    port = int(os.getenv("BOTTLENECK_PORT", "1939"))
    if request_host in {"127.0.0.1", "localhost", "0.0.0.0"}:
        lan_ips = discover_lan_ips()
        request_host = lan_ips[0] if lan_ips else request_host
    invite_url = f"http://{request_host}:{port}/?invite={raw_token}"
    return {"id":invite_id,"email":email,"role":role,"inviteCode":raw_token,"inviteUrl":invite_url,"expiresAt":expires}


@app.delete("/api/invitations/{invitation_id}")
def revoke_invitation(invitation_id: str, user: dict[str, Any] = Depends(require_admin)) -> dict[str, bool]:
    with db() as conn:
        cur = conn.execute("DELETE FROM invitations WHERE id=? AND workspace_id=? AND accepted_at IS NULL", (invitation_id,user["workspace_id"]))
        if not cur.rowcount: raise HTTPException(status_code=404, detail="دعوت‌نامه پیدا نشد.")
        log_activity(conn,user["workspace_id"],user["user_id"],"invitation",invitation_id,"revoked","یک دعوت‌نامه لغو شد.")
    return {"ok": True}


@app.get("/api/notifications")
def list_notifications(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute("""SELECT n.*,u.name AS actor_name FROM notifications n LEFT JOIN users u ON u.id=n.actor_id
                              WHERE n.workspace_id=? AND n.user_id=? ORDER BY n.created_at DESC LIMIT 100""",
                            (user["workspace_id"],user["user_id"])).fetchall()
        unread = conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id=? AND workspace_id=? AND is_read=0",
                              (user["user_id"],user["workspace_id"])).fetchone()[0]
        return {"items":[dict(r) for r in rows],"unread":unread}


@app.patch("/api/notifications/{notification_id}/read")
def read_notification(notification_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        conn.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=? AND workspace_id=?",
                     (notification_id,user["user_id"],user["workspace_id"]))
    return {"ok": True}


@app.post("/api/notifications/read-all")
def read_all_notifications(user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=? AND workspace_id=?",
                     (user["user_id"],user["workspace_id"]))
    return {"ok": True}


@app.api_route("/", methods=["GET", "HEAD"])
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
