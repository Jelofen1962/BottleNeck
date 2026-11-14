from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("BOTTLENECK_DB", BASE_DIR / "data" / "bottleneck.sqlite3"))
COOKIE_NAME = "bottleneck_session"
SESSION_DAYS = int(os.getenv("BOTTLENECK_SESSION_DAYS", "14"))
COOKIE_SECURE = os.getenv("BOTTLENECK_COOKIE_SECURE", "0") == "1"
PBKDF2_ITERATIONS = 310_000

STATUSES = {"todo", "in-progress", "review", "blocked", "done"}
PRIORITIES = {"low", "medium", "high", "urgent"}
ROLES = {"owner", "admin", "member"}

SCHEMA = r"""
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  onboarding_completed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workspaces (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_by TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memberships (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('owner','admin','member')),
  joined_at TEXT NOT NULL,
  UNIQUE(workspace_id, user_id)
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invitations (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  email TEXT NOT NULL COLLATE NOCASE,
  role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('admin','member')),
  token_hash TEXT NOT NULL UNIQUE,
  invited_by TEXT NOT NULL REFERENCES users(id),
  expires_at TEXT NOT NULL,
  accepted_at TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS teams (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS team_members (
  team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  PRIMARY KEY(team_id, user_id)
);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  color TEXT NOT NULL DEFAULT 'rust',
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','archived')),
  created_by TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'todo' CHECK(status IN ('todo','in-progress','review','blocked','done')),
  priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
  assignee_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  team_id TEXT REFERENCES teams(id) ON DELETE SET NULL,
  project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
  due_date TEXT,
  estimate REAL,
  created_by TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS task_comments (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity_logs (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  action TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workspace_settings (
  workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
  week_starts_on INTEGER NOT NULL DEFAULT 6,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_workspace_due ON tasks(workspace_id, due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_workspace_status ON tasks(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_activity_workspace_time ON activity_logs(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_invites_token ON invitations(token_hash);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)).hex()
        return hmac.compare_digest(actual, digest_hex)
    except (ValueError, TypeError):
        return False


def log_activity(conn: sqlite3.Connection, workspace_id: str, user_id: str | None,
                 entity_type: str, entity_id: str | None, action: str, message: str) -> None:
    conn.execute(
        "INSERT INTO activity_logs(id,workspace_id,user_id,entity_type,entity_id,action,message,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (new_id(), workspace_id, user_id, entity_type, entity_id, action, message, now_iso()),
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


class InviteInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    role: str = "member"


class CommentInput(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class ProfileInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class OnboardingInput(BaseModel):
    completed: bool = True


app = FastAPI(title="BottleNeck API", version="0.2.1")


@app.on_event("startup")
def startup() -> None:
    init_db()


def create_session(response: Response, user_id: str, workspace_id: str) -> None:
    token = secrets.token_urlsafe(40)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    with db() as conn:
        conn.execute(
            "INSERT INTO sessions(id,user_id,workspace_id,token_hash,expires_at,created_at) VALUES(?,?,?,?,?,?)",
            (new_id(), user_id, workspace_id, hash_token(token), expires.isoformat(), now_iso()),
        )
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_DAYS * 86400, httponly=True,
        secure=COOKIE_SECURE, samesite="lax", path="/",
    )


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


def ensure_workspace_user(conn: sqlite3.Connection, user: dict[str, Any] | None,
                          workspace_id: str, candidate_id: str | None) -> None:
    if not candidate_id:
        return
    row = conn.execute("SELECT id FROM memberships WHERE workspace_id=? AND user_id=?", (workspace_id, candidate_id)).fetchone()
    if not row:
        raise HTTPException(status_code=422, detail="عضو انتخاب‌شده در این فضای کاری حضور ندارد.")


def task_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "title": row["title"], "description": row["description"],
        "status": row["status"], "priority": row["priority"],
        "assigneeId": row["assignee_id"], "teamId": row["team_id"], "projectId": row["project_id"],
        "dueDate": row["due_date"], "estimate": row["estimate"],
        "createdBy": row["created_by"], "createdAt": row["created_at"],
        "updatedAt": row["updated_at"], "completedAt": row["completed_at"],
        "assigneeName": row["assignee_name"], "teamName": row["team_name"], "projectName": row["project_name"],
    }


def get_task(conn: sqlite3.Connection, workspace_id: str, task_id: str) -> sqlite3.Row:
    row = conn.execute(
        """SELECT t.*,u.name AS assignee_name,tm.name AS team_name,p.name AS project_name
           FROM tasks t LEFT JOIN users u ON u.id=t.assignee_id
           LEFT JOIN teams tm ON tm.id=t.team_id LEFT JOIN projects p ON p.id=t.project_id
           WHERE t.id=? AND t.workspace_id=?""", (task_id, workspace_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="کار موردنظر پیدا نشد.")
    return row


def get_workspace_data(workspace_id: str) -> dict[str, Any]:
    with db() as conn:
        tasks = conn.execute(
            """SELECT t.*,u.name AS assignee_name,tm.name AS team_name,p.name AS project_name
               FROM tasks t LEFT JOIN users u ON u.id=t.assignee_id
               LEFT JOIN teams tm ON tm.id=t.team_id LEFT JOIN projects p ON p.id=t.project_id
               WHERE t.workspace_id=? ORDER BY CASE WHEN t.due_date IS NULL THEN 1 ELSE 0 END,t.due_date,t.created_at DESC""",
            (workspace_id,),
        ).fetchall()
        users = conn.execute(
            """SELECT u.id,u.name,u.email,m.role,m.joined_at,
                      (SELECT COUNT(*) FROM tasks t WHERE t.assignee_id=u.id AND t.workspace_id=? AND t.status!='done') AS open_tasks
               FROM users u JOIN memberships m ON m.user_id=u.id
               WHERE m.workspace_id=? ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,u.name""",
            (workspace_id, workspace_id),
        ).fetchall()
        teams = conn.execute("SELECT * FROM teams WHERE workspace_id=? ORDER BY name", (workspace_id,)).fetchall()
        projects = conn.execute("SELECT * FROM projects WHERE workspace_id=? ORDER BY created_at DESC", (workspace_id,)).fetchall()
        activity = conn.execute(
            """SELECT a.*,u.name AS user_name FROM activity_logs a LEFT JOIN users u ON u.id=a.user_id
               WHERE a.workspace_id=? ORDER BY a.created_at DESC LIMIT 80""", (workspace_id,)
        ).fetchall()
        invites = conn.execute(
            "SELECT id,email,role,expires_at,created_at FROM invitations WHERE workspace_id=? AND accepted_at IS NULL AND expires_at>? ORDER BY created_at DESC",
            (workspace_id, now_iso()),
        ).fetchall()
        return {
            "tasks": [task_dict(r) for r in tasks],
            "users": [dict(r) for r in users],
            "teams": [dict(r) for r in teams],
            "projects": [dict(r) for r in projects],
            "activity": [dict(r) for r in activity],
            "invitations": [dict(r) for r in invites],
        }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "application": "BottleNeck", "version": "0.2.1"}


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
            role = invite["role"]
            conn.execute(
                "INSERT INTO users(id,name,email,password_hash,created_at) VALUES(?,?,?,?,?)",
                (user_id, name, email, password_hash(payload.password), now),
            )
            conn.execute(
                "INSERT INTO memberships(id,workspace_id,user_id,role,joined_at) VALUES(?,?,?,?,?)",
                (new_id(), workspace_id, user_id, role, now),
            )
            conn.execute("UPDATE invitations SET accepted_at=? WHERE id=?", (now, invite["id"]))
            log_activity(conn, workspace_id, user_id, "member", user_id, "joined", f"{name} به فضای کار پیوست.")
        else:
            workspace_name = (payload.workspace_name or "فضای کاری من").strip()
            if len(workspace_name) < 2:
                raise HTTPException(status_code=422, detail="نام فضای کار باید دست‌کم دو نویسه باشد.")
            conn.execute(
                "INSERT INTO users(id,name,email,password_hash,created_at) VALUES(?,?,?,?,?)",
                (user_id, name, email, password_hash(payload.password), now),
            )
            conn.execute("INSERT INTO workspaces(id,name,created_by,created_at) VALUES(?,?,?,?)", (workspace_id, workspace_name, user_id, now))
            conn.execute("INSERT INTO memberships(id,workspace_id,user_id,role,joined_at) VALUES(?,?,?,?,?)", (new_id(), workspace_id, user_id, "owner", now))
            conn.execute("INSERT INTO workspace_settings(workspace_id,created_at) VALUES(?,?)", (workspace_id, now))
            team_id = new_id()
            conn.execute("INSERT INTO teams(id,workspace_id,name,description,created_at) VALUES(?,?,?,?,?)", (team_id, workspace_id, "عمومی", "تیم پیش‌فرض فضای کاری", now))
            conn.execute("INSERT INTO team_members(team_id,user_id,created_at) VALUES(?,?,?)", (team_id, user_id, now))
            log_activity(conn, workspace_id, user_id, "workspace", workspace_id, "created", f"فضای کاری «{workspace_name}» ساخته شد.")
    create_session(response, user_id, workspace_id)
    return {"ok": True, "workspaceId": workspace_id}


@app.post("/api/auth/login")
def login(payload: LoginInput, response: Response) -> dict[str, Any]:
    email = valid_email(payload.email)
    with db() as conn:
        row = conn.execute(
            """SELECT u.id,u.password_hash,m.workspace_id FROM users u
               JOIN memberships m ON m.user_id=u.id WHERE u.email=? COLLATE NOCASE
               ORDER BY CASE m.role WHEN 'owner' THEN 0 ELSE 1 END LIMIT 1""", (email,)
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
    return {
        "id": user["user_id"], "name": user["name"], "email": user["email"],
        "role": user["role"], "workspaceId": user["workspace_id"],
        "workspaceName": user["workspace_name"], "onboardingCompleted": bool(user["onboarding_completed"]),
    }


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
    return {"me": {
        "id": user["user_id"], "name": user["name"], "email": user["email"], "role": user["role"],
        "workspaceId": user["workspace_id"], "workspaceName": user["workspace_name"],
        "onboardingCompleted": bool(user["onboarding_completed"]),
    }, **get_workspace_data(user["workspace_id"])}


@app.post("/api/tasks")
def create_task(payload: TaskInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if payload.status not in STATUSES or payload.priority not in PRIORITIES:
        raise HTTPException(status_code=422, detail="وضعیت یا اولویت انتخاب‌شده معتبر نیست.")
    now = now_iso()
    task_id = new_id()
    with db() as conn:
        ensure_workspace_user(conn, user, user["workspace_id"], payload.assignee_id)
        if payload.team_id and not conn.execute("SELECT id FROM teams WHERE id=? AND workspace_id=?", (payload.team_id, user["workspace_id"])).fetchone():
            raise HTTPException(status_code=422, detail="تیم انتخاب‌شده معتبر نیست.")
        if payload.project_id and not conn.execute("SELECT id FROM projects WHERE id=? AND workspace_id=?", (payload.project_id, user["workspace_id"])).fetchone():
            raise HTTPException(status_code=422, detail="پروژه انتخاب‌شده معتبر نیست.")
        completed = now if payload.status == "done" else None
        conn.execute(
            """INSERT INTO tasks(id,workspace_id,title,description,status,priority,assignee_id,team_id,project_id,due_date,estimate,created_by,created_at,updated_at,completed_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (task_id,user["workspace_id"],payload.title.strip(),payload.description.strip(),payload.status,payload.priority,
             payload.assignee_id or None,payload.team_id or None,payload.project_id or None,payload.due_date or None,payload.estimate,
             user["user_id"],now,now,completed),
        )
        log_activity(conn,user["workspace_id"],user["user_id"],"task",task_id,"created",f"کار «{payload.title.strip()}» ایجاد شد.")
        row = get_task(conn, user["workspace_id"], task_id)
    return task_dict(row)


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, payload: TaskInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if payload.status not in STATUSES or payload.priority not in PRIORITIES:
        raise HTTPException(status_code=422, detail="وضعیت یا اولویت انتخاب‌شده معتبر نیست.")
    now = now_iso()
    with db() as conn:
        old = get_task(conn, user["workspace_id"], task_id)
        ensure_workspace_user(conn, user, user["workspace_id"], payload.assignee_id)
        if payload.team_id and not conn.execute("SELECT id FROM teams WHERE id=? AND workspace_id=?", (payload.team_id, user["workspace_id"])).fetchone():
            raise HTTPException(status_code=422, detail="تیم انتخاب‌شده معتبر نیست.")
        if payload.project_id and not conn.execute("SELECT id FROM projects WHERE id=? AND workspace_id=?", (payload.project_id, user["workspace_id"])).fetchone():
            raise HTTPException(status_code=422, detail="پروژه انتخاب‌شده معتبر نیست.")
        completed = old["completed_at"]
        if payload.status == "done" and not completed:
            completed = now
        elif payload.status != "done":
            completed = None
        conn.execute(
            """UPDATE tasks SET title=?,description=?,status=?,priority=?,assignee_id=?,team_id=?,project_id=?,due_date=?,estimate=?,updated_at=?,completed_at=?
               WHERE id=? AND workspace_id=?""",
            (payload.title.strip(),payload.description.strip(),payload.status,payload.priority,payload.assignee_id or None,
             payload.team_id or None,payload.project_id or None,payload.due_date or None,payload.estimate,now,completed,task_id,user["workspace_id"]),
        )
        action = "status_changed" if old["status"] != payload.status else "updated"
        msg = f"وضعیت کار «{payload.title.strip()}» تغییر کرد." if action == "status_changed" else f"کار «{payload.title.strip()}» ویرایش شد."
        log_activity(conn,user["workspace_id"],user["user_id"],"task",task_id,action,msg)
        row = get_task(conn, user["workspace_id"], task_id)
    return task_dict(row)


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        row = get_task(conn, user["workspace_id"], task_id)
        if user["role"] == "member" and row["created_by"] != user["user_id"]:
            raise HTTPException(status_code=403, detail="فقط سازنده کار یا مدیر می‌تواند آن را حذف کند.")
        conn.execute("DELETE FROM tasks WHERE id=? AND workspace_id=?", (task_id,user["workspace_id"]))
        log_activity(conn,user["workspace_id"],user["user_id"],"task",task_id,"deleted",f"کار «{row['title']}» حذف شد.")
    return {"ok": True}


@app.get("/api/tasks/{task_id}/comments")
def list_comments(task_id: str, user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as conn:
        get_task(conn, user["workspace_id"], task_id)
        rows = conn.execute(
            """SELECT c.id,c.body,c.created_at,u.id AS user_id,u.name AS user_name
               FROM task_comments c JOIN users u ON u.id=c.user_id WHERE c.task_id=? ORDER BY c.created_at""", (task_id,)
        ).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/tasks/{task_id}/comments")
def add_comment(task_id: str, payload: CommentInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        task = get_task(conn, user["workspace_id"], task_id)
        comment_id, now = new_id(), now_iso()
        body = payload.body.strip()
        conn.execute("INSERT INTO task_comments(id,task_id,user_id,body,created_at) VALUES(?,?,?,?,?)", (comment_id,task_id,user["user_id"],body,now))
        log_activity(conn,user["workspace_id"],user["user_id"],"task",task_id,"commented",f"برای کار «{task['title']}» یادداشتی ثبت شد.")
        return {"id":comment_id,"body":body,"created_at":now,"user_id":user["user_id"],"user_name":user["name"]}


@app.post("/api/projects")
def create_project(payload: ProjectInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    project_id, now = new_id(), now_iso()
    with db() as conn:
        conn.execute("INSERT INTO projects(id,workspace_id,name,description,color,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                     (project_id,user["workspace_id"],payload.name.strip(),payload.description.strip(),payload.color,user["user_id"],now,now))
        log_activity(conn,user["workspace_id"],user["user_id"],"project",project_id,"created",f"پروژه «{payload.name.strip()}» ایجاد شد.")
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(row)


@app.patch("/api/projects/{project_id}")
def update_project(project_id: str, payload: ProjectInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    now = now_iso()
    with db() as conn:
        exists = conn.execute("SELECT id FROM projects WHERE id=? AND workspace_id=?", (project_id,user["workspace_id"])).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="پروژه پیدا نشد.")
        conn.execute("UPDATE projects SET name=?,description=?,color=?,updated_at=? WHERE id=?", (payload.name.strip(),payload.description.strip(),payload.color,now,project_id))
        log_activity(conn,user["workspace_id"],user["user_id"],"project",project_id,"updated",f"پروژه «{payload.name.strip()}» ویرایش شد.")
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(row)


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, user: dict[str, Any] = Depends(require_admin)) -> dict[str, bool]:
    with db() as conn:
        row = conn.execute("SELECT name FROM projects WHERE id=? AND workspace_id=?", (project_id,user["workspace_id"])).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="پروژه پیدا نشد.")
        conn.execute("UPDATE tasks SET project_id=NULL WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        log_activity(conn,user["workspace_id"],user["user_id"],"project",project_id,"deleted",f"پروژه «{row['name']}» حذف شد.")
    return {"ok": True}


@app.post("/api/teams")
def create_team(payload: TeamInput, user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    team_id, now = new_id(), now_iso()
    with db() as conn:
        conn.execute("INSERT INTO teams(id,workspace_id,name,description,created_at) VALUES(?,?,?,?,?)", (team_id,user["workspace_id"],payload.name.strip(),payload.description.strip(),now))
        log_activity(conn,user["workspace_id"],user["user_id"],"team",team_id,"created",f"تیم «{payload.name.strip()}» ایجاد شد.")
        return dict(conn.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone())


@app.post("/api/invitations")
def create_invitation(payload: InviteInput, user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    email = valid_email(payload.email)
    role = payload.role if payload.role in {"admin", "member"} else "member"
    with db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        if existing:
            already_member = conn.execute("SELECT id FROM memberships WHERE user_id=? AND workspace_id=?", (existing["id"],user["workspace_id"])).fetchone()
            if already_member:
                raise HTTPException(status_code=409, detail="این کاربر هم‌اکنون عضو فضای کار است.")
            raise HTTPException(status_code=409, detail="این ایمیل از قبل حساب دارد. در این نسخه هر حساب فقط به یک فضای کاری متصل می‌شود.")
        invite = conn.execute("SELECT id FROM invitations WHERE workspace_id=? AND email=? COLLATE NOCASE AND accepted_at IS NULL AND expires_at>?", (user["workspace_id"],email,now_iso())).fetchone()
        if invite:
            raise HTTPException(status_code=409, detail="برای این ایمیل دعوت فعال وجود دارد.")
        raw_token = secrets.token_urlsafe(28)
        invite_id, now = new_id(), now_iso()
        expires = (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0).isoformat()
        conn.execute("INSERT INTO invitations(id,workspace_id,email,role,token_hash,invited_by,expires_at,created_at) VALUES(?,?,?,?,?,?,?,?)",
                     (invite_id,user["workspace_id"],email,role,hash_token(raw_token),user["user_id"],expires,now))
        log_activity(conn,user["workspace_id"],user["user_id"],"invitation",invite_id,"created",f"دعوت‌نامه‌ای برای {email} ایجاد شد.")
    return {"id":invite_id,"email":email,"role":role,"inviteCode":raw_token,"expiresAt":expires}


@app.delete("/api/invitations/{invitation_id}")
def revoke_invitation(invitation_id: str, user: dict[str, Any] = Depends(require_admin)) -> dict[str, bool]:
    with db() as conn:
        cur = conn.execute("DELETE FROM invitations WHERE id=? AND workspace_id=? AND accepted_at IS NULL", (invitation_id,user["workspace_id"]))
        if not cur.rowcount:
            raise HTTPException(status_code=404, detail="دعوت‌نامه پیدا نشد.")
        log_activity(conn,user["workspace_id"],user["user_id"],"invitation",invitation_id,"revoked","یک دعوت‌نامه لغو شد.")
    return {"ok": True}


@app.api_route("/", methods=["GET", "HEAD"])
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")


app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")
