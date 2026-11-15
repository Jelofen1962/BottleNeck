from __future__ import annotations

import hashlib
import asyncio
import base64
import struct
import smtplib
import zipfile
import tempfile
import time
from email.message import EmailMessage
import hmac
import ipaddress
import json
import calendar
import csv
import io
import logging
import mimetypes
import os
import re
import secrets
import shutil
import socket
import sqlite3
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from logging.handlers import RotatingFileHandler

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("BOTTLENECK_DB", BASE_DIR / "data" / "bottleneck.sqlite3"))
UPLOAD_DIR = Path(os.getenv("BOTTLENECK_UPLOAD_DIR", BASE_DIR / "data" / "uploads"))
SHARED_DIR = Path(os.getenv("BOTTLENECK_SHARED_DIR", DB_PATH.parent / "shared"))
BACKUP_DIR = Path(os.getenv("BOTTLENECK_BACKUP_DIR", BASE_DIR / "backups"))
COOKIE_NAME = "bottleneck_session"
SESSION_DAYS = int(os.getenv("BOTTLENECK_SESSION_DAYS", "14"))
COOKIE_SECURE = os.getenv("BOTTLENECK_COOKIE_SECURE", "0") == "1"
PBKDF2_ITERATIONS = 310_000
APP_VERSION = "1.1.0"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_AVATAR_BYTES = 3 * 1024 * 1024
AVATAR_DIR = UPLOAD_DIR / "avatars"
MAX_SHARED_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_CHAT_UPLOAD_BYTES = 25 * 1024 * 1024
CHAT_DIR = DB_PATH.parent / "chat_uploads"
CHAT_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".txt", ".md", ".csv", ".zip", ".mp3", ".wav", ".m4a", ".ogg", ".oga", ".webm", ".mp4", ".mov", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".json"}
SHARED_FILE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".txt", ".md", ".csv", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".json", ".svg"}
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".txt", ".csv", ".doc", ".docx", ".xls", ".xlsx", ".zip"}
STATUSES = {"todo", "in-progress", "review", "blocked", "done"}
PRIORITIES = {"low", "medium", "high", "urgent"}
ROLES = {"owner", "admin", "member"}
SCHEMA = (BASE_DIR / "schema.sql").read_text(encoding="utf-8")
PROCESS_STARTED_AT = datetime.now(timezone.utc)
SERVER_LOG_DIR = BASE_DIR / "logs"
SERVER_LOG_DIR.mkdir(parents=True, exist_ok=True)
SERVER_LOG_PATH = SERVER_LOG_DIR / "server.log"
_server_logger = logging.getLogger("bottleneck.server")
if not _server_logger.handlers:
    _handler = RotatingFileHandler(SERVER_LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _server_logger.addHandler(_handler)
    _server_logger.setLevel(logging.INFO)


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


def enforce_rate_limit(request: Request, scope: str, subject: str, limit: int, window_seconds: int) -> None:
    """Apply a persistent per-IP/per-subject limit to authentication endpoints.

    The bucket key is hashed so the table does not retain raw IP addresses or email addresses.
    """
    client_ip = request.client.host if request.client else "unknown"
    bucket_key = hashlib.sha256(f"{scope}\0{client_ip}\0{subject.casefold()}".encode("utf-8")).hexdigest()
    current = datetime.now(timezone.utc)
    current_iso = current.isoformat()
    blocked_for = 0
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT window_started_at,hits FROM auth_rate_limits WHERE bucket_key=?", (bucket_key,)).fetchone()
        window_start = None
        if row:
            try:
                window_start = datetime.fromisoformat(row["window_started_at"])
            except (TypeError, ValueError):
                window_start = None
        if not row or not window_start or (current - window_start).total_seconds() >= window_seconds:
            conn.execute("""INSERT INTO auth_rate_limits(bucket_key,window_started_at,hits,updated_at)
                VALUES(?,?,1,?) ON CONFLICT(bucket_key) DO UPDATE SET
                window_started_at=excluded.window_started_at,hits=1,updated_at=excluded.updated_at""",
                (bucket_key, current_iso, current_iso))
        else:
            hits = int(row["hits"]) + 1
            conn.execute("UPDATE auth_rate_limits SET hits=?,updated_at=? WHERE bucket_key=?", (hits, current_iso, bucket_key))
            if hits > limit:
                blocked_for = max(1, int(window_seconds - (current - window_start).total_seconds()))
        # Keep old buckets bounded. The indexed timestamp makes this inexpensive
        # for the small authentication table and avoids a separate cleanup worker.
        cutoff = (current - timedelta(hours=24)).isoformat()
        conn.execute("DELETE FROM auth_rate_limits WHERE updated_at<?", (cutoff,))
    if blocked_for:
        raise HTTPException(status_code=429, detail="تعداد درخواست‌ها بیش از حد مجاز است؛ کمی بعد دوباره تلاش کنید.",
                            headers={"Retry-After": str(blocked_for)})


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
        conn.execute("""CREATE TABLE IF NOT EXISTS workspace_join_links (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('admin','member')),
            token_hash TEXT NOT NULL UNIQUE,
            created_by TEXT NOT NULL REFERENCES users(id),
            expires_at TEXT NOT NULL,
            max_uses INTEGER NOT NULL DEFAULT 0,
            use_count INTEGER NOT NULL DEFAULT 0,
            revoked_at TEXT,
            created_at TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workspace_join_links_active ON workspace_join_links(workspace_id, revoked_at, expires_at)")
        challenge_columns = {r["name"] for r in conn.execute("PRAGMA table_info(login_challenges)").fetchall()}
        if "attempts" not in challenge_columns:
            conn.execute("ALTER TABLE login_challenges ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        if "remember_me" not in challenge_columns:
            conn.execute("ALTER TABLE login_challenges ADD COLUMN remember_me INTEGER NOT NULL DEFAULT 0")
        user_columns = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "avatar_key" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_key TEXT")
        if "avatar_updated_at" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_updated_at TEXT")
        membership_columns = {r["name"] for r in conn.execute("PRAGMA table_info(memberships)").fetchall()}
        if "custom_role_id" not in membership_columns:
            conn.execute("ALTER TABLE memberships ADD COLUMN custom_role_id TEXT")
        presence_columns = {r["name"] for r in conn.execute("PRAGMA table_info(workspace_presence)").fetchall()}
        for column, declaration in {
            "active_team_id": "TEXT", "cursor_x_pct": "REAL", "cursor_y_pct": "REAL",
            "cursor_page": "TEXT", "cursor_color": "TEXT"
        }.items():
            if column not in presence_columns:
                conn.execute(f"ALTER TABLE workspace_presence ADD COLUMN {column} {declaration}")
        chat_columns = {r["name"] for r in conn.execute("PRAGMA table_info(chat_messages)").fetchall()}
        for column, declaration in {
            "reply_to_id": "TEXT", "edited_at": "TEXT", "deleted_at": "TEXT",
            "resource_type": "TEXT", "resource_id": "TEXT"
        }.items():
            if column not in chat_columns:
                conn.execute(f"ALTER TABLE chat_messages ADD COLUMN {column} {declaration}")
        conn.executescript("""
          CREATE TABLE IF NOT EXISTS chat_attachments (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            uploaded_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            channel_type TEXT NOT NULL CHECK(channel_type IN ('workspace','team')),
            team_id TEXT REFERENCES teams(id) ON DELETE CASCADE,
            message_id TEXT REFERENCES chat_messages(id) ON DELETE CASCADE,
            original_name TEXT NOT NULL, stored_name TEXT NOT NULL, content_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL, created_at TEXT NOT NULL
          );
          CREATE INDEX IF NOT EXISTS idx_chat_attachments_message ON chat_attachments(message_id);
          CREATE INDEX IF NOT EXISTS idx_chat_attachments_staging ON chat_attachments(uploaded_by,message_id,created_at);
          CREATE TABLE IF NOT EXISTS chat_message_mentions (
            message_id TEXT NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY(message_id,user_id)
          );
          CREATE INDEX IF NOT EXISTS idx_chat_mentions_user ON chat_message_mentions(user_id,message_id);
        """)
        conn.executescript("""
          CREATE TABLE IF NOT EXISTS workspace_custom_roles (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#4e574e', base_role TEXT NOT NULL DEFAULT 'member' CHECK(base_role IN ('admin','member')),
            created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
            UNIQUE(workspace_id,name)
          );
          UPDATE workspace_custom_roles SET color='#4e574e' WHERE lower(color)='#8b6bb1';
          CREATE TABLE IF NOT EXISTS workspace_custom_role_permissions (
            workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            role_id TEXT NOT NULL REFERENCES workspace_custom_roles(id) ON DELETE CASCADE,
            permission_key TEXT NOT NULL, allowed INTEGER NOT NULL DEFAULT 0,
            updated_by TEXT REFERENCES users(id) ON DELETE SET NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(role_id,permission_key)
          );
          CREATE TABLE IF NOT EXISTS workspace_join_codes (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('admin','member')),
            token_hash TEXT NOT NULL UNIQUE, created_by TEXT NOT NULL REFERENCES users(id),
            expires_at TEXT NOT NULL, max_uses INTEGER NOT NULL DEFAULT 1, use_count INTEGER NOT NULL DEFAULT 0,
            revoked_at TEXT, created_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS join_code_attempts (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            window_started TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0
          );
          CREATE INDEX IF NOT EXISTS idx_join_codes_active ON workspace_join_codes(workspace_id,revoked_at,expires_at);
        """)
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
        conn.executescript("""
          CREATE TABLE IF NOT EXISTS server_instance (
            id INTEGER PRIMARY KEY CHECK(id=1), install_id TEXT NOT NULL,
            owner_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            initialized_at TEXT NOT NULL, version TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS server_admins (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('owner','operator','auditor')),
            enabled INTEGER NOT NULL DEFAULT 1,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS server_settings (
            setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL,
            updated_by TEXT REFERENCES users(id) ON DELETE SET NULL, updated_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS server_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            action TEXT NOT NULL, target TEXT NOT NULL DEFAULT '',
            details_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
          );
          CREATE INDEX IF NOT EXISTS idx_server_audit_created ON server_audit_logs(created_at DESC);
        """)
        instance = conn.execute("SELECT id FROM server_instance WHERE id=1").fetchone()
        if not instance:
            first = conn.execute("SELECT id,created_by FROM workspaces ORDER BY rowid LIMIT 1").fetchone()
            owner_id = first["created_by"] if first else None
            conn.execute("INSERT INTO server_instance(id,install_id,owner_user_id,initialized_at,version) VALUES(1,?,?,?,?)",
                         (str(uuid.uuid4()), owner_id, now_iso(), APP_VERSION))
        # Backward-compatible elevation: the creator of the first workspace was
        # the instance administrator in earlier MVP releases.
        first_workspace = conn.execute("SELECT created_by FROM workspaces ORDER BY rowid LIMIT 1").fetchone()
        if first_workspace and first_workspace["created_by"]:
            conn.execute("INSERT OR IGNORE INTO server_admins(user_id,role,enabled,created_by,created_at) VALUES(?,'owner',1,?,?)",
                         (first_workspace["created_by"], first_workspace["created_by"], now_iso()))
            conn.execute("UPDATE server_instance SET owner_user_id=COALESCE(owner_user_id,?) WHERE id=1", (first_workspace["created_by"],))
        conn.execute("UPDATE server_instance SET version=? WHERE id=1", (APP_VERSION,))
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    CHAT_DIR.mkdir(parents=True, exist_ok=True)


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
    notification_id = new_id()
    conn.execute(
        """INSERT INTO notifications(id,workspace_id,user_id,actor_id,kind,title,body,entity_type,entity_id,is_read,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,0,?)""",
        (notification_id, workspace_id, recipient_id, actor_id, kind, title, body, entity_type, entity_id, now_iso()),
    )
    prefs = conn.execute("SELECT email_enabled FROM notification_preferences WHERE user_id=?", (recipient_id,)).fetchone()
    if prefs and prefs["email_enabled"]:
        conn.execute("INSERT OR IGNORE INTO notification_email_jobs(id,notification_id,user_id,created_at) VALUES(?,?,?,?)",
                     (new_id(), notification_id, recipient_id, now_iso()))


class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=200)
    workspace_name: str | None = Field(default=None, max_length=100)
    invite_code: str | None = None
    join_token: str | None = None


class LoginInput(BaseModel):
    email: str
    password: str
    remember_me: bool = False


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


class BoardInput(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=3000)
    access_mode: str = "workspace"
    team_id: str | None = None
    password: str | None = Field(default=None, max_length=200)


class BoardItemInput(BaseModel):
    item_type: str = "note"
    title: str = Field(default="", max_length=180)
    content: str = Field(default="", max_length=12000)
    url: str = Field(default="", max_length=1000)
    task_id: str | None = None
    x: float = Field(default=24, ge=0, le=10000)
    y: float = Field(default=24, ge=0, le=10000)
    width: float = Field(default=260, ge=180, le=620)
    color: str = "butter"


class DriveNodeInput(BaseModel):
    node_type: str = "folder"
    title: str = Field(min_length=1, max_length=180)
    content: str = Field(default="", max_length=100000)
    parent_id: str | None = None
    access_mode: str = "workspace"
    team_id: str | None = None
    password: str | None = Field(default=None, max_length=200)
    parent_password: str | None = Field(default=None, max_length=200)


class DriveNodeUpdateInput(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    content: str | None = Field(default=None, max_length=100000)
    access_mode: str | None = None
    team_id: str | None = None
    password: str | None = Field(default=None, max_length=200)


class ChatMessageInput(BaseModel):
    body: str = Field(default="", max_length=10000)
    channel_type: str = "workspace"
    team_id: str | None = None
    attachment_id: str | None = None
    reply_to_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    mentions: list[str] = Field(default_factory=list, max_length=50)


class ChatMessageEditInput(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    mentions: list[str] = Field(default_factory=list, max_length=50)


class PresenceInput(BaseModel):
    page: str = Field(default="overview", max_length=50)
    team_id: str | None = None


class CursorInput(BaseModel):
    page: str = Field(default="overview", max_length=50)
    team_id: str | None = None
    x_pct: float = Field(ge=0, le=100)
    y_pct: float = Field(ge=0, le=100)


class JoinCodeCreateInput(BaseModel):
    role: str = "member"
    max_uses: int = Field(default=1, ge=1, le=100)


class JoinCodeAcceptInput(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class CustomRoleCreateInput(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    color: str = Field(default="#4e574e", pattern=r"^#[0-9a-fA-F]{6}$")
    base_role: str = "member"
    permissions: list[str] = Field(default_factory=list, max_length=80)


class CustomRolePermissionsInput(BaseModel):
    permissions: list[str] = Field(default_factory=list, max_length=80)


class MemberRoleInput(BaseModel):
    role: str = "member"
    custom_role_id: str | None = None


class WorkspaceCreateInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class WorkspaceSwitchInput(BaseModel):
    workspace_id: str


class WorkspaceJoinLinkInput(BaseModel):
    role: str = "member"
    expires_days: int = Field(default=7, ge=1, le=90)
    max_uses: int = Field(default=0, ge=0, le=500)


class LinkTokenInput(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class TotpVerifyInput(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class TotpDisableInput(BaseModel):
    password: str
    code: str = Field(min_length=6, max_length=8)


class PasswordResetRequestInput(BaseModel):
    email: str


class PasswordResetCompleteInput(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=200)


class RolePermissionItem(BaseModel):
    role: str
    permission: str
    allowed: bool


class RolePermissionsInput(BaseModel):
    items: list[RolePermissionItem] = Field(min_length=1, max_length=100)


class NodeAclItem(BaseModel):
    role: str
    can_read: bool = True
    can_write: bool = False


class NodeAclInput(BaseModel):
    items: list[NodeAclItem] = Field(max_length=3)


class NotificationPreferencesInput(BaseModel):
    email_enabled: bool = False
    assigned_enabled: bool = True
    mentions_enabled: bool = True
    deadlines_enabled: bool = True


RUNTIME_ENV = os.getenv("BOTTLENECK_ENV", "development").strip().lower()
API_DOCS_ENABLED = os.getenv("BOTTLENECK_ENABLE_API_DOCS", "0" if RUNTIME_ENV == "production" else "1") == "1"
_background_tasks: list[asyncio.Task] = []
_background_stop: asyncio.Event | None = None


@asynccontextmanager
async def app_lifespan(application: FastAPI):
    init_db()
    _seed_all_workspace_permissions()
    global _background_stop
    _background_stop = asyncio.Event()
    _background_tasks.extend([
        asyncio.create_task(_recurring_scheduler(), name="bottleneck-recurring"),
        asyncio.create_task(_backup_scheduler(), name="bottleneck-backups"),
        asyncio.create_task(_notification_mailer(), name="bottleneck-email"),
    ])
    if RUNTIME_ENV == "production" and not COOKIE_SECURE:
        _server_logger.warning("security_cookie_secure_disabled environment=production; use HTTPS before exposing outside a trusted LAN")
    try:
        yield
    finally:
        if _background_stop:
            _background_stop.set()
        for task in _background_tasks:
            task.cancel()
        if _background_tasks:
            await asyncio.gather(*_background_tasks, return_exceptions=True)
        _background_tasks.clear()


app = FastAPI(
    title="BottleNeck API",
    version=APP_VERSION,
    docs_url="/api/docs" if API_DOCS_ENABLED else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if API_DOCS_ENABLED else None,
    lifespan=app_lifespan,
)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    started = time.monotonic()
    if request.url.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        fetch_site = request.headers.get("sec-fetch-site", "").lower()
        if fetch_site == "cross-site":
            return JSONResponse({"detail": "Cross-site state-changing requests are not accepted."}, status_code=403)
        origin = request.headers.get("origin")
        if origin:
            parsed = urlsplit(origin)
            supplied_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/").lower()
            request_origin = f"{request.url.scheme}://{request.headers.get('host', request.url.netloc)}".rstrip("/").lower()
            configured_origins = {item.strip().rstrip("/").lower() for item in os.getenv("BOTTLENECK_ALLOWED_ORIGINS", "").split(",") if item.strip()}
            if not parsed.scheme or not parsed.netloc or parsed.path not in {"", "/"} or (supplied_origin != request_origin and supplied_origin not in configured_origins):
                return JSONResponse({"detail": "Request origin is not allowed."}, status_code=403)
    try:
        response = await call_next(request)
    except Exception:
        _server_logger.exception("http_error method=%s path=%s", request.method, request.url.path)
        raise
    if request.url.path.startswith("/api/") and response.status_code >= 400:
        _server_logger.warning("http_response status=%s method=%s path=%s duration_ms=%s", response.status_code, request.method,
                               request.url.path, int((time.monotonic()-started)*1000))
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'; object-src 'none'; "
        "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob:; "
        "media-src 'self' blob:; connect-src 'self' ws: wss:"
    )
    if request.url.path == "/" or request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

def create_session(response: Response, user_id: str, workspace_id: str, remember_me: bool = False) -> None:
    token = secrets.token_urlsafe(40)
    lifetime = timedelta(days=30) if remember_me else timedelta(hours=12)
    expires = datetime.now(timezone.utc) + lifetime
    with db() as conn:
        conn.execute(
            "INSERT INTO sessions(id,user_id,workspace_id,token_hash,expires_at,created_at) VALUES(?,?,?,?,?,?)",
            (new_id(), user_id, workspace_id, hash_token(token), expires.isoformat(), now_iso()),
        )
    cookie_options = {"httponly": True, "secure": COOKIE_SECURE, "samesite": "lax", "path": "/"}
    if remember_me:
        cookie_options["max_age"] = 30 * 86400
    response.set_cookie(COOKIE_NAME, token, **cookie_options)


def get_context(request: Request) -> dict[str, Any]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="برای ادامه وارد حساب کاربری شوید.")
    with db() as conn:
        row = conn.execute(
            """SELECT s.id AS session_id,s.user_id,s.workspace_id,s.expires_at,
                      u.name,u.email,u.onboarding_completed,u.avatar_key,u.avatar_updated_at,
                      w.name AS workspace_name,m.role,m.custom_role_id,
                      cr.name AS custom_role_name,cr.color AS custom_role_color
               FROM sessions s JOIN users u ON u.id=s.user_id
               JOIN workspaces w ON w.id=s.workspace_id
               JOIN memberships m ON m.user_id=s.user_id AND m.workspace_id=s.workspace_id
               LEFT JOIN workspace_custom_roles cr ON cr.id=m.custom_role_id
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


def has_permission(user: dict[str, Any], permission: str) -> bool:
    if user.get("role") == "owner":
        return True
    with db() as conn:
        if user.get("custom_role_id"):
            row = conn.execute("SELECT allowed FROM workspace_custom_role_permissions WHERE workspace_id=? AND role_id=? AND permission_key=?",
                               (user["workspace_id"], user["custom_role_id"], permission)).fetchone()
            if row is not None:
                return bool(row["allowed"])
            base = conn.execute("SELECT base_role FROM workspace_custom_roles WHERE id=? AND workspace_id=?",
                                (user["custom_role_id"], user["workspace_id"])).fetchone()
            fallback_role = base["base_role"] if base else "member"
        else:
            fallback_role = user.get("role", "member")
        row = conn.execute("SELECT allowed FROM workspace_role_permissions WHERE workspace_id=? AND role=? AND permission_key=?",
                           (user["workspace_id"], fallback_role, permission)).fetchone()
    if row is not None:
        return bool(row["allowed"])
    return fallback_role == "admin" and permission in {"workspace.manage", "members.invite", "members.manage", "teams.manage", "backups.manage", "permissions.manage"}


def permissions_for_user(user: dict[str, Any]) -> list[str]:
    """Return the effective workspace permission set for the current membership."""
    if user.get("role") == "owner":
        return sorted(PERMISSION_KEYS)
    with db() as conn:
        if user.get("custom_role_id"):
            rows = conn.execute(
                "SELECT permission_key,allowed FROM workspace_custom_role_permissions WHERE workspace_id=? AND role_id=?",
                (user["workspace_id"], user["custom_role_id"]),
            ).fetchall()
            # A custom role with an explicit all-deny matrix must stay empty;
            # do not silently fall back to its base role just because no key is allowed.
            if rows:
                return sorted(r["permission_key"] for r in rows if r["allowed"])
            base = conn.execute("SELECT base_role FROM workspace_custom_roles WHERE id=? AND workspace_id=?",
                                (user["custom_role_id"], user["workspace_id"])).fetchone()
            role = base["base_role"] if base else "member"
        else:
            role = user.get("role", "member")
        rows = conn.execute("SELECT permission_key FROM workspace_role_permissions WHERE workspace_id=? AND role=? AND allowed=1",
                            (user["workspace_id"], role)).fetchall()
    if rows:
        return sorted(r["permission_key"] for r in rows)
    return sorted(DEFAULT_ROLE_PERMISSIONS.get(role, set()))


def require_admin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if not has_permission(user, "workspace.manage"):
        raise HTTPException(status_code=403, detail="این عملیات به مجوز مدیریت فضای کار نیاز دارد.")
    return user


def require_permission(permission: str):
    def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if not has_permission(user, permission):
            raise HTTPException(status_code=403, detail="نقش شما مجوز انجام این عملیات را ندارد.")
        return user
    return dependency


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
            """SELECT u.id,u.name,u.email,m.role,m.custom_role_id,cr.name AS role_name,cr.color AS role_color,
               u.avatar_key,u.avatar_updated_at,m.joined_at,
               (SELECT COUNT(DISTINCT ta.task_id) FROM task_assignees ta JOIN tasks t ON t.id=ta.task_id
                 WHERE ta.user_id=u.id AND t.workspace_id=? AND t.status!='done') AS open_tasks
               FROM users u JOIN memberships m ON m.user_id=u.id
               LEFT JOIN workspace_custom_roles cr ON cr.id=m.custom_role_id
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
        join_links = conn.execute(
            """SELECT id,role,expires_at,max_uses,use_count,created_at FROM workspace_join_links
               WHERE workspace_id=? AND revoked_at IS NULL AND expires_at>? ORDER BY created_at DESC""",
            (workspace_id, now_iso())
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
            "users": [{**dict(r), "avatarUrl": f"/api/users/{r['id']}/avatar?v={r['avatar_updated_at'] or ''}" if r['avatar_key'] else None,
                       "roleName": r['role_name'] or {"owner":"مالک","admin":"مدیر","member":"عضو"}.get(r['role'],"عضو")}
                      for r in users],
            "customRoles": [dict(r) for r in conn.execute("SELECT r.id,r.name,r.color,r.base_role,r.created_at,COUNT(p.permission_key) AS permission_count FROM workspace_custom_roles r LEFT JOIN workspace_custom_role_permissions p ON p.role_id=r.id WHERE r.workspace_id=? GROUP BY r.id ORDER BY r.name", (workspace_id,)).fetchall()],
            "teams": teams,
            "projects": [dict(r) for r in projects],
            "activity": [dict(r) for r in activity],
            "invitations": [dict(r) for r in invitations],
            "joinLinks": [dict(r) for r in join_links],
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
    port = int(_server_setting("bind_port", os.getenv("BOTTLENECK_PORT") or "1939"))
    scheme = "https" if request.url.scheme == "https" else "http"
    return {"host": host, "port": port, "lanIps": ips, "urls": [f"{scheme}://{ip}:{port}" for ip in ips]}


@app.post("/api/auth/register")
def register(payload: RegisterInput, response: Response, request: Request) -> dict[str, Any]:
    enforce_rate_limit(request, "register-ip", "all", 8, 3600)
    email = valid_email(payload.email)
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="نام باید دست‌کم دو نویسه باشد.")
    user_id, workspace_id = new_id(), new_id()
    now = now_iso()
    with db() as conn:
        existing_user = conn.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        if existing_user:
            if payload.join_token or payload.invite_code:
                raise HTTPException(status_code=409, detail="این ایمیل از قبل حساب دارد؛ از بخش ورود وارد شوید و سپس لینک عضویت را باز کنید.")
            raise HTTPException(status_code=409, detail="با این ایمیل قبلاً حساب ساخته شده است؛ وارد حساب خود شوید.")

        join_link = None
        invite = None
        if payload.join_token:
            join_link = conn.execute(
                "SELECT * FROM workspace_join_links WHERE token_hash=? AND revoked_at IS NULL AND expires_at>?",
                (hash_token(payload.join_token), now),
            ).fetchone()
            if not join_link or (int(join_link["max_uses"]) > 0 and int(join_link["use_count"]) >= int(join_link["max_uses"])):
                raise HTTPException(status_code=400, detail="لینک عضویت معتبر نیست، لغو شده یا ظرفیت آن تکمیل شده است.")
            workspace_id = join_link["workspace_id"]
        elif payload.invite_code:
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
        conn.execute("INSERT OR IGNORE INTO notification_preferences(user_id,updated_at) VALUES(?,?)", (user_id, now))

        if join_link:
            conn.execute("INSERT INTO memberships(id,workspace_id,user_id,role,joined_at) VALUES(?,?,?,?,?)",
                         (new_id(), workspace_id, user_id, join_link["role"], now))
            changed = conn.execute(
                "UPDATE workspace_join_links SET use_count=use_count+1 WHERE id=? AND revoked_at IS NULL AND expires_at>? AND (max_uses=0 OR use_count<max_uses)",
                (join_link["id"], now),
            )
            if changed.rowcount != 1:
                raise HTTPException(status_code=409, detail="ظرفیت لینک عضویت در همین لحظه تکمیل شد؛ از مدیر فضای کار لینک تازه بگیرید.")
            default_team = conn.execute("SELECT id FROM teams WHERE workspace_id=? ORDER BY created_at LIMIT 1", (workspace_id,)).fetchone()
            if default_team:
                conn.execute("INSERT OR IGNORE INTO team_members(team_id,user_id,created_at) VALUES(?,?,?)", (default_team["id"], user_id, now))
            log_activity(conn, workspace_id, user_id, "member", user_id, "joined", f"{name} با لینک امن به فضای کار پیوست.")
            owner = conn.execute("SELECT created_by FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
            if owner:
                create_notification(conn, workspace_id, owner["created_by"], user_id, "member", "عضو جدید به فضای کار پیوست", name, "member", user_id)
        elif invite:
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
            for role, allowed_keys in DEFAULT_ROLE_PERMISSIONS.items():
                for permission in PERMISSION_KEYS:
                    conn.execute("""INSERT OR IGNORE INTO workspace_role_permissions
                        (workspace_id,role,permission_key,allowed,updated_at) VALUES(?,?,?,?,?)""",
                        (workspace_id, role, permission, 1 if permission in allowed_keys else 0, now))
            log_activity(conn, workspace_id, user_id, "workspace", workspace_id, "created", f"فضای کاری «{workspace_name}» ساخته شد.")
    create_session(response, user_id, workspace_id)
    return {"ok": True, "workspaceId": workspace_id}


@app.post("/api/auth/login")
def login(payload: LoginInput, response: Response, request: Request) -> dict[str, Any]:
    email = valid_email(payload.email)
    enforce_rate_limit(request, "login-ip", "all", 40, 600)
    enforce_rate_limit(request, "login-account", email, 10, 600)
    with db() as conn:
        row = conn.execute(
            """SELECT u.id,u.password_hash,m.workspace_id FROM users u JOIN memberships m ON m.user_id=u.id
               WHERE u.email=? COLLATE NOCASE ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,m.joined_at LIMIT 1""", (email,)
        ).fetchone()
        if not row or not verify_password(payload.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="ایمیل یا گذرواژه درست نیست.")
        security = conn.execute("SELECT totp_enabled FROM user_security WHERE user_id=?", (row["id"],)).fetchone()
        if security and security["totp_enabled"]:
            token = secrets.token_urlsafe(36)
            conn.execute("DELETE FROM login_challenges WHERE expires_at<?", (now_iso(),))
            conn.execute("INSERT INTO login_challenges(id,user_id,workspace_id,token_hash,expires_at,created_at,remember_me) VALUES(?,?,?,?,?,?,?)",
                         (new_id(), row["id"], row["workspace_id"], hash_token(token), (datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(), now_iso(), 1 if payload.remember_me else 0))
            return {"ok": False, "twoFactorRequired": True, "challengeToken": token}
        conn.execute("DELETE FROM sessions WHERE expires_at<?", (now_iso(),))
        user_id, workspace_id = row["id"], row["workspace_id"]
    create_session(response, user_id, workspace_id, payload.remember_me)
    return {"ok": True, "twoFactorRequired": False}


@app.post("/api/auth/2fa/verify")
def verify_login_totp(payload: TotpVerifyInput, request: Request, response: Response, challenge_token: str = Header(default="", alias="X-Login-Challenge")) -> dict[str, bool]:
    enforce_rate_limit(request, "totp-ip", challenge_token[:32] or "missing", 10, 600)
    invalid = False
    with db() as conn:
        challenge = conn.execute("SELECT * FROM login_challenges WHERE token_hash=? AND expires_at>?", (hash_token(challenge_token), now_iso())).fetchone()
        if not challenge:
            raise HTTPException(status_code=401, detail="درخواست ورود دومرحله‌ای منقضی شده است.")
        security = conn.execute("SELECT totp_secret,totp_enabled FROM user_security WHERE user_id=?", (challenge["user_id"],)).fetchone()
        if not security or not security["totp_enabled"] or not _verify_totp_or_recovery(conn, challenge["user_id"], security["totp_secret"], payload.code):
            attempts = int(challenge["attempts"] or 0) + 1
            if attempts >= 5:
                conn.execute("DELETE FROM login_challenges WHERE id=?", (challenge["id"],))
            else:
                conn.execute("UPDATE login_challenges SET attempts=? WHERE id=?", (attempts, challenge["id"]))
            invalid = True
        else:
            conn.execute("DELETE FROM login_challenges WHERE id=?", (challenge["id"],))
            user_id, workspace_id = challenge["user_id"], challenge["workspace_id"]
            remember_me = bool(challenge["remember_me"])
    if invalid:
        raise HTTPException(status_code=401, detail="کد تأیید معتبر نیست یا تلاش‌های ورود بیش از حد شده است.")
    create_session(response, user_id, workspace_id, remember_me)
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
            "roleName": user.get("custom_role_name") or {"owner":"مالک","admin":"مدیر","member":"عضو"}.get(user["role"],"عضو"),
            "customRoleId": user.get("custom_role_id"), "roleColor": user.get("custom_role_color"),
            "avatarUrl": f"/api/users/{user['user_id']}/avatar?v={user.get('avatar_updated_at') or ''}" if user.get("avatar_key") else None,
            "workspaceId": user["workspace_id"], "workspaceName": user["workspace_name"],
            "onboardingCompleted": bool(user["onboarding_completed"]), "canManage": has_permission(user, "workspace.manage"),
            "permissions": permissions_for_user(user),
            "instanceAdmin": is_instance_admin(user["user_id"]),
            "serverAdminRole": (server_admin_record(user["user_id"]) or {}).get("role")}


@app.patch("/api/me")
def update_me(payload: ProfileInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        conn.execute("UPDATE users SET name=? WHERE id=?", (payload.name.strip(), user["user_id"]))
        log_activity(conn, user["workspace_id"], user["user_id"], "profile", user["user_id"], "updated", "نام حساب کاربری به‌روزرسانی شد.")
    return {"ok": True}


@app.post("/api/me/avatar")
async def upload_my_avatar(request: Request, x_filename: str = Header(default="avatar"), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="تصویر باید کمتر از ۳ مگابایت باشد.")
    raw = await request.body()
    if not raw or len(raw) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="تصویر باید کمتر از ۳ مگابایت باشد.")
    mime = (request.headers.get("content-type") or "").split(";",1)[0].lower()
    signatures = {"image/jpeg": (b"\xff\xd8\xff", ".jpg"), "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
                  "image/webp": (b"RIFF", ".webp"), "image/gif": (b"GIF8", ".gif")}
    if mime not in signatures or not raw.startswith(signatures[mime][0]) or (mime == "image/webp" and raw[8:12] != b"WEBP"):
        raise HTTPException(status_code=415, detail="فقط تصویر JPEG، PNG، WebP یا GIF پذیرفته می‌شود.")
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    CHAT_DIR.mkdir(parents=True, exist_ok=True)
    key = f"{uuid.uuid4().hex}{signatures[mime][1]}"
    path = AVATAR_DIR / key
    path.write_bytes(raw)
    with db() as conn:
        old = conn.execute("SELECT avatar_key FROM users WHERE id=?", (user["user_id"],)).fetchone()
        conn.execute("UPDATE users SET avatar_key=?,avatar_updated_at=? WHERE id=?", (key,now_iso(),user["user_id"]))
        if old and old["avatar_key"]:
            (AVATAR_DIR / old["avatar_key"]).unlink(missing_ok=True)
        log_activity(conn,user["workspace_id"],user["user_id"],"profile",user["user_id"],"avatar_updated","تصویر نمایه به‌روزرسانی شد.")
    return {"ok":True,"avatarUrl":f"/api/users/{user['user_id']}/avatar?v={int(time.time())}"}


@app.delete("/api/me/avatar")
def delete_my_avatar(user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        row = conn.execute("SELECT avatar_key FROM users WHERE id=?", (user["user_id"],)).fetchone()
        conn.execute("UPDATE users SET avatar_key=NULL,avatar_updated_at=NULL WHERE id=?", (user["user_id"],))
        if row and row["avatar_key"]:
            (AVATAR_DIR / row["avatar_key"]).unlink(missing_ok=True)
        log_activity(conn,user["workspace_id"],user["user_id"],"profile",user["user_id"],"avatar_removed","تصویر نمایه حذف شد.")
    return {"ok":True}


@app.get("/api/users/{user_id}/avatar")
def get_user_avatar(user_id: str, user: dict[str, Any] = Depends(current_user)) -> Response:
    with db() as conn:
        row = conn.execute("SELECT avatar_key FROM users u JOIN memberships m ON m.user_id=u.id WHERE u.id=? AND m.workspace_id=?",
                           (user_id,user["workspace_id"])).fetchone()
    if not row or not row["avatar_key"]:
        raise HTTPException(status_code=404, detail="تصویر نمایه ثبت نشده است.")
    path = (AVATAR_DIR / row["avatar_key"]).resolve()
    if path.parent != AVATAR_DIR.resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="تصویر نمایه پیدا نشد.")
    media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media, headers={"Cache-Control":"private, max-age=300"})


@app.post("/api/me/onboarding")
def update_onboarding(payload: OnboardingInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        conn.execute("UPDATE users SET onboarding_completed=? WHERE id=?", (1 if payload.completed else 0, user["user_id"]))
    return {"ok": True}


@app.get("/api/bootstrap")
def bootstrap(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    me_data = {"id": user["user_id"], "name": user["name"], "email": user["email"], "role": user["role"],
               "roleName": user.get("custom_role_name") or {"owner":"مالک","admin":"مدیر","member":"عضو"}.get(user["role"],"عضو"),
               "customRoleId": user.get("custom_role_id"), "roleColor": user.get("custom_role_color"),
               "avatarUrl": f"/api/users/{user['user_id']}/avatar?v={user.get('avatar_updated_at') or ''}" if user.get("avatar_key") else None,
               "workspaceId": user["workspace_id"], "workspaceName": user["workspace_name"],
               "onboardingCompleted": bool(user["onboarding_completed"]), "canManage": has_permission(user, "workspace.manage"),
               "permissions": permissions_for_user(user), "instanceAdmin": is_instance_admin(user["user_id"]),
               "serverAdminRole": (server_admin_record(user["user_id"]) or {}).get("role")}
    generate_due_recurring(user["workspace_id"])
    with db() as conn:
        workspaces = [dict(r) for r in conn.execute("""SELECT w.id,w.name,m.role FROM memberships m JOIN workspaces w ON w.id=m.workspace_id
            WHERE m.user_id=? ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,w.name""", (user["user_id"],)).fetchall()]
    me_data["canManage"] = has_permission(user, "workspace.manage")
    return {"me": me_data, "workspaces": workspaces, **workspace_snapshot(user["workspace_id"], user["user_id"])}


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
def create_task(payload: TaskInput, user: dict[str, Any] = Depends(require_permission("tasks.create"))) -> dict[str, Any]:
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
def update_task(task_id: str, payload: TaskInput, user: dict[str, Any] = Depends(require_permission("tasks.update"))) -> dict[str, Any]:
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
def delete_task(task_id: str, user: dict[str, Any] = Depends(require_permission("tasks.delete"))) -> dict[str, bool]:
    if not has_permission(user, "tasks.delete"):
        raise HTTPException(status_code=403, detail="نقش شما مجوز حذف کارها را ندارد.")
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
def add_comment(task_id: str, payload: CommentInput, user: dict[str, Any] = Depends(require_permission("comments.create"))) -> dict[str, Any]:
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
def add_checklist(task_id: str, payload: ChecklistInput, user: dict[str, Any] = Depends(require_permission("tasks.checklist"))) -> dict[str, Any]:
    with db() as conn:
        task = get_task_row(conn,user["workspace_id"],task_id)
        pos = conn.execute("SELECT COALESCE(MAX(position),0)+1 FROM task_checklists WHERE task_id=?", (task_id,)).fetchone()[0]
        item_id, now = new_id(), now_iso()
        conn.execute("INSERT INTO task_checklists(id,task_id,title,is_done,position,created_by,created_at) VALUES(?,?,?,0,?,?,?)",
                     (item_id,task_id,payload.title.strip(),pos,user["user_id"],now))
        log_activity(conn,user["workspace_id"],user["user_id"],"checklist",item_id,"created",f"یک مورد به چک‌لیست «{task['title']}» اضافه شد.")
        return dict(conn.execute("SELECT * FROM task_checklists WHERE id=?", (item_id,)).fetchone())


@app.patch("/api/tasks/{task_id}/checklist/{item_id}")
def toggle_checklist(task_id: str, item_id: str, payload: ChecklistToggleInput, user: dict[str, Any] = Depends(require_permission("tasks.checklist"))) -> dict[str, Any]:
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
def delete_checklist(task_id: str, item_id: str, user: dict[str, Any] = Depends(require_permission("tasks.checklist"))) -> dict[str, bool]:
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
async def upload_attachment(task_id: str, request: Request, x_filename: str = Header(default="attachment"), user: dict[str, Any] = Depends(require_permission("tasks.attachments"))) -> dict[str, Any]:
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
def delete_attachment(attachment_id: str, user: dict[str, Any] = Depends(require_permission("tasks.attachments"))) -> dict[str, bool]:
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
def start_task_timer(task_id: str, user: dict[str, Any] = Depends(require_permission("tasks.time"))) -> dict[str, Any]:
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
def stop_task_timer(payload: TimeStopInput, user: dict[str, Any] = Depends(require_permission("tasks.time"))) -> dict[str, Any]:
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
def workspace_reports(period: str = "weekly", user: dict[str, Any] = Depends(require_permission("reports.view"))) -> dict[str, Any]:
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
def set_task_dependencies(task_id: str, payload: DependencyInput, user: dict[str, Any] = Depends(require_permission("tasks.dependencies"))) -> dict[str, Any]:
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
def create_recurring(payload: RecurringInput, user: dict[str, Any] = Depends(require_permission("recurring.manage"))) -> dict[str, Any]:
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
def toggle_recurring(rule_id: str, user: dict[str, Any] = Depends(require_permission("recurring.manage"))) -> dict[str, Any]:
    with db() as conn:
        rule = conn.execute("SELECT * FROM recurring_rules WHERE id=? AND workspace_id=?", (rule_id,user["workspace_id"])).fetchone()
        if not rule: raise HTTPException(status_code=404, detail="الگوی تکرار پیدا نشد.")
        active = 0 if rule["is_active"] else 1
        conn.execute("UPDATE recurring_rules SET is_active=?,updated_at=? WHERE id=?", (active,now_iso(),rule_id))
        log_activity(conn,user["workspace_id"],user["user_id"],"recurring",rule_id,"toggled",f"الگوی «{rule['title']}» {'فعال' if active else 'متوقف'} شد.")
        return {"id":rule_id,"is_active":active}


@app.delete("/api/recurring/{rule_id}")
def delete_recurring(rule_id: str, user: dict[str, Any] = Depends(require_permission("recurring.manage"))) -> dict[str, bool]:
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
def create_template(payload: TemplateInput, user: dict[str, Any] = Depends(require_permission("templates.manage"))) -> dict[str, Any]:
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
def create_task_from_template(template_id: str, user: dict[str, Any] = Depends(require_permission("tasks.create"))) -> dict[str, Any]:
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
def delete_template(template_id: str, user: dict[str, Any] = Depends(require_permission("templates.manage"))) -> dict[str, bool]:
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
def request_task_approval(task_id: str, user: dict[str, Any] = Depends(require_permission("tasks.update"))) -> dict[str, Any]:
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
def decide_approval(approval_id: str, payload: ApprovalDecisionInput, user: dict[str, Any] = Depends(require_permission("approvals.manage"))) -> dict[str, Any]:
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
def create_project(payload: ProjectInput, user: dict[str, Any] = Depends(require_permission("projects.create"))) -> dict[str, Any]:
    project_id, now = new_id(), now_iso()
    with db() as conn:
        conn.execute("INSERT INTO projects(id,workspace_id,name,description,color,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                     (project_id,user["workspace_id"],payload.name.strip(),payload.description.strip(),payload.color,user["user_id"],now,now))
        log_activity(conn,user["workspace_id"],user["user_id"],"project",project_id,"created",f"پروژه «{payload.name.strip()}» ایجاد شد.")
        return dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())


@app.patch("/api/projects/{project_id}")
def update_project(project_id: str, payload: ProjectInput, user: dict[str, Any] = Depends(require_permission("projects.update"))) -> dict[str, Any]:
    now = now_iso()
    with db() as conn:
        exists = conn.execute("SELECT id FROM projects WHERE id=? AND workspace_id=?", (project_id,user["workspace_id"])).fetchone()
        if not exists: raise HTTPException(status_code=404, detail="پروژه پیدا نشد.")
        conn.execute("UPDATE projects SET name=?,description=?,color=?,updated_at=? WHERE id=?", (payload.name.strip(),payload.description.strip(),payload.color,now,project_id))
        log_activity(conn,user["workspace_id"],user["user_id"],"project",project_id,"updated",f"پروژه «{payload.name.strip()}» ویرایش شد.")
        return dict(conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, user: dict[str, Any] = Depends(require_permission("projects.delete"))) -> dict[str, bool]:
    with db() as conn:
        row = conn.execute("SELECT name FROM projects WHERE id=? AND workspace_id=?", (project_id,user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404, detail="پروژه پیدا نشد.")
        conn.execute("UPDATE tasks SET project_id=NULL WHERE project_id=?", (project_id,))
        conn.execute("UPDATE task_templates SET project_id=NULL WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        log_activity(conn,user["workspace_id"],user["user_id"],"project",project_id,"deleted",f"پروژه «{row['name']}» حذف شد.")
    return {"ok": True}


@app.post("/api/teams")
def create_team(payload: TeamInput, user: dict[str, Any] = Depends(require_permission("teams.manage"))) -> dict[str, Any]:
    team_id, now = new_id(), now_iso()
    with db() as conn:
        conn.execute("INSERT INTO teams(id,workspace_id,name,description,created_at) VALUES(?,?,?,?,?)",
                     (team_id,user["workspace_id"],payload.name.strip(),payload.description.strip(),now))
        conn.execute("INSERT INTO team_members(team_id,user_id,created_at) VALUES(?,?,?)", (team_id,user["user_id"],now))
        log_activity(conn,user["workspace_id"],user["user_id"],"team",team_id,"created",f"تیم «{payload.name.strip()}» ایجاد شد.")
        return {**dict(conn.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()), "members": [{"id":user["user_id"],"name":user["name"]}], "memberIds": [user["user_id"]]}


@app.put("/api/teams/{team_id}/members")
def update_team_members(team_id: str, payload: TeamMembersInput, user: dict[str, Any] = Depends(require_permission("teams.manage"))) -> dict[str, Any]:
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
def delete_team(team_id: str, user: dict[str, Any] = Depends(require_permission("teams.manage"))) -> dict[str, bool]:
    with db() as conn:
        team = conn.execute("SELECT name FROM teams WHERE id=? AND workspace_id=?", (team_id,user["workspace_id"])).fetchone()
        if not team: raise HTTPException(status_code=404, detail="تیم پیدا نشد.")
        conn.execute("UPDATE tasks SET team_id=NULL WHERE team_id=?", (team_id,))
        conn.execute("UPDATE task_templates SET team_id=NULL WHERE team_id=?", (team_id,))
        conn.execute("DELETE FROM teams WHERE id=?", (team_id,))
        log_activity(conn,user["workspace_id"],user["user_id"],"team",team_id,"deleted",f"تیم «{team['name']}» حذف شد.")
    return {"ok": True}


@app.post("/api/invitations")
def create_invitation(payload: InviteInput, request: Request, user: dict[str, Any] = Depends(require_permission("members.invite"))) -> dict[str, Any]:
    email = valid_email(payload.email)
    role = payload.role if payload.role in {"admin", "member"} else "member"
    if role == "admin" and user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="فقط مالک فضای کاری می‌تواند دعوت با نقش مدیر ایجاد کند.")
    with db() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        if existing:
            already = conn.execute("SELECT id FROM memberships WHERE user_id=? AND workspace_id=?", (existing["id"],user["workspace_id"])).fetchone()
            if already: raise HTTPException(status_code=409, detail="این کاربر هم‌اکنون عضو فضای کار است.")
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
    scheme = "https" if request.url.scheme == "https" or COOKIE_SECURE else "http"
    invite_url = f"{scheme}://{request_host}:{port}/#invite={raw_token}"
    return {"id":invite_id,"email":email,"role":role,"inviteCode":raw_token,"inviteUrl":invite_url,"expiresAt":expires}


@app.post("/api/workspace-join-links")
def create_workspace_join_link(payload: WorkspaceJoinLinkInput, request: Request,
                               user: dict[str, Any] = Depends(require_permission("members.invite"))) -> dict[str, Any]:
    role = payload.role if payload.role in {"admin", "member"} else "member"
    if role == "admin" and user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="فقط مالک فضای کاری می‌تواند لینک عضویت با نقش مدیر بسازد.")
    raw_token = secrets.token_urlsafe(48)
    link_id = new_id()
    stamp = now_iso()
    expires = (datetime.now(timezone.utc) + timedelta(days=payload.expires_days)).replace(microsecond=0).isoformat()
    with db() as conn:
        conn.execute("""INSERT INTO workspace_join_links
            (id,workspace_id,role,token_hash,created_by,expires_at,max_uses,use_count,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (link_id,user["workspace_id"],role,hash_token(raw_token),user["user_id"],expires,payload.max_uses,0,stamp))
        log_activity(conn,user["workspace_id"],user["user_id"],"workspace_join_link",link_id,"created","یک لینک امن عضویت ساخته شد.")
    host = request.url.hostname or "127.0.0.1"
    port = int(os.getenv("BOTTLENECK_PORT", "1939"))
    if host in {"127.0.0.1", "localhost", "0.0.0.0"}:
        ips = discover_lan_ips()
        host = ips[0] if ips else host
    scheme = "https" if request.url.scheme == "https" or COOKIE_SECURE else "http"
    url = f"{scheme}://{host}:{port}/#join={raw_token}"
    return {"id":link_id,"role":role,"expiresAt":expires,"maxUses":payload.max_uses,"joinUrl":url}


@app.get("/api/workspace-join-links/{token}")
def preview_workspace_join_link(token: str) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("""SELECT l.role,l.expires_at,l.max_uses,l.use_count,w.name AS workspace_name
            FROM workspace_join_links l JOIN workspaces w ON w.id=l.workspace_id
            WHERE l.token_hash=? AND l.revoked_at IS NULL AND l.expires_at>?""",(hash_token(token),now_iso())).fetchone()
        if not row or (row["max_uses"] and row["use_count"] >= row["max_uses"]):
            raise HTTPException(status_code=404,detail="لینک عضویت معتبر نیست یا منقضی شده است.")
    return {"workspaceName":row["workspace_name"],"role":row["role"],"expiresAt":row["expires_at"],"remainingUses":None if not row["max_uses"] else max(0,row["max_uses"]-row["use_count"])}


def _accept_workspace_join_link(token: str, request: Request, user: dict[str, Any]) -> dict[str, Any]:
    stamp = now_iso()
    session_token = request.cookies.get(COOKIE_NAME)
    if not session_token:
        raise HTTPException(status_code=401,detail="برای پیوستن ابتدا وارد حساب شوید.")
    with db() as conn:
        link = conn.execute("""SELECT * FROM workspace_join_links WHERE token_hash=? AND revoked_at IS NULL AND expires_at>?""",
                            (hash_token(token),stamp)).fetchone()
        if not link or (link["max_uses"] and link["use_count"] >= link["max_uses"]):
            raise HTTPException(status_code=404,detail="لینک عضویت معتبر نیست، لغو شده یا ظرفیت آن تکمیل شده است.")
        workspace_id = link["workspace_id"]
        existing = conn.execute("SELECT 1 FROM memberships WHERE workspace_id=? AND user_id=?",(workspace_id,user["user_id"])).fetchone()
        if not existing:
            conn.execute("INSERT INTO memberships(id,workspace_id,user_id,role,joined_at) VALUES(?,?,?,?,?)",
                         (new_id(),workspace_id,user["user_id"],link["role"],stamp))
            changed = conn.execute("""UPDATE workspace_join_links SET use_count=use_count+1
                WHERE id=? AND revoked_at IS NULL AND expires_at>? AND (max_uses=0 OR use_count<max_uses)""",(link["id"],stamp))
            if changed.rowcount != 1:
                raise HTTPException(status_code=409,detail="ظرفیت لینک عضویت در همین لحظه تکمیل شد.")
            default_team = conn.execute("SELECT id FROM teams WHERE workspace_id=? ORDER BY created_at LIMIT 1",(workspace_id,)).fetchone()
            if default_team:
                conn.execute("INSERT OR IGNORE INTO team_members(team_id,user_id,created_at) VALUES(?,?,?)",(default_team["id"],user["user_id"],stamp))
            log_activity(conn,workspace_id,user["user_id"],"member",user["user_id"],"joined",f"{user['name']} با لینک امن به فضای کار پیوست.")
            owner = conn.execute("SELECT created_by FROM workspaces WHERE id=?",(workspace_id,)).fetchone()
            if owner:
                create_notification(conn,workspace_id,owner["created_by"],user["user_id"],"member","عضو جدید به فضای کار پیوست",user["name"],"member",user["user_id"])
        conn.execute("UPDATE sessions SET workspace_id=? WHERE token_hash=? AND user_id=?",(workspace_id,hash_token(session_token),user["user_id"]))
    return {"ok":True,"workspaceId":workspace_id,"alreadyMember":bool(existing)}


@app.post("/api/workspace-join/accept")
def accept_workspace_join_link_body(payload: LinkTokenInput, request: Request,
                                   user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return _accept_workspace_join_link(payload.token, request, user)


@app.post("/api/workspace-join-links/{token}/accept")
def accept_workspace_join_link(token: str, request: Request,
                               user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return _accept_workspace_join_link(token, request, user)


@app.delete("/api/workspace-join-links/{link_id}")
def revoke_workspace_join_link(link_id: str,user: dict[str, Any] = Depends(require_permission("members.manage"))) -> dict[str,bool]:
    with db() as conn:
        cur=conn.execute("UPDATE workspace_join_links SET revoked_at=? WHERE id=? AND workspace_id=? AND revoked_at IS NULL",
                         (now_iso(),link_id,user["workspace_id"]))
        if not cur.rowcount:
            raise HTTPException(status_code=404,detail="لینک عضویت پیدا نشد.")
        log_activity(conn,user["workspace_id"],user["user_id"],"workspace_join_link",link_id,"revoked","یک لینک عضویت لغو شد.")
    return {"ok":True}


@app.delete("/api/invitations/{invitation_id}")
def revoke_invitation(invitation_id: str, user: dict[str, Any] = Depends(require_permission("members.manage"))) -> dict[str, bool]:
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



# ---------------------------------------------------------------------------
# v0.5.0: shared boards, shared drive, Markdown notes, team chat and presence.
# ---------------------------------------------------------------------------
def validate_share_settings(conn: sqlite3.Connection, workspace_id: str, access_mode: str,
                            team_id: str | None, password: str | None,
                            user: dict[str, Any] | None = None) -> str | None:
    if access_mode not in {"workspace", "team", "password"}:
        raise HTTPException(status_code=422, detail="نوع دسترسی معتبر نیست.")
    if access_mode == "team":
        if not team_id:
            raise HTTPException(status_code=422, detail="برای اشتراک‌گذاری تیمی، یک تیم انتخاب کنید.")
        found = conn.execute("SELECT 1 FROM teams WHERE id=? AND workspace_id=?", (team_id, workspace_id)).fetchone()
        if not found:
            raise HTTPException(status_code=422, detail="تیم انتخاب‌شده در این فضای کاری وجود ندارد.")
        if user is not None and not _team_member(conn, team_id, user):
            raise HTTPException(status_code=403, detail="برای اشتراک‌گذاری در این تیم باید عضو آن باشید یا مدیر فضای کار باشید.")
    else:
        team_id = None
    if access_mode == "password":
        if not password or len(password) < 8:
            raise HTTPException(status_code=422, detail="گذرواژه اشتراک باید حداقل ۸ نویسه باشد.")
        return password_hash(password)
    return None


def _team_member(conn: sqlite3.Connection, team_id: str | None, user: dict[str, Any]) -> bool:
    if not team_id:
        return False
    if user.get("role") in ("owner", "admin"):
        return True
    return conn.execute("SELECT 1 FROM team_members WHERE team_id=? AND user_id=?",
                        (team_id, user["user_id"])).fetchone() is not None


def check_node_access(conn: sqlite3.Connection, node: sqlite3.Row, user: dict[str, Any],
                      password: str | None = None, *, allow_locked: bool = False) -> bool:
    """Check the node and all ancestor gates. Returns True when a password lock remains."""
    if node["workspace_id"] != user["workspace_id"]:
        raise HTTPException(status_code=404, detail="مورد پیدا نشد.")
    locked = False
    current = node
    seen: set[str] = set()
    while current:
        if current["id"] in seen:
            raise HTTPException(status_code=409, detail="ساختار پوشه‌ها معتبر نیست.")
        seen.add(current["id"])
        if current["access_mode"] == "team" and not _team_member(conn, current["team_id"], user):
            raise HTTPException(status_code=403, detail="این مورد فقط برای اعضای تیم مشخص‌شده قابل دسترسی است.")
        if current["access_mode"] == "password":
            if not password:
                locked = True
            elif not current["password_hash"] or not verify_password(password, current["password_hash"]):
                raise HTTPException(status_code=403, detail="گذرواژه اشتراک‌گذاری نادرست است.")
        parent_id = current["parent_id"] if "parent_id" in current.keys() else None
        current = conn.execute("SELECT * FROM shared_nodes WHERE id=? AND workspace_id=?",
                               (parent_id, user["workspace_id"])).fetchone() if parent_id else None
    if locked and not allow_locked:
        raise HTTPException(status_code=423, detail="این مورد با گذرواژه محافظت شده است.")
    return locked


def require_board_access(conn: sqlite3.Connection, board: sqlite3.Row, user: dict[str, Any],
                         password: str | None = None, *, allow_locked: bool = False) -> bool:
    if board["workspace_id"] != user["workspace_id"]:
        raise HTTPException(status_code=404, detail="برد پیدا نشد.")
    locked = False
    if board["access_mode"] == "team" and not _team_member(conn, board["team_id"], user):
        raise HTTPException(status_code=403, detail="این برد فقط برای اعضای تیم قابل مشاهده است.")
    if board["access_mode"] == "password":
        if not password:
            locked = True
        elif not board["password_hash"] or not verify_password(password, board["password_hash"]):
            raise HTTPException(status_code=403, detail="گذرواژه برد نادرست است.")
    if locked and not allow_locked:
        raise HTTPException(status_code=423, detail="این برد با گذرواژه محافظت شده است.")
    return locked


def shared_node_public(row: sqlite3.Row, *, locked: bool = False) -> dict[str, Any]:
    return {
        "id": row["id"], "parentId": row["parent_id"], "type": row["node_type"],
        "title": row["title"], "content": "" if locked else row["content"],
        "originalName": row["original_name"], "contentType": row["content_type"],
        "sizeBytes": row["size_bytes"], "accessMode": row["access_mode"],
        "teamId": row["team_id"], "createdBy": row["created_by"],
        "createdAt": row["created_at"], "updatedAt": row["updated_at"], "locked": locked,
    }


@app.get("/api/boards")
def list_shared_boards(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM shared_boards WHERE workspace_id=? ORDER BY created_at",
                            (user["workspace_id"],)).fetchall()
        if not rows:
            stamp = now_iso()
            board_id = new_id()
            conn.execute("INSERT INTO shared_boards(id,workspace_id,title,description,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                         (board_id, user["workspace_id"], "برد ایده‌های تیم", "ایده‌ها، یادداشت‌ها و مسیرهای مشترک را کنار هم بچینید.", user["user_id"], stamp, stamp))
            log_activity(conn, user["workspace_id"], user["user_id"], "board", board_id, "board.created", "برد ایده‌های تیم ساخته شد")
            rows = conn.execute("SELECT * FROM shared_boards WHERE workspace_id=? ORDER BY created_at",
                                (user["workspace_id"],)).fetchall()
        result = []
        for row in rows:
            if row["access_mode"] == "team" and not _team_member(conn, row["team_id"], user):
                continue
            result.append({"id": row["id"], "title": row["title"], "description": row["description"],
                           "accessMode": row["access_mode"], "teamId": row["team_id"],
                           "locked": row["access_mode"] == "password", "updatedAt": row["updated_at"]})
        return result


@app.post("/api/boards")
def create_shared_board(payload: BoardInput, user: dict[str, Any] = Depends(require_permission("boards.manage"))) -> dict[str, Any]:
    with db() as conn:
        encoded = validate_share_settings(conn, user["workspace_id"], payload.access_mode,
                                           payload.team_id, payload.password, user)
        stamp, board_id = now_iso(), new_id()
        conn.execute("""INSERT INTO shared_boards(id,workspace_id,title,description,access_mode,team_id,password_hash,created_by,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                     (board_id, user["workspace_id"], payload.title.strip(), payload.description,
                      payload.access_mode, payload.team_id, encoded, user["user_id"], stamp, stamp))
        log_activity(conn, user["workspace_id"], user["user_id"], "board", board_id, "board.created", f"برد «{payload.title}» ساخته شد")
        return {"id": board_id, "title": payload.title.strip(), "description": payload.description,
                "accessMode": payload.access_mode, "teamId": payload.team_id, "locked": False}


@app.get("/api/boards/{board_id}/items")
def list_board_items(board_id: str, password: str | None = None,
                     user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        board = conn.execute("SELECT * FROM shared_boards WHERE id=? AND workspace_id=?",
                             (board_id, user["workspace_id"])).fetchone()
        if not board:
            raise HTTPException(status_code=404, detail="برد پیدا نشد.")
        require_board_access(conn, board, user, password)
        rows = conn.execute("""SELECT bi.*,u.name AS creator_name FROM shared_board_items bi
                              LEFT JOIN users u ON u.id=bi.created_by WHERE bi.board_id=? ORDER BY bi.y,bi.x""",
                            (board_id,)).fetchall()
        return {"board": {"id": board["id"], "title": board["title"], "description": board["description"]},
                "items": [{"id": r["id"], "type": r["item_type"], "title": r["title"], "content": r["content"],
                           "url": r["url"], "taskId": r["task_id"], "x": r["x"], "y": r["y"],
                           "width": r["width"], "color": r["color"], "createdBy": r["created_by"],
                           "creatorName": r["creator_name"], "updatedAt": r["updated_at"]} for r in rows]}


@app.post("/api/boards/{board_id}/items")
def create_board_item(board_id: str, payload: BoardItemInput, password: str | None = None,
                      user: dict[str, Any] = Depends(require_permission("boards.manage"))) -> dict[str, Any]:
    if payload.item_type not in {"note", "text", "link", "task"}:
        raise HTTPException(status_code=422, detail="نوع کارت برد معتبر نیست.")
    if payload.item_type == "link" and payload.url and not payload.url.startswith(("https://", "http://")):
        raise HTTPException(status_code=422, detail="پیوند باید با http یا https آغاز شود.")
    with db() as conn:
        board = conn.execute("SELECT * FROM shared_boards WHERE id=? AND workspace_id=?", (board_id, user["workspace_id"])).fetchone()
        if not board: raise HTTPException(status_code=404, detail="برد پیدا نشد.")
        require_board_access(conn, board, user, password)
        if payload.task_id:
            get_task_row(conn, user["workspace_id"], payload.task_id)
        stamp, item_id = now_iso(), new_id()
        conn.execute("""INSERT INTO shared_board_items(id,workspace_id,board_id,item_type,title,content,url,task_id,x,y,width,color,created_by,updated_by,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (item_id,user["workspace_id"],board_id,payload.item_type,payload.title.strip(),payload.content,
                      payload.url,payload.task_id,payload.x,payload.y,payload.width,payload.color,user["user_id"],user["user_id"],stamp,stamp))
        conn.execute("UPDATE shared_boards SET updated_at=? WHERE id=?", (stamp, board_id))
        log_activity(conn, user["workspace_id"], user["user_id"], "board_item", item_id, "board.item.created", f"کارت «{payload.title or 'بدون عنوان'}» به برد اضافه شد")
        return {"id": item_id}


@app.patch("/api/boards/{board_id}/items/{item_id}")
def update_board_item(board_id: str, item_id: str, payload: BoardItemInput, password: str | None = None,
                      user: dict[str, Any] = Depends(require_permission("boards.manage"))) -> dict[str, bool]:
    if payload.item_type not in {"note", "text", "link", "task"}:
        raise HTTPException(status_code=422, detail="نوع کارت برد معتبر نیست.")
    if payload.item_type == "link" and payload.url and not payload.url.startswith(("https://", "http://")):
        raise HTTPException(status_code=422, detail="پیوند باید با http یا https آغاز شود.")
    with db() as conn:
        board = conn.execute("SELECT * FROM shared_boards WHERE id=? AND workspace_id=?", (board_id, user["workspace_id"])).fetchone()
        if not board: raise HTTPException(status_code=404, detail="برد پیدا نشد.")
        require_board_access(conn, board, user, password)
        row = conn.execute("SELECT * FROM shared_board_items WHERE id=? AND board_id=? AND workspace_id=?", (item_id,board_id,user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404, detail="کارت پیدا نشد.")
        if payload.task_id: get_task_row(conn, user["workspace_id"], payload.task_id)
        stamp = now_iso()
        conn.execute("""UPDATE shared_board_items SET item_type=?,title=?,content=?,url=?,task_id=?,x=?,y=?,width=?,color=?,updated_by=?,updated_at=? WHERE id=?""",
                     (payload.item_type,payload.title.strip(),payload.content,payload.url,payload.task_id,payload.x,payload.y,payload.width,payload.color,user["user_id"],stamp,item_id))
        conn.execute("UPDATE shared_boards SET updated_at=? WHERE id=?", (stamp,board_id))
        # Position updates are intentionally included in the live workspace event feed.
        conn.execute("INSERT INTO workspace_events(workspace_id,user_id,kind,message,created_at) VALUES(?,?,?,?,?)",
                     (user["workspace_id"],user["user_id"],"board.item.updated","کارت برد به‌روزرسانی شد",stamp))
        return {"ok": True}


@app.delete("/api/boards/{board_id}/items/{item_id}")
def delete_board_item(board_id: str, item_id: str, password: str | None = None,
                      user: dict[str, Any] = Depends(require_permission("boards.manage"))) -> dict[str, bool]:
    with db() as conn:
        board = conn.execute("SELECT * FROM shared_boards WHERE id=? AND workspace_id=?", (board_id,user["workspace_id"])).fetchone()
        if not board: raise HTTPException(status_code=404, detail="برد پیدا نشد.")
        require_board_access(conn, board, user, password)
        conn.execute("DELETE FROM shared_board_items WHERE id=? AND board_id=? AND workspace_id=?", (item_id,board_id,user["workspace_id"]))
        log_activity(conn,user["workspace_id"],user["user_id"],"board_item",item_id,"board.item.deleted","یک کارت از برد حذف شد")
    return {"ok": True}


@app.get("/api/drive")
def list_drive_nodes(parent_id: str | None = None, password: str | None = None,
                     user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        if parent_id:
            parent = conn.execute("SELECT * FROM shared_nodes WHERE id=? AND workspace_id=? AND node_type='folder'",
                                  (parent_id,user["workspace_id"])).fetchone()
            if not parent: raise HTTPException(status_code=404, detail="پوشه پیدا نشد.")
            check_node_access(conn,parent,user,password)
        rows = conn.execute("SELECT * FROM shared_nodes WHERE workspace_id=? AND parent_id IS ? ORDER BY CASE node_type WHEN 'folder' THEN 0 WHEN 'text' THEN 1 ELSE 2 END,title COLLATE NOCASE",
                            (user["workspace_id"], parent_id)).fetchall()
        items = []
        for row in rows:
            if row["access_mode"] == "team" and not _team_member(conn,row["team_id"],user):
                continue
            locked = row["access_mode"] == "password"
            if parent_id and parent_id:
                # Child nodes inherit the folder's password gate, so the browser must pass it on.
                locked = locked or False
            items.append(shared_node_public(row,locked=locked))
        return {"items":items,"parentId":parent_id}


@app.get("/api/drive/nodes/{node_id}")
def get_drive_node(node_id: str, password: str | None = None,
                   user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT * FROM shared_nodes WHERE id=? AND workspace_id=?",(node_id,user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404,detail="مورد پیدا نشد.")
        check_node_access(conn,row,user,password)
        return shared_node_public(row)


@app.post("/api/drive/nodes")
def create_drive_node(payload: DriveNodeInput, user: dict[str, Any] = Depends(require_permission("drive.manage"))) -> dict[str, Any]:
    if payload.node_type not in {"folder","text"}:
        raise HTTPException(status_code=422,detail="نوع مورد باید پوشه یا یادداشت متنی باشد.")
    with db() as conn:
        if payload.parent_id:
            parent=conn.execute("SELECT * FROM shared_nodes WHERE id=? AND workspace_id=? AND node_type='folder'",(payload.parent_id,user["workspace_id"])).fetchone()
            if not parent: raise HTTPException(status_code=404,detail="پوشه والد پیدا نشد.")
            check_node_access(conn,parent,user,payload.parent_password)
            require_shared_node_write(conn,parent,user)
        encoded=validate_share_settings(conn,user["workspace_id"],payload.access_mode,payload.team_id,payload.password,user)
        stamp,node_id=now_iso(),new_id()
        conn.execute("""INSERT INTO shared_nodes(id,workspace_id,parent_id,node_type,title,content,access_mode,team_id,password_hash,created_by,updated_by,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (node_id,user["workspace_id"],payload.parent_id,payload.node_type,payload.title.strip(),payload.content,
                      payload.access_mode,payload.team_id,encoded,user["user_id"],user["user_id"],stamp,stamp))
        log_activity(conn,user["workspace_id"],user["user_id"],"shared_node",node_id,"drive.node.created",f"{('پوشه' if payload.node_type=='folder' else 'یادداشت')} «{payload.title}» ساخته شد")
        return {"id":node_id}


@app.patch("/api/drive/nodes/{node_id}")
def update_drive_node(node_id: str,payload: DriveNodeUpdateInput,password: str | None = None,
                      user: dict[str, Any] = Depends(require_permission("drive.manage"))) -> dict[str,bool]:
    with db() as conn:
        row=conn.execute("SELECT * FROM shared_nodes WHERE id=? AND workspace_id=?",(node_id,user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404,detail="مورد پیدا نشد.")
        check_node_access(conn,row,user,password)
        require_shared_node_write(conn,row,user)
        if payload.access_mode is not None and row["created_by"] != user["user_id"] and user["role"] not in ("owner","admin"):
            raise HTTPException(status_code=403,detail="فقط سازنده مورد یا مدیر می‌تواند تنظیمات اشتراک را تغییر دهد.")
        title=payload.title.strip() if payload.title is not None else row["title"]
        content=payload.content if payload.content is not None else row["content"]
        access_mode=payload.access_mode or row["access_mode"]
        team_id=payload.team_id if payload.access_mode is not None else row["team_id"]
        encoded=row["password_hash"]
        if payload.access_mode is not None:
            if access_mode == "password":
                if payload.password:
                    if len(payload.password)<8: raise HTTPException(status_code=422,detail="گذرواژه باید حداقل ۸ نویسه باشد.")
                    encoded=password_hash(payload.password)
                elif row["access_mode"] != "password":
                    raise HTTPException(status_code=422,detail="برای فعال‌کردن محافظت، گذرواژه وارد کنید.")
            else:
                encoded=None
            if access_mode not in {"workspace","team","password"}: raise HTTPException(status_code=422,detail="نوع دسترسی معتبر نیست.")
            if access_mode=="team":
                if not team_id or not conn.execute("SELECT 1 FROM teams WHERE id=? AND workspace_id=?",(team_id,user["workspace_id"])).fetchone():
                    raise HTTPException(status_code=422,detail="تیم اشتراک معتبر نیست.")
            else: team_id=None
        stamp=now_iso()
        conn.execute("UPDATE shared_nodes SET title=?,content=?,access_mode=?,team_id=?,password_hash=?,updated_by=?,updated_at=? WHERE id=?",
                     (title,content,access_mode,team_id,encoded,user["user_id"],stamp,node_id))
        log_activity(conn,user["workspace_id"],user["user_id"],"shared_node",node_id,"drive.node.updated",f"مورد مشترک «{title}» به‌روزرسانی شد")
    return {"ok":True}


@app.delete("/api/drive/nodes/{node_id}")
def delete_drive_node(node_id: str,password: str | None = None,user: dict[str, Any] = Depends(require_permission("drive.manage"))) -> dict[str,bool]:
    with db() as conn:
        row=conn.execute("SELECT * FROM shared_nodes WHERE id=? AND workspace_id=?",(node_id,user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404,detail="مورد پیدا نشد.")
        check_node_access(conn,row,user,password)
        require_shared_node_write(conn,row,user)
        if row["created_by"] != user["user_id"] and user["role"] not in ("owner","admin"):
            raise HTTPException(status_code=403,detail="حذف این مورد به دسترسی سازنده یا مدیر نیاز دارد.")
        descendants=conn.execute("WITH RECURSIVE tree(id,stored_name) AS (SELECT id,stored_name FROM shared_nodes WHERE id=? UNION ALL SELECT n.id,n.stored_name FROM shared_nodes n JOIN tree t ON n.parent_id=t.id) SELECT stored_name FROM tree WHERE stored_name IS NOT NULL",(node_id,)).fetchall()
        paths=[SHARED_DIR/user["workspace_id"]/r["stored_name"] for r in descendants]
        conn.execute("DELETE FROM shared_nodes WHERE id=? AND workspace_id=?",(node_id,user["workspace_id"]))
        log_activity(conn,user["workspace_id"],user["user_id"],"shared_node",node_id,"drive.node.deleted",f"مورد «{row['title']}» حذف شد")
    for path in paths:
        try: path.unlink(missing_ok=True)
        except OSError: pass
    return {"ok":True}


@app.post("/api/drive/upload")
async def upload_drive_file(request: Request, parent_id: str | None = None,
                            access_mode: str = "workspace", team_id: str | None = None,
                            share_password: str | None = Header(default=None, alias="X-Share-Password"),
                            user: dict[str, Any] = Depends(require_permission("drive.manage"))) -> dict[str, Any]:
    raw_name = unquote(request.headers.get("x-file-name", "file.bin"))
    safe_name = Path(raw_name.replace("\\", "/")).name.strip() or "file.bin"
    ext = Path(safe_name).suffix.lower()
    if ext not in SHARED_FILE_EXTENSIONS:
        raise HTTPException(status_code=415, detail="این نوع فایل پشتیبانی نمی‌شود.")

    # Validate access gates before writing any bytes to disk.
    with db() as conn:
        if parent_id:
            parent = conn.execute(
                "SELECT * FROM shared_nodes WHERE id=? AND workspace_id=? AND node_type='folder'",
                (parent_id, user["workspace_id"]),
            ).fetchone()
            if not parent:
                raise HTTPException(status_code=404, detail="پوشه مقصد پیدا نشد.")
            check_node_access(conn, parent, user, request.headers.get("x-folder-password"))
            require_shared_node_write(conn, parent, user)
        encoded = validate_share_settings(conn, user["workspace_id"], access_mode, team_id, share_password, user)

    node_id, stamp = new_id(), now_iso()
    folder = SHARED_DIR / user["workspace_id"]
    folder.mkdir(parents=True, exist_ok=True)
    stored = f"{node_id}{ext}"
    path = folder / stored
    size = 0
    content_type = request.headers.get("content-type") or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    try:
        # Stream in bounded chunks so an oversized request cannot be buffered wholesale in memory.
        with path.open("wb") as handle:
            async for chunk in request.stream():
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_SHARED_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="حداکثر حجم هر فایل ۵۰ مگابایت است.")
                handle.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="فایل خالی است.")
        with db() as conn:
            conn.execute(
                """INSERT INTO shared_nodes(id,workspace_id,parent_id,node_type,title,stored_name,original_name,content_type,size_bytes,access_mode,team_id,password_hash,created_by,updated_by,created_at,updated_at)
                   VALUES(?,?,?,'file',?,?,?,?,?,?,?,?,?,?,?,?)""",
                (node_id, user["workspace_id"], parent_id, safe_name, stored, safe_name, content_type,
                 size, access_mode, team_id if access_mode == "team" else None, encoded,
                 user["user_id"], user["user_id"], stamp, stamp),
            )
            log_activity(conn, user["workspace_id"], user["user_id"], "shared_file", node_id,
                         "drive.file.uploaded", f"فایل «{safe_name}» بارگذاری شد")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {"id": node_id, "title": safe_name, "sizeBytes": size}


@app.get("/api/drive/nodes/{node_id}/download")
def download_drive_file(node_id: str,password: str | None = None,
                        user: dict[str, Any] = Depends(current_user)) -> FileResponse:
    with db() as conn:
        row=conn.execute("SELECT * FROM shared_nodes WHERE id=? AND workspace_id=? AND node_type='file'",(node_id,user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404,detail="فایل پیدا نشد.")
        check_node_access(conn,row,user,password)
        path=SHARED_DIR/user["workspace_id"]/row["stored_name"]
        if not path.is_file(): raise HTTPException(status_code=404,detail="فایل روی دیسک پیدا نشد.")
        return FileResponse(path,media_type=row["content_type"] or "application/octet-stream",filename=row["original_name"] or row["title"],content_disposition_type="attachment")


def _chat_channel_access(conn: sqlite3.Connection, user: dict[str, Any], channel_type: str, team_id: str | None) -> None:
    if channel_type not in {"workspace", "team"}:
        raise HTTPException(status_code=422, detail="کانال گفتگو معتبر نیست.")
    if channel_type == "team":
        if not team_id or not conn.execute("SELECT 1 FROM teams WHERE id=? AND workspace_id=?", (team_id, user["workspace_id"])).fetchone():
            raise HTTPException(status_code=404, detail="تیم پیدا نشد.")
        if not _team_member(conn, team_id, user):
            raise HTTPException(status_code=403, detail="برای دسترسی به این کانال باید عضو تیم باشید.")


def _chat_resource(conn: sqlite3.Connection, user: dict[str, Any], resource_type: str | None,
                   resource_id: str | None) -> dict[str, Any] | None:
    if not resource_type and not resource_id:
        return None
    if not resource_type or not resource_id or resource_type not in {"task", "project", "note", "file", "board"}:
        raise HTTPException(status_code=422, detail="نوع پیوند داخل پیام معتبر نیست.")
    if resource_type == "task":
        row = conn.execute("SELECT id,title FROM tasks WHERE id=? AND workspace_id=?", (resource_id, user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404, detail="کار پیوندشده پیدا نشد.")
        title = row["title"]
    elif resource_type == "project":
        row = conn.execute("SELECT id,name AS title FROM projects WHERE id=? AND workspace_id=?", (resource_id, user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404, detail="پروژه پیوندشده پیدا نشد.")
        title = row["title"]
    elif resource_type in {"note", "file"}:
        row = conn.execute("SELECT * FROM shared_nodes WHERE id=? AND workspace_id=?", (resource_id, user["workspace_id"])).fetchone()
        if not row or row["node_type"] != ("text" if resource_type == "note" else "file"):
            raise HTTPException(status_code=404, detail="مورد پیوندشده پیدا نشد.")
        check_node_access(conn, row, user)
        title = row["title"]
    else:
        row = conn.execute("SELECT * FROM shared_boards WHERE id=? AND workspace_id=?", (resource_id, user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404, detail="برد پیوندشده پیدا نشد.")
        require_board_access(conn, row, user)
        title = row["title"]
    return {"type": resource_type, "id": resource_id, "title": title}


def _chat_attachment_public(row: sqlite3.Row) -> dict[str, Any]:
    return {"id": row["id"], "name": row["original_name"], "contentType": row["content_type"],
            "sizeBytes": row["size_bytes"], "url": f"/api/chat/attachments/{row['id']}"}


@app.get("/api/chat")
def get_chat(channel_type: str = "workspace", team_id: str | None = None, q: str = "",
             before_id: str | None = None, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        _chat_channel_access(conn, user, channel_type, team_id)
        query = """SELECT c.*,u.name AS user_name,u.avatar_key,u.avatar_updated_at,
                    ru.name AS reply_user_name,rc.body AS reply_body
                   FROM chat_messages c JOIN users u ON u.id=c.user_id
                   LEFT JOIN chat_messages rc ON rc.id=c.reply_to_id
                   LEFT JOIN users ru ON ru.id=rc.user_id
                   WHERE c.workspace_id=? AND c.channel_type=?"""
        args: list[Any] = [user["workspace_id"], channel_type]
        if channel_type == "team": query += " AND c.team_id=?"; args.append(team_id)
        if q.strip():
            needle = f"%{q.strip()[:80]}%"
            query += " AND c.deleted_at IS NULL AND (c.body LIKE ? OR u.name LIKE ?)"
            args.extend([needle, needle])
        if before_id:
            before = conn.execute("SELECT created_at FROM chat_messages WHERE id=? AND workspace_id=?", (before_id,user["workspace_id"])).fetchone()
            if before: query += " AND c.created_at<?"; args.append(before["created_at"])
        query += " ORDER BY c.created_at DESC LIMIT 100"
        rows = conn.execute(query, args).fetchall()
        results = []
        for r in reversed(rows):
            attachment = conn.execute("SELECT * FROM chat_attachments WHERE message_id=? ORDER BY created_at LIMIT 1", (r["id"],)).fetchone()
            mentions = [dict(x) for x in conn.execute("SELECT m.user_id AS id,u.name FROM chat_message_mentions m JOIN users u ON u.id=m.user_id WHERE m.message_id=?", (r["id"],)).fetchall()]
            resource = None
            if r["resource_type"] and r["resource_id"]:
                # Titles are re-resolved under the current viewer's access rights.
                try: resource = _chat_resource(conn, user, r["resource_type"], r["resource_id"])
                except HTTPException: resource = {"type": r["resource_type"], "id": r["resource_id"], "title": "مورد دیگر در دسترس نیست"}
            results.append({"id": r["id"], "body": "این پیام حذف شده است." if r["deleted_at"] else r["body"],
                "userId": r["user_id"], "userName": r["user_name"], "avatarUrl": f"/api/users/{r['user_id']}/avatar?v={r['avatar_updated_at'] or ''}" if r["avatar_key"] else None,
                "createdAt": r["created_at"], "editedAt": r["edited_at"], "deleted": bool(r["deleted_at"]),
                "replyTo": {"userName": r["reply_user_name"], "body": r["reply_body"]} if r["reply_to_id"] else None,
                "attachment": _chat_attachment_public(attachment) if attachment and not r["deleted_at"] else None,
                "resource": resource, "mentions": mentions})
        return {"items": results}


@app.post("/api/chat/uploads")
async def upload_chat_attachment(request: Request, channel_type: str = "workspace", team_id: str | None = None,
                                 user: dict[str, Any] = Depends(require_permission("chat.send"))) -> dict[str, Any]:
    with db() as conn: _chat_channel_access(conn, user, channel_type, team_id)
    raw_name = unquote(request.headers.get("x-file-name", "attachment.bin"))
    safe_name = Path(raw_name.replace("\\", "/")).name.strip() or "attachment.bin"
    ext = Path(safe_name).suffix.lower()
    if ext not in CHAT_ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="نوع فایل برای گفتگوی تیمی پشتیبانی نمی‌شود.")
    if ext == ".svg": raise HTTPException(status_code=415, detail="فایل SVG برای ارسال مستقیم مجاز نیست.")
    # Never trust the browser-supplied MIME type for inline rendering. Infer it
    # from the allow-listed extension so an uploaded HTML/SVG payload cannot
    # ask the browser to render as an active document.
    content_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    if ext == ".md": content_type = "text/markdown"
    if ext in {".m4a", ".oga"} and content_type == "application/octet-stream": content_type = "audio/mp4" if ext == ".m4a" else "audio/ogg"
    attachment_id = new_id(); folder = CHAT_DIR / user["workspace_id"]; folder.mkdir(parents=True, exist_ok=True)
    stored_name = f"{attachment_id}{ext}"; path = folder / stored_name; total = 0
    try:
        with path.open("wb") as handle:
            async for chunk in request.stream():
                if not chunk: continue
                total += len(chunk)
                if total > MAX_CHAT_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="حداکثر حجم هر پیوست گفتگو ۲۵ مگابایت است.")
                handle.write(chunk)
        if not total: raise HTTPException(status_code=400, detail="فایل خالی است.")
        stamp = now_iso()
        with db() as conn:
            # Expire abandoned pre-uploads after one day.
            stale = conn.execute("SELECT id,workspace_id,stored_name FROM chat_attachments WHERE message_id IS NULL AND created_at<?", ((datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),)).fetchall()
            for old in stale:
                (CHAT_DIR / old["workspace_id"] / old["stored_name"]).unlink(missing_ok=True)
                conn.execute("DELETE FROM chat_attachments WHERE id=?", (old["id"],))
            conn.execute("INSERT INTO chat_attachments(id,workspace_id,uploaded_by,channel_type,team_id,message_id,original_name,stored_name,content_type,size_bytes,created_at) VALUES(?,?,?,?,?,NULL,?,?,?,?,?)",
                (attachment_id,user["workspace_id"],user["user_id"],channel_type,team_id if channel_type=="team" else None,safe_name,stored_name,content_type,total,stamp))
        return {"id": attachment_id, "name": safe_name, "contentType": content_type, "sizeBytes": total,
                "url": f"/api/chat/attachments/{attachment_id}"}
    except Exception:
        path.unlink(missing_ok=True)
        raise


@app.get("/api/chat/attachments/{attachment_id}")
def download_chat_attachment(attachment_id: str, download: bool = False,
                             user: dict[str, Any] = Depends(current_user)) -> FileResponse:
    with db() as conn:
        row = conn.execute("SELECT a.*,m.channel_type AS message_channel,m.team_id AS message_team,m.deleted_at FROM chat_attachments a LEFT JOIN chat_messages m ON m.id=a.message_id WHERE a.id=? AND a.workspace_id=?", (attachment_id,user["workspace_id"])).fetchone()
        if not row or not row["message_id"] or row["deleted_at"]: raise HTTPException(status_code=404, detail="پیوست گفتگو پیدا نشد.")
        channel_type = row["message_channel"] or row["channel_type"]
        team_id = row["message_team"] if row["message_channel"] else row["team_id"]
        _chat_channel_access(conn,user,channel_type,team_id)
        path = CHAT_DIR / user["workspace_id"] / row["stored_name"]
        if not path.is_file(): raise HTTPException(status_code=404,detail="فایل پیوست در دسترس نیست.")
        safe_inline = row["content_type"].startswith(("image/", "audio/", "video/"))
        disposition = "attachment" if download or not safe_inline else "inline"
        return FileResponse(path, media_type=row["content_type"], filename=row["original_name"], content_disposition_type=disposition)


@app.get("/api/chat/resources")
def search_chat_resources(q: str = "", user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    needle = f"%{q.strip()[:80]}%"
    with db() as conn:
        items: list[dict[str, Any]] = []
        for r in conn.execute("SELECT id,title FROM tasks WHERE workspace_id=? AND title LIKE ? ORDER BY updated_at DESC LIMIT 30", (user["workspace_id"],needle)):
            items.append({"type":"task","id":r["id"],"title":r["title"]})
        for r in conn.execute("SELECT id,name AS title FROM projects WHERE workspace_id=? AND name LIKE ? ORDER BY updated_at DESC LIMIT 20", (user["workspace_id"],needle)):
            items.append({"type":"project","id":r["id"],"title":r["title"]})
        for r in conn.execute("SELECT * FROM shared_nodes WHERE workspace_id=? AND node_type IN ('text','file') AND title LIKE ? ORDER BY updated_at DESC LIMIT 40", (user["workspace_id"],needle)):
            try:
                check_node_access(conn,r,user)
                items.append({"type":"note" if r["node_type"]=="text" else "file","id":r["id"],"title":r["title"]})
            except HTTPException: pass
        for r in conn.execute("SELECT * FROM shared_boards WHERE workspace_id=? AND title LIKE ? ORDER BY updated_at DESC LIMIT 20", (user["workspace_id"],needle)):
            try:
                require_board_access(conn,r,user)
                items.append({"type":"board","id":r["id"],"title":r["title"]})
            except HTTPException: pass
        return {"items":items[:80]}


def _validate_chat_reply(conn: sqlite3.Connection, user: dict[str, Any], channel_type: str, team_id: str | None, reply_to_id: str | None) -> None:
    if not reply_to_id: return
    row = conn.execute("SELECT channel_type,team_id FROM chat_messages WHERE id=? AND workspace_id=? AND deleted_at IS NULL", (reply_to_id,user["workspace_id"])).fetchone()
    if not row or row["channel_type"] != channel_type or (channel_type == "team" and row["team_id"] != team_id):
        raise HTTPException(status_code=422, detail="پیام مبنا برای پاسخ معتبر نیست.")


@app.post("/api/chat")
def post_chat(payload: ChatMessageInput, user: dict[str, Any] = Depends(require_permission("chat.send"))) -> dict[str, Any]:
    body = payload.body.strip()
    if len(body) > 10000: raise HTTPException(status_code=422,detail="متن پیام بیش از حد طولانی است.")
    with db() as conn:
        _chat_channel_access(conn,user,payload.channel_type,payload.team_id)
        _validate_chat_reply(conn,user,payload.channel_type,payload.team_id,payload.reply_to_id)
        attachment = None
        if payload.attachment_id:
            attachment = conn.execute("SELECT * FROM chat_attachments WHERE id=? AND workspace_id=? AND uploaded_by=? AND message_id IS NULL AND channel_type=? AND COALESCE(team_id,'')=COALESCE(?,'')",
                (payload.attachment_id,user["workspace_id"],user["user_id"],payload.channel_type,payload.team_id)).fetchone()
            if not attachment: raise HTTPException(status_code=404,detail="پیوست آماده ارسال پیدا نشد.")
        resource = _chat_resource(conn,user,payload.resource_type,payload.resource_id)
        if not body and not attachment and not resource: raise HTTPException(status_code=422,detail="پیام باید متن، فایل یا پیوند داشته باشد.")
        mentions = list(dict.fromkeys(x for x in payload.mentions if x and x != user["user_id"]))
        if len(mentions) > 50: raise HTTPException(status_code=422,detail="تعداد اشاره‌ها بیش از حد مجاز است.")
        valid_mentions = []
        for target_id in mentions:
            membership = conn.execute("SELECT role FROM memberships WHERE workspace_id=? AND user_id=?", (user["workspace_id"],target_id)).fetchone()
            if not membership: continue
            if payload.channel_type == "team" and not _team_member(conn, payload.team_id, {"user_id": target_id, "role": membership["role"]}):
                continue
            valid_mentions.append(target_id)
        msg_id,stamp=new_id(),now_iso()
        conn.execute("INSERT INTO chat_messages(id,workspace_id,channel_type,team_id,user_id,body,created_at,reply_to_id,resource_type,resource_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (msg_id,user["workspace_id"],payload.channel_type,payload.team_id if payload.channel_type=="team" else None,user["user_id"],body,stamp,payload.reply_to_id,resource["type"] if resource else None,resource["id"] if resource else None))
        if attachment: conn.execute("UPDATE chat_attachments SET message_id=? WHERE id=?",(msg_id,attachment["id"]))
        for target_id in valid_mentions:
            conn.execute("INSERT OR IGNORE INTO chat_message_mentions(message_id,user_id) VALUES(?,?)",(msg_id,target_id))
            create_notification(conn,user["workspace_id"],target_id,user["user_id"],"mention","در یک پیام از شما نام برده شد",body[:240],"chat",msg_id)
        log_activity(conn,user["workspace_id"],user["user_id"],"chat",msg_id,"chat.message","پیام تازه‌ای در گفتگوی تیمی ثبت شد")
        return {"id":msg_id,"createdAt":stamp}


@app.patch("/api/chat/{message_id}")
def edit_chat_message(message_id: str,payload: ChatMessageEditInput,user: dict[str,Any] = Depends(current_user)) -> dict[str,bool]:
    with db() as conn:
        row=conn.execute("SELECT * FROM chat_messages WHERE id=? AND workspace_id=? AND deleted_at IS NULL",(message_id,user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404,detail="پیام پیدا نشد.")
        _chat_channel_access(conn,user,row["channel_type"],row["team_id"])
        if row["user_id"] != user["user_id"] and not has_permission(user,"chat.moderate"):
            raise HTTPException(status_code=403,detail="فقط نویسنده یا ناظر گفتگو می‌تواند پیام را ویرایش کند.")
        body = payload.body.strip()
        if not body: raise HTTPException(status_code=422, detail="متن پیام نمی‌تواند خالی باشد.")
        previous = {r["user_id"] for r in conn.execute("SELECT user_id FROM chat_message_mentions WHERE message_id=?", (message_id,)).fetchall()}
        requested = list(dict.fromkeys(x for x in payload.mentions if x and x != user["user_id"]))
        if len(requested) > 50: raise HTTPException(status_code=422, detail="تعداد اشاره‌ها بیش از حد مجاز است.")
        valid = []
        for target_id in requested:
            membership = conn.execute("SELECT role FROM memberships WHERE workspace_id=? AND user_id=?", (user["workspace_id"], target_id)).fetchone()
            if not membership: continue
            if row["channel_type"] == "team" and not _team_member(conn, row["team_id"], {"user_id": target_id, "role": membership["role"]}): continue
            valid.append(target_id)
        conn.execute("DELETE FROM chat_message_mentions WHERE message_id=?", (message_id,))
        for target_id in valid:
            conn.execute("INSERT INTO chat_message_mentions(message_id,user_id) VALUES(?,?)", (message_id,target_id))
            if target_id not in previous:
                create_notification(conn,user["workspace_id"],target_id,user["user_id"],"mention","در یک پیام از شما نام برده شد",body[:240],"chat",message_id)
        conn.execute("UPDATE chat_messages SET body=?,edited_at=? WHERE id=?",(body,now_iso(),message_id))
        log_activity(conn,user["workspace_id"],user["user_id"],"chat",message_id,"chat.message.edited","یک پیام ویرایش شد")
    return {"ok":True}


@app.delete("/api/chat/{message_id}")
def delete_chat_message(message_id: str,user: dict[str,Any] = Depends(current_user)) -> dict[str,bool]:
    file_to_remove=[]
    with db() as conn:
        row=conn.execute("SELECT * FROM chat_messages WHERE id=? AND workspace_id=? AND deleted_at IS NULL",(message_id,user["workspace_id"])).fetchone()
        if not row: raise HTTPException(status_code=404,detail="پیام پیدا نشد.")
        _chat_channel_access(conn,user,row["channel_type"],row["team_id"])
        if row["user_id"] != user["user_id"] and not has_permission(user,"chat.moderate"):
            raise HTTPException(status_code=403,detail="فقط نویسنده یا ناظر گفتگو می‌تواند پیام را حذف کند.")
        attachments=conn.execute("SELECT id,stored_name FROM chat_attachments WHERE message_id=?",(message_id,)).fetchall()
        file_to_remove=[CHAT_DIR/user["workspace_id"]/a["stored_name"] for a in attachments]
        conn.execute("DELETE FROM chat_attachments WHERE message_id=?",(message_id,))
        conn.execute("UPDATE chat_messages SET body='',deleted_at=? WHERE id=?",(now_iso(),message_id))
        conn.execute("DELETE FROM chat_message_mentions WHERE message_id=?",(message_id,))
        log_activity(conn,user["workspace_id"],user["user_id"],"chat",message_id,"chat.message.deleted","یک پیام حذف شد")
    for path in file_to_remove: path.unlink(missing_ok=True)
    return {"ok":True}


@app.post("/api/presence")
def update_presence(payload: PresenceInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    stamp = now_iso()
    team_id = payload.team_id
    with db() as conn:
        if team_id and not conn.execute("SELECT 1 FROM team_members WHERE team_id=? AND user_id=?", (team_id,user["user_id"])).fetchone() and user["role"] not in ("owner","admin"):
            raise HTTPException(status_code=403, detail="برای حضور در این تیم باید عضو آن باشید.")
        if team_id and not conn.execute("SELECT 1 FROM teams WHERE id=? AND workspace_id=?", (team_id,user["workspace_id"])).fetchone():
            raise HTTPException(status_code=404, detail="تیم پیدا نشد.")
        conn.execute("""INSERT INTO workspace_presence(workspace_id,user_id,page,last_seen,active_team_id)
            VALUES(?,?,?,?,?) ON CONFLICT(workspace_id,user_id) DO UPDATE SET page=excluded.page,last_seen=excluded.last_seen,active_team_id=excluded.active_team_id""",
            (user["workspace_id"],user["user_id"],payload.page,stamp,team_id))
        conn.execute("DELETE FROM workspace_presence WHERE workspace_id=? AND last_seen<?",
                     (user["workspace_id"],(datetime.now(timezone.utc)-timedelta(minutes=3)).isoformat()))
    return {"ok":True}


@app.post("/api/presence/cursor")
def update_cursor(payload: CursorInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    stamp = now_iso()
    palette = ["#C65C42", "#397C83", "#8B6BB1", "#B27A31", "#4F805F", "#B34C73", "#63799B"]
    color = palette[int(hashlib.sha256(user["user_id"].encode()).hexdigest()[:8],16) % len(palette)]
    team_id = payload.team_id
    with db() as conn:
        if team_id and not conn.execute("SELECT 1 FROM teams WHERE id=? AND workspace_id=?", (team_id,user["workspace_id"])).fetchone():
            team_id = None
        conn.execute("""INSERT INTO workspace_presence(workspace_id,user_id,page,last_seen,active_team_id,cursor_x_pct,cursor_y_pct,cursor_page,cursor_color)
            VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(workspace_id,user_id) DO UPDATE SET last_seen=excluded.last_seen,
            active_team_id=excluded.active_team_id,cursor_x_pct=excluded.cursor_x_pct,cursor_y_pct=excluded.cursor_y_pct,
            cursor_page=excluded.cursor_page,cursor_color=excluded.cursor_color""",
            (user["workspace_id"],user["user_id"],payload.page,stamp,team_id,payload.x_pct,payload.y_pct,payload.page,color))
    return {"ok":True}


@app.get("/api/presence")
def get_presence(team_id: str | None = None, user: dict[str, Any] = Depends(current_user)) -> dict[str,Any]:
    cutoff = (datetime.now(timezone.utc)-timedelta(seconds=45)).isoformat()
    with db() as conn:
        if team_id:
            rows = conn.execute("""SELECT p.user_id,u.name,u.avatar_key,u.avatar_updated_at,p.page,p.last_seen,p.active_team_id,
                p.cursor_x_pct,p.cursor_y_pct,p.cursor_page,p.cursor_color,m.role,m.custom_role_id,cr.name AS role_name,cr.color AS role_color
                FROM workspace_presence p JOIN users u ON u.id=p.user_id
                JOIN team_members tm ON tm.user_id=u.id AND tm.team_id=?
                JOIN memberships m ON m.user_id=u.id AND m.workspace_id=p.workspace_id
                LEFT JOIN workspace_custom_roles cr ON cr.id=m.custom_role_id
                WHERE p.workspace_id=? AND p.last_seen>? ORDER BY u.name""",(team_id,user["workspace_id"],cutoff)).fetchall()
        else:
            rows = conn.execute("""SELECT p.user_id,u.name,u.avatar_key,u.avatar_updated_at,p.page,p.last_seen,p.active_team_id,
                p.cursor_x_pct,p.cursor_y_pct,p.cursor_page,p.cursor_color,m.role,m.custom_role_id,cr.name AS role_name,cr.color AS role_color
                FROM workspace_presence p JOIN users u ON u.id=p.user_id
                JOIN memberships m ON m.user_id=u.id AND m.workspace_id=p.workspace_id
                LEFT JOIN workspace_custom_roles cr ON cr.id=m.custom_role_id
                WHERE p.workspace_id=? AND p.last_seen>? ORDER BY u.name""",(user["workspace_id"],cutoff)).fetchall()
        items=[]
        for row in rows:
            item=dict(row)
            item["avatarUrl"] = f"/api/users/{row['user_id']}/avatar?v={row['avatar_updated_at'] or ''}" if row['avatar_key'] else None
            item["roleName"] = row["role_name"] or {"owner":"مالک","admin":"مدیر","member":"عضو"}.get(row["role"],"عضو")
            item["roleColor"] = row["role_color"]
            items.append(item)
        return {"items":items,"onlineCount":len(items)}


@app.api_route("/", methods=["GET", "HEAD"])
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")



# ---------------------------------------------------------------------------
# BottleNeck v0.6.0: operations, account security and multi-workspace support.
# ---------------------------------------------------------------------------
PERMISSION_KEYS = {
    "workspace.manage", "members.invite", "members.manage", "teams.manage",
    "backups.manage", "permissions.manage", "shared.manage", "reports.view", "chat.moderate",
    "tasks.create", "tasks.update", "tasks.delete", "comments.create", "chat.send",
    "boards.manage", "drive.manage", "projects.delete", "projects.create", "projects.update",
    "recurring.manage", "templates.manage", "approvals.manage", "tasks.checklist",
    "tasks.attachments", "tasks.dependencies", "tasks.time",
}
DEFAULT_ROLE_PERMISSIONS = {
    "owner": set(PERMISSION_KEYS),
    "admin": set(PERMISSION_KEYS) - {"permissions.manage"},
    "member": {"reports.view", "tasks.create", "tasks.update", "comments.create", "chat.send",
               "tasks.checklist", "tasks.attachments", "tasks.dependencies", "tasks.time"},
}
BACKUP_RETENTION = max(2, int(os.getenv("BOTTLENECK_BACKUP_RETENTION", "14")))
BACKUP_INTERVAL_HOURS = max(1, int(os.getenv("BOTTLENECK_BACKUP_INTERVAL_HOURS", "24")))


def _seed_all_workspace_permissions() -> None:
    stamp = now_iso()
    with db() as conn:
        workspace_ids = [r["id"] for r in conn.execute("SELECT id FROM workspaces").fetchall()]
        for workspace_id in workspace_ids:
            for role, allowed_keys in DEFAULT_ROLE_PERMISSIONS.items():
                for permission in PERMISSION_KEYS:
                    conn.execute("""INSERT OR IGNORE INTO workspace_role_permissions
                        (workspace_id,role,permission_key,allowed,updated_at) VALUES(?,?,?,?,?)""",
                        (workspace_id, role, permission, 1 if permission in allowed_keys else 0, stamp))


def _create_workspace_defaults(conn: sqlite3.Connection, workspace_id: str, owner_id: str) -> None:
    stamp = now_iso()
    conn.execute("INSERT OR IGNORE INTO workspace_settings(workspace_id,created_at) VALUES(?,?)", (workspace_id, stamp))
    for key, label, color, position in [("todo", "در صف", "neutral", 0), ("in-progress", "در حال انجام", "blue", 1),
        ("review", "در بررسی", "gold", 2), ("blocked", "متوقف‌شده", "red", 3), ("done", "تکمیل‌شده", "green", 4)]:
        conn.execute("""INSERT OR IGNORE INTO workspace_status_labels
            (workspace_id,status_key,label,color,position,updated_at) VALUES(?,?,?,?,?,?)""",
            (workspace_id, key, label, color, position, stamp))
    team_id = new_id()
    conn.execute("INSERT INTO teams(id,workspace_id,name,description,created_at) VALUES(?,?,?,?,?)",
                 (team_id, workspace_id, "عمومی", "تیم پیش‌فرض فضای کاری", stamp))
    conn.execute("INSERT OR IGNORE INTO team_members(team_id,user_id,created_at) VALUES(?,?,?)", (team_id, owner_id, stamp))
    for role, allowed_keys in DEFAULT_ROLE_PERMISSIONS.items():
        for permission in PERMISSION_KEYS:
            conn.execute("""INSERT OR IGNORE INTO workspace_role_permissions
                (workspace_id,role,permission_key,allowed,updated_at) VALUES(?,?,?,?,?)""",
                (workspace_id, role, permission, 1 if permission in allowed_keys else 0, stamp))


def _totp_code(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 1_000_000).zfill(6)


def verify_totp(secret: str | None, code: str) -> bool:
    if not secret or not code or not code.isdigit():
        return False
    counter = int(time.time() // 30)
    return any(hmac.compare_digest(_totp_code(secret, counter + drift), code.zfill(6)) for drift in (-1, 0, 1))


def _verify_totp_or_recovery(conn: sqlite3.Connection, user_id: str, secret: str | None, code: str) -> bool:
    if verify_totp(secret, code):
        return True
    normalized = re.sub(r"[^A-Fa-f0-9]", "", code or "").upper()
    if len(normalized) != 8:
        return False
    row = conn.execute("SELECT id FROM totp_recovery_codes WHERE user_id=? AND code_hash=? AND used_at IS NULL",
                       (user_id, hash_token(normalized))).fetchone()
    if not row:
        return False
    conn.execute("UPDATE totp_recovery_codes SET used_at=? WHERE id=? AND used_at IS NULL", (now_iso(), row["id"]))
    return True


def _send_email(to_email: str, subject: str, body: str) -> bool:
    host = os.getenv("BOTTLENECK_SMTP_HOST", "").strip()
    sender = os.getenv("BOTTLENECK_SMTP_FROM", "").strip()
    if not host or not sender:
        return False
    port = int(os.getenv("BOTTLENECK_SMTP_PORT", "587"))
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if os.getenv("BOTTLENECK_SMTP_STARTTLS", "1") == "1":
            smtp.starttls()
        smtp_user = os.getenv("BOTTLENECK_SMTP_USER", "")
        smtp_password = os.getenv("BOTTLENECK_SMTP_PASSWORD", "")
        if smtp_user:
            smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)
    return True


def _new_password_reset(conn: sqlite3.Connection, user_id: str) -> str:
    token = secrets.token_urlsafe(42)
    conn.execute("INSERT INTO password_reset_tokens(id,user_id,token_hash,expires_at,created_at) VALUES(?,?,?,?,?)",
                 (new_id(), user_id, hash_token(token), (datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat(), now_iso()))
    return token


def _build_backup(created_by: str | None = None, automatic: bool = False) -> dict[str, Any]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_id = new_id()
    filename = f"bottleneck-backup-{stamp}-{backup_id[:8]}.zip"
    target = BACKUP_DIR / filename
    with tempfile.TemporaryDirectory(prefix="bottleneck-backup-") as tmp_dir:
        tmp = Path(tmp_dir)
        db_copy = tmp / "bottleneck.sqlite3"
        if DB_PATH.exists():
            src = sqlite3.connect(DB_PATH, timeout=30)
            dst = sqlite3.connect(db_copy)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
        else:
            raise RuntimeError("Database file is not present yet.")
        manifest = {
            "application": "BottleNeck", "version": APP_VERSION,
            "createdAt": now_iso(), "includes": ["sqlite-database", "uploads", "shared-files", "chat-uploads"],
            "restore": "Stop BottleNeck, extract this archive, and restore the database and data folders as described in HANDBOOK.md.",
        }
        (tmp / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.write(db_copy, "data/bottleneck.sqlite3")
            zf.write(tmp / "manifest.json", "manifest.json")
            for folder, arc_root in ((UPLOAD_DIR, "data/uploads"), (SHARED_DIR, "data/shared"), (CHAT_DIR, "data/chat_uploads")):
                if folder.exists():
                    for file_path in folder.rglob("*"):
                        if file_path.is_file():
                            zf.write(file_path, f"{arc_root}/{file_path.relative_to(folder).as_posix()}")
    size = target.stat().st_size
    with db() as conn:
        conn.execute("INSERT INTO backup_catalog(id,filename,size_bytes,created_by,created_at,is_automatic) VALUES(?,?,?,?,?,?)",
                     (backup_id, filename, size, created_by, now_iso(), 1 if automatic else 0))
    # Retain the newest configured number of backups.
    with db() as conn:
        retention = _server_setting_int("backup_retention", BACKUP_RETENTION, minimum=2, maximum=100)
        old = conn.execute("SELECT id,filename FROM backup_catalog ORDER BY created_at DESC LIMIT -1 OFFSET ?", (retention,)).fetchall()
        for row in old:
            (BACKUP_DIR / row["filename"]).unlink(missing_ok=True)
            conn.execute("DELETE FROM backup_catalog WHERE id=?", (row["id"],))
    return {"id": backup_id, "filename": filename, "sizeBytes": size, "createdAt": now_iso(), "automatic": automatic}


async def _recurring_scheduler() -> None:
    while _background_stop and not _background_stop.is_set():
        try:
            with db() as conn:
                ids = [r["id"] for r in conn.execute("SELECT id FROM workspaces").fetchall()]
            for workspace_id in ids:
                try:
                    generate_due_recurring(workspace_id)
                except Exception as exc:
                    print(f"[BottleNeck scheduler] recurring workspace {workspace_id}: {exc}")
        except Exception as exc:
            print(f"[BottleNeck scheduler] recurring scan: {exc}")
        try:
            await asyncio.wait_for(_background_stop.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass


async def _backup_scheduler() -> None:
    while _background_stop and not _background_stop.is_set():
        try:
            with db() as conn:
                user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                latest = conn.execute("SELECT created_at FROM backup_catalog ORDER BY created_at DESC LIMIT 1").fetchone()
            if not user_count:
                try:
                    await asyncio.wait_for(_background_stop.wait(), timeout=60)
                except asyncio.TimeoutError:
                    pass
                continue
            due = not latest
            if latest:
                try:
                    interval_hours = _server_setting_int("backup_interval_hours", BACKUP_INTERVAL_HOURS, minimum=1, maximum=720)
                    due = datetime.fromisoformat(latest["created_at"]) < datetime.now(timezone.utc) - timedelta(hours=interval_hours)
                except ValueError:
                    due = True
            if due:
                await asyncio.to_thread(_build_backup, None, True)
        except Exception as exc:
            print(f"[BottleNeck backups] automatic backup failed: {exc}")
        try:
            await asyncio.wait_for(_background_stop.wait(), timeout=1800)
        except asyncio.TimeoutError:
            pass


async def _notification_mailer() -> None:
    while _background_stop and not _background_stop.is_set():
        try:
            if os.getenv("BOTTLENECK_SMTP_HOST"):
                with db() as conn:
                    rows = conn.execute("""SELECT j.id,j.notification_id,u.email,n.title,n.body,n.kind,p.email_enabled,
                        CASE n.kind WHEN 'assignment' THEN p.assigned_enabled WHEN 'mention' THEN p.mentions_enabled
                        WHEN 'deadline' THEN p.deadlines_enabled ELSE 1 END AS category_enabled
                        FROM notification_email_jobs j JOIN users u ON u.id=j.user_id
                        JOIN notifications n ON n.id=j.notification_id
                        LEFT JOIN notification_preferences p ON p.user_id=j.user_id
                        WHERE j.status='pending' ORDER BY j.created_at LIMIT 30""").fetchall()
                for row in rows:
                    if not row["email_enabled"] or not row["category_enabled"]:
                        with db() as conn:
                            conn.execute("UPDATE notification_email_jobs SET status='skipped' WHERE id=?", (row["id"],))
                        continue
                    try:
                        sent = await asyncio.to_thread(_send_email, row["email"], f"BottleNeck: {row['title']}", row["body"] or row["title"])
                        with db() as conn:
                            conn.execute("UPDATE notification_email_jobs SET status=?,attempts=attempts+1,sent_at=?,last_error='' WHERE id=?",
                                         ("sent" if sent else "skipped", now_iso() if sent else None, row["id"]))
                    except Exception as exc:
                        with db() as conn:
                            conn.execute("UPDATE notification_email_jobs SET attempts=attempts+1,last_error=?,status=CASE WHEN attempts>=4 THEN 'failed' ELSE 'pending' END WHERE id=?",
                                         (str(exc)[:500], row["id"]))
        except Exception as exc:
            print(f"[BottleNeck email] delivery loop: {exc}")
        try:
            await asyncio.wait_for(_background_stop.wait(), timeout=15)
        except asyncio.TimeoutError:
            pass


@app.get("/api/workspaces")
def list_user_workspaces(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute("""SELECT w.id,w.name,w.created_at,m.role FROM memberships m JOIN workspaces w ON w.id=m.workspace_id
            WHERE m.user_id=? ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,w.name""", (user["user_id"],)).fetchall()
    return {"items": [dict(r) for r in rows], "currentId": user["workspace_id"]}


@app.post("/api/workspaces")
def create_workspace(payload: WorkspaceCreateInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    workspace_id = new_id()
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="نام فضای کار کوتاه است.")
    with db() as conn:
        conn.execute("INSERT INTO workspaces(id,name,created_by,created_at) VALUES(?,?,?,?)", (workspace_id, name, user["user_id"], now_iso()))
        conn.execute("INSERT INTO memberships(id,workspace_id,user_id,role,joined_at) VALUES(?,?,?,?,?)", (new_id(), workspace_id, user["user_id"], "owner", now_iso()))
        _create_workspace_defaults(conn, workspace_id, user["user_id"])
        log_activity(conn, workspace_id, user["user_id"], "workspace", workspace_id, "created", f"فضای کاری «{name}» ساخته شد.")
    return {"id": workspace_id, "name": name}


@app.post("/api/workspaces/switch")
def switch_workspace(payload: WorkspaceSwitchInput, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="نشست معتبر نیست.")
    with db() as conn:
        member = conn.execute("SELECT 1 FROM memberships WHERE user_id=? AND workspace_id=?", (user["user_id"], payload.workspace_id)).fetchone()
        if not member:
            raise HTTPException(status_code=403, detail="شما عضو این فضای کاری نیستید.")
        conn.execute("UPDATE sessions SET workspace_id=? WHERE token_hash=? AND user_id=?", (payload.workspace_id, hash_token(token), user["user_id"]))
    return {"ok": True, "workspaceId": payload.workspace_id}


def _accept_workspace_invitation(token: str, request: Request, user: dict[str, Any]) -> dict[str, Any]:
    with db() as conn:
        invite = conn.execute("SELECT * FROM invitations WHERE token_hash=? AND accepted_at IS NULL AND expires_at>?", (hash_token(token), now_iso())).fetchone()
        if not invite:
            raise HTTPException(status_code=404, detail="دعوت‌نامه معتبر نیست یا منقضی شده است.")
        if invite["email"].lower() != user["email"].lower():
            raise HTTPException(status_code=403, detail="ایمیل حساب شما با ایمیل دعوت‌شده یکسان نیست.")
        conn.execute("INSERT OR IGNORE INTO memberships(id,workspace_id,user_id,role,joined_at) VALUES(?,?,?,?,?)",
                     (new_id(), invite["workspace_id"], user["user_id"], invite["role"], now_iso()))
        conn.execute("UPDATE invitations SET accepted_at=? WHERE id=?", (now_iso(), invite["id"]))
        session_token = request.cookies.get(COOKIE_NAME)
        if session_token:
            conn.execute("UPDATE sessions SET workspace_id=? WHERE token_hash=? AND user_id=?",
                         (invite["workspace_id"], hash_token(session_token), user["user_id"]))
        default_team = conn.execute("SELECT id FROM teams WHERE workspace_id=? ORDER BY created_at LIMIT 1", (invite["workspace_id"],)).fetchone()
        if default_team:
            conn.execute("INSERT OR IGNORE INTO team_members(team_id,user_id,created_at) VALUES(?,?,?)", (default_team["id"], user["user_id"], now_iso()))
        log_activity(conn, invite["workspace_id"], user["user_id"], "member", user["user_id"], "joined", f"{user['name']} به فضای کار پیوست.")
    return {"ok": True, "workspaceId": invite["workspace_id"]}


@app.post("/api/invitations/accept")
def accept_workspace_invitation_body(payload: LinkTokenInput, request: Request,
                                    user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return _accept_workspace_invitation(payload.token, request, user)


@app.post("/api/invitations/{token}/accept")
def accept_workspace_invitation(token: str, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return _accept_workspace_invitation(token, request, user)


@app.post("/api/workspace-join-codes")
def create_workspace_join_code(payload: JoinCodeCreateInput, user: dict[str, Any] = Depends(require_permission("members.invite"))) -> dict[str, Any]:
    role = payload.role if payload.role in {"admin","member"} else "member"
    if role == "admin" and user["role"] != "owner":
        raise HTTPException(status_code=403, detail="فقط مالک می‌تواند کد عضویت مدیر بسازد.")
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code = "".join(secrets.choice(alphabet) for _ in range(8))
    code_id = new_id(); stamp=now_iso(); expires=(datetime.now(timezone.utc)+timedelta(minutes=15)).replace(microsecond=0).isoformat()
    with db() as conn:
        conn.execute("INSERT INTO workspace_join_codes(id,workspace_id,role,token_hash,created_by,expires_at,max_uses,created_at) VALUES(?,?,?,?,?,?,?,?)",
                     (code_id,user["workspace_id"],role,hash_token(code),user["user_id"],expires,payload.max_uses,stamp))
        log_activity(conn,user["workspace_id"],user["user_id"],"join_code",code_id,"created","کد عضویت ۱۵ دقیقه‌ای ساخته شد.")
    return {"id":code_id,"code":code,"role":role,"expiresAt":expires,"maxUses":payload.max_uses}


@app.post("/api/workspace-join-codes/accept")
def accept_workspace_join_code(payload: JoinCodeAcceptInput, request: Request, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    code = re.sub(r"[^A-Za-z0-9]", "", payload.code).upper()
    if len(code) != 8:
        raise HTTPException(status_code=400, detail="کد عضویت معتبر نیست.")
    stamp = now_iso()
    error_status: int | None = None
    error_message = ""
    workspace_id = ""
    already_member = False
    with db() as conn:
        attempt = conn.execute("SELECT * FROM join_code_attempts WHERE user_id=?", (user["user_id"],)).fetchone()
        now_dt = datetime.now(timezone.utc)
        if attempt:
            try:
                window = datetime.fromisoformat(attempt["window_started"])
            except ValueError:
                window = now_dt - timedelta(minutes=10)
            if now_dt - window > timedelta(minutes=10):
                conn.execute("UPDATE join_code_attempts SET window_started=?,attempts=0 WHERE user_id=?", (stamp, user["user_id"]))
            elif attempt["attempts"] >= 12:
                error_status, error_message = 429, "تلاش‌های زیادی انجام شده است؛ ۱۰ دقیقه دیگر امتحان کنید."
        else:
            conn.execute("INSERT INTO join_code_attempts(user_id,window_started,attempts) VALUES(?,?,0)", (user["user_id"], stamp))
        if error_status is None:
            row = conn.execute("SELECT * FROM workspace_join_codes WHERE token_hash=? AND revoked_at IS NULL AND expires_at>?", (hash_token(code), stamp)).fetchone()
            if not row or row["use_count"] >= row["max_uses"]:
                conn.execute("UPDATE join_code_attempts SET attempts=attempts+1 WHERE user_id=?", (user["user_id"],))
                error_status, error_message = 404, "کد معتبر نیست یا زمان استفاده از آن به پایان رسیده است."
            else:
                workspace_id = row["workspace_id"]
                existing = conn.execute("SELECT 1 FROM memberships WHERE workspace_id=? AND user_id=?", (workspace_id, user["user_id"])).fetchone()
                already_member = bool(existing)
                changed = conn.execute("UPDATE workspace_join_codes SET use_count=use_count+1 WHERE id=? AND revoked_at IS NULL AND expires_at>? AND use_count<max_uses", (row["id"], stamp))
                if changed.rowcount != 1:
                    error_status, error_message = 409, "ظرفیت این کد در همین لحظه تکمیل شد؛ کد تازه بگیرید."
                else:
                    if not existing:
                        conn.execute("INSERT INTO memberships(id,workspace_id,user_id,role,joined_at) VALUES(?,?,?,?,?)", (new_id(), workspace_id, user["user_id"], row["role"], stamp))
                        team = conn.execute("SELECT id FROM teams WHERE workspace_id=? ORDER BY created_at LIMIT 1", (workspace_id,)).fetchone()
                        if team:
                            conn.execute("INSERT OR IGNORE INTO team_members(team_id,user_id,created_at) VALUES(?,?,?)", (team["id"], user["user_id"], stamp))
                        log_activity(conn, workspace_id, user["user_id"], "member", user["user_id"], "joined", "با کد عضویت ۱۵ دقیقه‌ای به فضای کار پیوست.")
                    token = request.cookies.get(COOKIE_NAME)
                    if token:
                        conn.execute("UPDATE sessions SET workspace_id=? WHERE token_hash=? AND user_id=?", (workspace_id, hash_token(token), user["user_id"]))
                    conn.execute("UPDATE join_code_attempts SET attempts=0,window_started=? WHERE user_id=?", (stamp, user["user_id"]))
    if error_status is not None:
        raise HTTPException(status_code=error_status, detail=error_message)
    return {"ok": True, "workspaceId": workspace_id, "alreadyMember": already_member}


@app.get("/api/workspace-join-codes")
def list_workspace_join_codes(user: dict[str, Any] = Depends(require_permission("members.manage"))) -> dict[str, Any]:
    with db() as conn:
        rows=conn.execute("SELECT id,role,expires_at,max_uses,use_count,created_at,revoked_at FROM workspace_join_codes WHERE workspace_id=? AND expires_at>? ORDER BY created_at DESC LIMIT 40",(user["workspace_id"],now_iso())).fetchall()
    return {"items":[dict(r) for r in rows]}


@app.delete("/api/workspace-join-codes/{code_id}")
def revoke_workspace_join_code(code_id: str, user: dict[str, Any] = Depends(require_permission("members.manage"))) -> dict[str,bool]:
    with db() as conn:
        cur=conn.execute("UPDATE workspace_join_codes SET revoked_at=? WHERE id=? AND workspace_id=? AND revoked_at IS NULL",(now_iso(),code_id,user["workspace_id"]))
        if not cur.rowcount: raise HTTPException(status_code=404,detail="کد عضویت پیدا نشد.")
    return {"ok":True}


@app.get("/api/custom-roles")
def list_custom_roles(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        rows=conn.execute("SELECT id,name,color,base_role,created_at FROM workspace_custom_roles WHERE workspace_id=? ORDER BY name",(user["workspace_id"],)).fetchall()
        result=[]
        for row in rows:
            perms=conn.execute("SELECT permission_key,allowed FROM workspace_custom_role_permissions WHERE role_id=? ORDER BY permission_key",(row["id"],)).fetchall()
            result.append({**dict(row),"permissions":[dict(p) for p in perms]})
    return {"items":result,"keys":sorted(PERMISSION_KEYS)}


@app.post("/api/custom-roles")
def create_custom_role(payload: CustomRoleCreateInput, user: dict[str, Any] = Depends(require_permission("permissions.manage"))) -> dict[str, Any]:
    if payload.base_role not in {"admin","member"}: raise HTTPException(status_code=422,detail="نقش پایه معتبر نیست.")
    invalid=set(payload.permissions)-PERMISSION_KEYS
    if invalid: raise HTTPException(status_code=422,detail="یکی از مجوزها معتبر نیست.")
    role_id=new_id(); stamp=now_iso()
    with db() as conn:
        try:
            conn.execute("INSERT INTO workspace_custom_roles(id,workspace_id,name,color,base_role,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
                         (role_id,user["workspace_id"],payload.name.strip(),payload.color,payload.base_role,user["user_id"],stamp))
        except sqlite3.IntegrityError: raise HTTPException(status_code=409,detail="نقشی با این نام از قبل وجود دارد.")
        for permission in PERMISSION_KEYS:
            conn.execute("INSERT INTO workspace_custom_role_permissions(workspace_id,role_id,permission_key,allowed,updated_by,updated_at) VALUES(?,?,?,?,?,?)",
                         (user["workspace_id"],role_id,permission,1 if permission in payload.permissions else 0,user["user_id"],stamp))
        log_activity(conn,user["workspace_id"],user["user_id"],"role",role_id,"created",f"نقش سفارشی «{payload.name.strip()}» ساخته شد.")
    return {"id":role_id,"name":payload.name.strip(),"color":payload.color,"base_role":payload.base_role}


@app.put("/api/custom-roles/{role_id}/permissions")
def update_custom_role_permissions(role_id: str, payload: CustomRolePermissionsInput, user: dict[str, Any] = Depends(require_permission("permissions.manage"))) -> dict[str,bool]:
    invalid=set(payload.permissions)-PERMISSION_KEYS
    if invalid: raise HTTPException(status_code=422,detail="یکی از مجوزها معتبر نیست.")
    stamp=now_iso()
    with db() as conn:
        role=conn.execute("SELECT id FROM workspace_custom_roles WHERE id=? AND workspace_id=?",(role_id,user["workspace_id"])).fetchone()
        if not role: raise HTTPException(status_code=404,detail="نقش پیدا نشد.")
        for permission in PERMISSION_KEYS:
            conn.execute("INSERT INTO workspace_custom_role_permissions(workspace_id,role_id,permission_key,allowed,updated_by,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(role_id,permission_key) DO UPDATE SET allowed=excluded.allowed,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
                         (user["workspace_id"],role_id,permission,1 if permission in payload.permissions else 0,user["user_id"],stamp))
    return {"ok":True}


@app.delete("/api/custom-roles/{role_id}")
def delete_custom_role(role_id: str, user: dict[str, Any] = Depends(require_permission("permissions.manage"))) -> dict[str,bool]:
    with db() as conn:
        role=conn.execute("SELECT name FROM workspace_custom_roles WHERE id=? AND workspace_id=?",(role_id,user["workspace_id"])).fetchone()
        if not role: raise HTTPException(status_code=404,detail="نقش پیدا نشد.")
        conn.execute("UPDATE memberships SET custom_role_id=NULL WHERE custom_role_id=? AND workspace_id=?",(role_id,user["workspace_id"]))
        conn.execute("DELETE FROM workspace_custom_roles WHERE id=?",(role_id,))
        log_activity(conn,user["workspace_id"],user["user_id"],"role",role_id,"deleted",f"نقش «{role['name']}» حذف شد و اعضا به نقش پایه برگشتند.")
    return {"ok":True}


@app.put("/api/members/{member_id}/role")
def assign_member_role(member_id: str, payload: MemberRoleInput, user: dict[str, Any] = Depends(require_permission("members.manage"))) -> dict[str,bool]:
    if member_id == user["user_id"]: raise HTTPException(status_code=400,detail="نقش مالک فعلی قابل تغییر نیست.")
    with db() as conn:
        member=conn.execute("SELECT role FROM memberships WHERE workspace_id=? AND user_id=?",(user["workspace_id"],member_id)).fetchone()
        if not member: raise HTTPException(status_code=404,detail="عضو پیدا نشد.")
        if member["role"] == "owner": raise HTTPException(status_code=403,detail="نقش مالک قابل تغییر نیست.")
        if payload.custom_role_id:
            custom=conn.execute("SELECT base_role FROM workspace_custom_roles WHERE id=? AND workspace_id=?",(payload.custom_role_id,user["workspace_id"])).fetchone()
            if not custom: raise HTTPException(status_code=404,detail="نقش سفارشی پیدا نشد.")
            conn.execute("UPDATE memberships SET role=?,custom_role_id=? WHERE workspace_id=? AND user_id=?",(custom["base_role"],payload.custom_role_id,user["workspace_id"],member_id))
        else:
            if payload.role not in {"admin","member"}: raise HTTPException(status_code=422,detail="نقش پایه معتبر نیست.")
            if payload.role == "admin" and user["role"] != "owner": raise HTTPException(status_code=403,detail="فقط مالک فضای کاری می‌تواند نقش پایه مدیر را واگذار کند.")
            conn.execute("UPDATE memberships SET role=?,custom_role_id=NULL WHERE workspace_id=? AND user_id=?",(payload.role,user["workspace_id"],member_id))
        log_activity(conn,user["workspace_id"],user["user_id"],"member",member_id,"role_changed","نقش یکی از اعضا تغییر کرد.")
    return {"ok":True}


@app.get("/api/permissions")
def get_role_permissions(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute("SELECT role,permission_key,allowed FROM workspace_role_permissions WHERE workspace_id=? ORDER BY role,permission_key", (user["workspace_id"],)).fetchall()
    return {"items": [dict(r) for r in rows], "keys": sorted(PERMISSION_KEYS)}


@app.put("/api/permissions")
def set_role_permissions(payload: RolePermissionsInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    if not has_permission(user, "permissions.manage"):
        raise HTTPException(status_code=403, detail="مجوز مدیریت نقش‌ها را ندارید.")
    stamp = now_iso()
    with db() as conn:
        for item in payload.items:
            if item.role not in {"admin", "member"} or item.permission not in PERMISSION_KEYS:
                raise HTTPException(status_code=422, detail="نقش یا مجوز معتبر نیست.")
            conn.execute("""INSERT INTO workspace_role_permissions(workspace_id,role,permission_key,allowed,updated_by,updated_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(workspace_id,role,permission_key) DO UPDATE SET allowed=excluded.allowed,updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
                (user["workspace_id"], item.role, item.permission, 1 if item.allowed else 0, user["user_id"], stamp))
        log_activity(conn, user["workspace_id"], user["user_id"], "permissions", user["workspace_id"], "updated", "مجوزهای نقش‌های فضای کاری تغییر کرد.")
    return {"ok": True}


SERVER_ROLE_PERMISSIONS = {
    "owner": {"overview", "users.view", "workspaces.view", "logs.view", "backups.view", "backups.create", "backups.download", "exports", "imports", "settings.manage", "admins.manage", "restore"},
    "operator": {"overview", "users.view", "workspaces.view", "logs.view", "backups.view", "backups.create", "exports", "imports"},
    "auditor": {"overview", "users.view", "workspaces.view", "logs.view", "backups.view", "exports"},
}


def server_admin_record(user_id: str) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute("SELECT user_id,role,enabled,created_at FROM server_admins WHERE user_id=? AND enabled=1", (user_id,)).fetchone()
    return dict(row) if row else None


def is_instance_admin(user_id: str) -> bool:
    return server_admin_record(user_id) is not None


def require_server_permission(permission: str):
    def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        admin = server_admin_record(user["user_id"])
        if not admin or permission not in SERVER_ROLE_PERMISSIONS.get(admin["role"], set()):
            raise HTTPException(status_code=403, detail="این عملیات به دسترسی مدیریت سرور نیاز دارد.")
        user["server_admin_role"] = admin["role"]
        return user
    return dependency


def require_instance_admin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return require_server_permission("backups.view")(user)


def server_audit(conn: sqlite3.Connection, actor_id: str | None, action: str, target: str = "", details: dict[str, Any] | None = None) -> None:
    conn.execute("INSERT INTO server_audit_logs(actor_user_id,action,target,details_json,created_at) VALUES(?,?,?,?,?)",
                 (actor_id, action, target[:240], json.dumps(details or {}, ensure_ascii=False), now_iso()))
    _server_logger.info("actor=%s action=%s target=%s details=%s", actor_id or "cli", action, target, json.dumps(details or {}, ensure_ascii=False))


@app.get("/api/security")
def get_security_status(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT totp_enabled FROM user_security WHERE user_id=?", (user["user_id"],)).fetchone()
        prefs = conn.execute("SELECT * FROM notification_preferences WHERE user_id=?", (user["user_id"],)).fetchone()
        recovery_remaining = conn.execute("SELECT COUNT(*) FROM totp_recovery_codes WHERE user_id=? AND used_at IS NULL", (user["user_id"],)).fetchone()[0]
    return {"twoFactorEnabled": bool(row["totp_enabled"]) if row else False,
            "recoveryCodesRemaining": recovery_remaining,
            "emailConfigured": bool(os.getenv("BOTTLENECK_SMTP_HOST") and os.getenv("BOTTLENECK_SMTP_FROM")),
            "instanceAdmin": is_instance_admin(user["user_id"]),
            "notificationPreferences": dict(prefs) if prefs else {"email_enabled": 0, "assigned_enabled": 1, "mentions_enabled": 1, "deadlines_enabled": 1}}


@app.post("/api/security/totp/setup")
def totp_setup(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")
    recovery_codes = [secrets.token_hex(4).upper() for _ in range(10)]
    with db() as conn:
        existing = conn.execute("SELECT totp_enabled FROM user_security WHERE user_id=?", (user["user_id"],)).fetchone()
        if existing and existing["totp_enabled"]:
            raise HTTPException(status_code=409, detail="تأیید دومرحله‌ای قبلاً فعال است.")
        conn.execute("""INSERT INTO user_security(user_id,totp_secret,totp_enabled,updated_at) VALUES(?,?,0,?)
            ON CONFLICT(user_id) DO UPDATE SET totp_secret=excluded.totp_secret,totp_enabled=0,updated_at=excluded.updated_at""", (user["user_id"], secret, now_iso()))
        conn.execute("DELETE FROM totp_recovery_codes WHERE user_id=?", (user["user_id"],))
        for code in recovery_codes:
            conn.execute("INSERT INTO totp_recovery_codes(id,user_id,code_hash,created_at) VALUES(?,?,?,?)",
                         (new_id(), user["user_id"], hash_token(code), now_iso()))
    label = f"BottleNeck:{user['email']}"
    uri = f"otpauth://totp/{label}?secret={secret}&issuer=BottleNeck&algorithm=SHA1&digits=6&period=30"
    return {"secret": secret, "otpauthUri": uri, "recoveryCodes": recovery_codes,
            "message": "کلید را در برنامه احراز هویت وارد کنید و کدهای بازیابی را در جای امن نگه دارید."}


@app.post("/api/security/totp/enable")
def totp_enable(payload: TotpVerifyInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        row = conn.execute("SELECT totp_secret,totp_enabled FROM user_security WHERE user_id=?", (user["user_id"],)).fetchone()
        if not row or not verify_totp(row["totp_secret"], payload.code):
            raise HTTPException(status_code=400, detail="کد برنامه احراز هویت صحیح نیست.")
        conn.execute("UPDATE user_security SET totp_enabled=1,updated_at=? WHERE user_id=?", (now_iso(), user["user_id"]))
        log_activity(conn, user["workspace_id"], user["user_id"], "security", user["user_id"], "totp.enabled", "تأیید دومرحله‌ای حساب فعال شد.")
    return {"ok": True}


@app.post("/api/security/totp/disable")
def totp_disable(payload: TotpDisableInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id=?", (user["user_id"],)).fetchone()
        security = conn.execute("SELECT totp_secret,totp_enabled FROM user_security WHERE user_id=?", (user["user_id"],)).fetchone()
        if not row or not verify_password(payload.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="گذرواژه حساب درست نیست.")
        if not security or not security["totp_enabled"] or not verify_totp(security["totp_secret"], payload.code):
            raise HTTPException(status_code=400, detail="کد احراز هویت درست نیست.")
        conn.execute("UPDATE user_security SET totp_enabled=0,totp_secret=NULL,updated_at=? WHERE user_id=?", (now_iso(), user["user_id"]))
        conn.execute("DELETE FROM totp_recovery_codes WHERE user_id=?", (user["user_id"],))
    return {"ok": True}


@app.post("/api/auth/password-reset/request")
def request_password_reset(payload: PasswordResetRequestInput, request: Request) -> dict[str, str]:
    email = valid_email(payload.email)
    enforce_rate_limit(request, "password-reset-ip", "all", 8, 3600)
    enforce_rate_limit(request, "password-reset-account", email, 4, 3600)
    with db() as conn:
        user_row = conn.execute("SELECT id,email FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        if user_row:
            token = _new_password_reset(conn, user_row["id"])
            base_url = str(request.base_url).rstrip("/")
            reset_url = f"{base_url}/?reset={token}"
            try:
                sent = _send_email(email, "بازیابی گذرواژه BottleNeck", f"برای تنظیم گذرواژه تازه این پیوند را ظرف ۳۰ دقیقه باز کنید:\n{reset_url}\n\nاگر این درخواست از طرف شما نبوده، این پیام را نادیده بگیرید.")
            except Exception as exc:
                print(f"[BottleNeck mail] reset mail failed: {exc}")
                sent = False
            # Deliberately do not disclose account existence or the token in this public response.
            if not sent:
                conn.execute("DELETE FROM password_reset_tokens WHERE token_hash=?", (hash_token(token),))
    return {"message": "اگر حسابی با این ایمیل وجود داشته باشد و ایمیل سرور تنظیم شده باشد، پیوند بازیابی ارسال می‌شود."}


@app.post("/api/auth/password-reset/complete")
def complete_password_reset(payload: PasswordResetCompleteInput, response: Response, request: Request) -> dict[str, bool]:
    enforce_rate_limit(request, "password-reset-complete-ip", "all", 12, 600)
    with db() as conn:
        row = conn.execute("SELECT * FROM password_reset_tokens WHERE token_hash=? AND used_at IS NULL AND expires_at>?", (hash_token(payload.token), now_iso())).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="پیوند بازیابی نامعتبر یا منقضی شده است.")
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash(payload.password), row["user_id"]))
        conn.execute("UPDATE password_reset_tokens SET used_at=? WHERE id=?", (now_iso(), row["id"]))
        conn.execute("DELETE FROM sessions WHERE user_id=?", (row["user_id"],))
        conn.execute("DELETE FROM login_challenges WHERE user_id=?", (row["user_id"],))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@app.post("/api/workspaces/members/{member_id}/password-reset")
def admin_password_reset(member_id: str, request: Request, user: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT u.id,u.email FROM users u JOIN memberships m ON m.user_id=u.id WHERE u.id=? AND m.workspace_id=?", (member_id, user["workspace_id"])).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="عضو پیدا نشد.")
        token = _new_password_reset(conn, member_id)
        log_activity(conn, user["workspace_id"], user["user_id"], "security", member_id, "password.reset.issued", f"پیوند بازیابی برای {row['email']} ساخته شد.")
    return {"email": row["email"], "resetUrl": f"{str(request.base_url).rstrip('/')}/?reset={token}", "expiresInMinutes": 30}


@app.get("/api/notifications/preferences")
def get_notification_preferences(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        row = conn.execute("SELECT * FROM notification_preferences WHERE user_id=?", (user["user_id"],)).fetchone()
        if not row:
            conn.execute("INSERT OR IGNORE INTO notification_preferences(user_id,updated_at) VALUES(?,?)", (user["user_id"], now_iso()))
            row = conn.execute("SELECT * FROM notification_preferences WHERE user_id=?", (user["user_id"],)).fetchone()
    return dict(row)


@app.put("/api/notifications/preferences")
def update_notification_preferences(payload: NotificationPreferencesInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    with db() as conn:
        conn.execute("""INSERT INTO notification_preferences(user_id,email_enabled,assigned_enabled,mentions_enabled,deadlines_enabled,updated_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET email_enabled=excluded.email_enabled,assigned_enabled=excluded.assigned_enabled,
            mentions_enabled=excluded.mentions_enabled,deadlines_enabled=excluded.deadlines_enabled,updated_at=excluded.updated_at""",
            (user["user_id"], int(payload.email_enabled), int(payload.assigned_enabled), int(payload.mentions_enabled), int(payload.deadlines_enabled), now_iso()))
    return {"ok": True}


@app.get("/api/backups")
def list_backups(user: dict[str, Any] = Depends(require_instance_admin)) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM backup_catalog ORDER BY created_at DESC LIMIT 50").fetchall()
    return {"items": [dict(r) for r in rows], "retention": BACKUP_RETENTION, "intervalHours": BACKUP_INTERVAL_HOURS}


@app.post("/api/backups")
def create_manual_backup(user: dict[str, Any] = Depends(require_server_permission("backups.create"))) -> dict[str, Any]:
    try:
        backup = _build_backup(user["user_id"], False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ساخت پشتیبان ناموفق بود: {exc}")
    log_msg = f"نسخه پشتیبان {backup['filename']} ساخته شد."
    with db() as conn:
        log_activity(conn, user["workspace_id"], user["user_id"], "backup", backup["id"], "created", log_msg)
    return backup


@app.get("/api/backups/{backup_id}/download")
def download_backup(backup_id: str, user: dict[str, Any] = Depends(require_server_permission("backups.download"))) -> FileResponse:
    with db() as conn:
        row = conn.execute("SELECT * FROM backup_catalog WHERE id=?", (backup_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="نسخه پشتیبان پیدا نشد.")
    path = BACKUP_DIR / row["filename"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="فایل پشتیبان روی دیسک موجود نیست.")
    return FileResponse(path, media_type="application/zip", filename=row["filename"])


@app.put("/api/drive/nodes/{node_id}/role-permissions")
def set_shared_node_acl(node_id: str, payload: NodeAclInput, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    if user["role"] != "owner":
        raise HTTPException(status_code=403, detail="فقط مالک می‌تواند دسترسی نقش‌ها به پوشه یا فایل را تنظیم کند.")
    with db() as conn:
        node = conn.execute("SELECT * FROM shared_nodes WHERE id=? AND workspace_id=?", (node_id, user["workspace_id"])).fetchone()
        if not node:
            raise HTTPException(status_code=404, detail="مورد پیدا نشد.")
        conn.execute("DELETE FROM shared_node_role_acl WHERE node_id=?", (node_id,))
        for item in payload.items:
            if item.role not in {"owner", "admin", "member"}:
                raise HTTPException(status_code=422, detail="نقش انتخاب‌شده معتبر نیست.")
            conn.execute("INSERT INTO shared_node_role_acl(node_id,role,can_read,can_write,updated_by,updated_at) VALUES(?,?,?,?,?,?)",
                         (node_id, item.role, int(item.can_read), int(item.can_write), user["user_id"], now_iso()))
        log_activity(conn, user["workspace_id"], user["user_id"], "shared_node", node_id, "acl.updated", f"مجوز دسترسی «{node['title']}» تغییر کرد.")
    return {"ok": True}


@app.get("/api/drive/nodes/{node_id}/role-permissions")
def get_shared_node_acl(node_id: str, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with db() as conn:
        node = conn.execute("SELECT * FROM shared_nodes WHERE id=? AND workspace_id=?", (node_id, user["workspace_id"])).fetchone()
        if not node:
            raise HTTPException(status_code=404, detail="مورد پیدا نشد.")
        check_node_access(conn, node, user, allow_locked=True)
        rows = conn.execute("SELECT role,can_read,can_write FROM shared_node_role_acl WHERE node_id=? ORDER BY role", (node_id,)).fetchall()
    return {"items": [dict(r) for r in rows]}


# Enforce per-role ACLs in addition to workspace/team/password gates for shared drive nodes.
_original_check_node_access = check_node_access

def check_node_access(conn: sqlite3.Connection, node: sqlite3.Row, user: dict[str, Any],
                      password: str | None = None, *, allow_locked: bool = False) -> bool:
    locked = _original_check_node_access(conn, node, user, password, allow_locked=allow_locked)
    if user.get("role") != "owner":
        current = node
        visited = set()
        while current:
            if current["id"] in visited:
                break
            visited.add(current["id"])
            acl = conn.execute("SELECT can_read FROM shared_node_role_acl WHERE node_id=? AND role=?",
                               (current["id"], user["role"])).fetchone()
            any_acl = conn.execute("SELECT 1 FROM shared_node_role_acl WHERE node_id=? LIMIT 1", (current["id"],)).fetchone()
            if any_acl and (not acl or not acl["can_read"]):
                raise HTTPException(status_code=403, detail="نقش شما اجازه مشاهده این مورد یا پوشه والد آن را ندارد.")
            parent_id = current["parent_id"] if "parent_id" in current.keys() else None
            current = conn.execute("SELECT * FROM shared_nodes WHERE id=? AND workspace_id=?", (parent_id,user["workspace_id"])).fetchone() if parent_id else None
    return locked


def require_shared_node_write(conn: sqlite3.Connection, node: sqlite3.Row, user: dict[str, Any]) -> None:
    if user.get("role") == "owner":
        return
    current = node
    visited = set()
    while current:
        if current["id"] in visited: break
        visited.add(current["id"])
        any_acl = conn.execute("SELECT 1 FROM shared_node_role_acl WHERE node_id=? LIMIT 1", (current["id"],)).fetchone()
        if any_acl:
            acl = conn.execute("SELECT can_write FROM shared_node_role_acl WHERE node_id=? AND role=?", (current["id"],user["role"])).fetchone()
            if not acl or not acl["can_write"]:
                raise HTTPException(status_code=403, detail="نقش شما اجازه تغییر این مورد را ندارد.")
        parent_id = current["parent_id"] if "parent_id" in current.keys() else None
        current = conn.execute("SELECT * FROM shared_nodes WHERE id=? AND workspace_id=?", (parent_id,user["workspace_id"])).fetchone() if parent_id else None


@app.websocket("/ws")
async def websocket_events(websocket: WebSocket) -> None:
    token = websocket.cookies.get(COOKIE_NAME)
    if not token:
        await websocket.close(code=4401)
        return
    with db() as conn:
        session = conn.execute("""SELECT s.id AS session_id,s.user_id,s.workspace_id,s.expires_at,m.role
            FROM sessions s JOIN memberships m ON m.user_id=s.user_id AND m.workspace_id=s.workspace_id
            WHERE s.token_hash=?""", (hash_token(token),)).fetchone()
    if not session or datetime.fromisoformat(session["expires_at"]) < datetime.now(timezone.utc):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        cursor = max(0, int(websocket.query_params.get("after_id", "0")))
    except ValueError:
        cursor = 0
    try:
        while True:
            with db() as conn:
                still_valid = conn.execute("SELECT 1 FROM sessions WHERE id=? AND expires_at>?", (session["session_id"], now_iso())).fetchone()
                if still_valid:
                    rows = conn.execute("SELECT id,user_id,kind,message,created_at FROM workspace_events WHERE workspace_id=? AND id>? ORDER BY id LIMIT 100",
                                        (session["workspace_id"], cursor)).fetchall()
                    current = conn.execute("SELECT COALESCE(MAX(id),0) FROM workspace_events WHERE workspace_id=?", (session["workspace_id"],)).fetchone()[0]
                    unread = conn.execute("SELECT COUNT(*) FROM notifications WHERE workspace_id=? AND user_id=? AND is_read=0",
                                          (session["workspace_id"], session["user_id"])).fetchone()[0]
            if not still_valid:
                await websocket.close(code=4401)
                return
            if rows:
                await websocket.send_json({"events": [dict(r) for r in rows], "cursor": current, "unread": unread})
                cursor = max(cursor, int(current))
            await asyncio.sleep(0.8)
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


# Uvicorn HTTPS is configured by the launch scripts using BOTTLENECK_SSL_CERTFILE/KEYFILE.

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def _server_setting(key: str, default: str) -> str:
    try:
        with db() as conn:
            row = conn.execute("SELECT setting_value FROM server_settings WHERE setting_key=?", (key,)).fetchone()
        return row["setting_value"] if row else default
    except sqlite3.Error:
        return default


def _server_setting_int(key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(_server_setting(key, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


# ---------------------------------------------------------------------------
# v1.1.0 — dedicated server administration, diagnostics and data portability.
# Server administration is intentionally separate from workspace settings.
# ---------------------------------------------------------------------------

SERVER_EXPORT_TABLES = [
    "teams", "projects", "workspace_settings", "workspace_status_labels",
    "workspace_role_permissions", "workspace_custom_roles", "workspace_custom_role_permissions",
    "tasks", "task_assignees", "task_comments", "task_checklists", "task_attachments",
    "time_entries", "task_dependencies", "recurring_rules", "task_templates", "task_approvals",
    "team_members", "shared_boards", "shared_board_items", "shared_nodes", "shared_node_role_acl",
    "chat_messages", "chat_attachments", "chat_message_mentions", "notifications", "activity_logs",
    "workspace_events", "workspace_presence", "notification_preferences"
]


def _folder_bytes(path: Path) -> int:
    total = 0
    if path.exists():
        for item in path.rglob("*"):
            try:
                if item.is_file(): total += item.stat().st_size
            except OSError:
                continue
    return total


def _server_overview() -> dict[str, Any]:
    with db() as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        workspaces = conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
        sessions = conn.execute("SELECT COUNT(*) FROM sessions WHERE expires_at>?", (now_iso(),)).fetchone()[0]
        backups = conn.execute("SELECT COUNT(*) FROM backup_catalog").fetchone()[0]
        admin_count = conn.execute("SELECT COUNT(*) FROM server_admins WHERE enabled=1").fetchone()[0]
        recent = conn.execute("SELECT action,target,created_at FROM server_audit_logs ORDER BY id DESC LIMIT 5").fetchall()
    db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    data_size = _folder_bytes(DB_PATH.parent)
    free = shutil.disk_usage(DB_PATH.parent).free if DB_PATH.parent.exists() else 0
    return {
        "version": APP_VERSION, "status": "healthy" if integrity == "ok" else "warning",
        "databaseIntegrity": integrity, "databasePath": str(DB_PATH.relative_to(BASE_DIR)) if DB_PATH.is_relative_to(BASE_DIR) else str(DB_PATH),
        "databaseBytes": db_size, "dataBytes": data_size, "freeBytes": free,
        "users": users, "workspaces": workspaces, "activeSessions": sessions,
        "backups": backups, "serverAdmins": admin_count,
        "uptimeSeconds": max(0, int((datetime.now(timezone.utc)-PROCESS_STARTED_AT).total_seconds())),
        "host": _server_setting("bind_host", os.getenv("BOTTLENECK_HOST") or "0.0.0.0"),
        "port": int(_server_setting("bind_port", os.getenv("BOTTLENECK_PORT") or "1939")),
        "serverLogBytes": SERVER_LOG_PATH.stat().st_size if SERVER_LOG_PATH.exists() else 0,
        "backupIntervalHours": _server_setting_int("backup_interval_hours", BACKUP_INTERVAL_HOURS, 1, 720),
        "backupRetention": _server_setting_int("backup_retention", BACKUP_RETENTION, 2, 100),
        "diskTotalBytes": shutil.disk_usage(DB_PATH.parent).total if DB_PATH.parent.exists() else 0,
        "diskUsedBytes": shutil.disk_usage(DB_PATH.parent).used if DB_PATH.parent.exists() else 0,
        "recent": [dict(x) for x in recent],
    }


def _workspace_export_rows(conn: sqlite3.Connection, workspace_id: str) -> dict[str, list[dict[str, Any]]]:
    export: dict[str, list[dict[str, Any]]] = {}
    workspace = conn.execute("SELECT * FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
    if not workspace:
        raise HTTPException(status_code=404, detail="فضای کاری پیدا نشد.")
    export["workspaces"] = [dict(workspace)]
    export["memberships"] = [dict(r) for r in conn.execute("SELECT * FROM memberships WHERE workspace_id=?", (workspace_id,)).fetchall()]
    for table in SERVER_EXPORT_TABLES:
        columns = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "workspace_id" in columns:
            if table == "shared_nodes":
                rows = conn.execute(f"SELECT * FROM {table} WHERE workspace_id=? ORDER BY created_at ASC", (workspace_id,)).fetchall()
            else:
                rows = conn.execute(f"SELECT * FROM {table} WHERE workspace_id=?", (workspace_id,)).fetchall()
        elif table == "team_members":
            rows = conn.execute("SELECT tm.* FROM team_members tm JOIN teams t ON t.id=tm.team_id WHERE t.workspace_id=?", (workspace_id,)).fetchall()
        elif table == "task_assignees":
            rows = conn.execute("SELECT ta.* FROM task_assignees ta JOIN tasks t ON t.id=ta.task_id WHERE t.workspace_id=?", (workspace_id,)).fetchall()
        elif table in {"task_comments", "task_checklists"}:
            rows = conn.execute(f"SELECT x.* FROM {table} x JOIN tasks t ON t.id=x.task_id WHERE t.workspace_id=?", (workspace_id,)).fetchall()
        elif table == "task_dependencies":
            rows = conn.execute("SELECT d.* FROM task_dependencies d JOIN tasks t ON t.id=d.task_id WHERE t.workspace_id=?", (workspace_id,)).fetchall()
        elif table == "shared_board_items":
            rows = conn.execute("SELECT i.* FROM shared_board_items i JOIN shared_boards b ON b.id=i.board_id WHERE b.workspace_id=?", (workspace_id,)).fetchall()
        elif table == "chat_message_mentions":
            rows = conn.execute("SELECT mm.* FROM chat_message_mentions mm JOIN chat_messages m ON m.id=mm.message_id WHERE m.workspace_id=?", (workspace_id,)).fetchall()
        elif table == "notification_preferences":
            rows = conn.execute("SELECT np.* FROM notification_preferences np JOIN memberships m ON m.user_id=np.user_id WHERE m.workspace_id=?", (workspace_id,)).fetchall()
        else:
            rows = []
        export[table] = [dict(r) for r in rows]
    member_rows = conn.execute("SELECT u.id,u.name,u.email,u.avatar_key,u.avatar_updated_at FROM users u JOIN memberships m ON m.user_id=u.id WHERE m.workspace_id=?", (workspace_id,)).fetchall()
    export["users"] = [dict(r) for r in member_rows]
    return export


def build_workspace_export(workspace_id: str, output_path: Path) -> dict[str, Any]:
    with db() as conn:
        rows = _workspace_export_rows(conn, workspace_id)
    stamp = now_iso()
    manifest = {"application": "BottleNeck", "format": "workspace-package", "formatVersion": 1,
                "applicationVersion": APP_VERSION, "createdAt": stamp, "workspaceId": workspace_id,
                "tables": sorted(rows.keys()), "filesIncluded": True,
                "note": "User credentials and global server settings are deliberately excluded."}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("workspace.json", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
        for table, folder, root in (("task_attachments", UPLOAD_DIR, "files/task_attachments"),
                                    ("shared_nodes", SHARED_DIR, "files/shared_nodes"),
                                    ("chat_attachments", CHAT_DIR, "files/chat_attachments")):
            for row in rows.get(table, []):
                stored = row.get("stored_name")
                if not stored: continue
                source = folder / workspace_id / Path(stored).name
                if source.is_file(): zf.write(source, f"{root}/{Path(stored).name}")
    return manifest


def import_workspace_package(package_bytes: bytes, importing_user: dict[str, Any]) -> dict[str, Any]:
    if len(package_bytes) > 512 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="بسته فضای کاری حداکثر ۵۱۲ مگابایت است.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(package_bytes))
        infos = archive.infolist()
        if len(infos) > 20000 or sum(x.file_size for x in infos) > 1024 * 1024 * 1024:
            raise ValueError("archive too large")
        for info in infos:
            path = Path(info.filename)
            if path.is_absolute() or ".." in path.parts or info.is_dir():
                if info.is_dir(): continue
                raise ValueError("unsafe archive path")
        manifest = json.loads(archive.read("manifest.json"))
        rows = json.loads(archive.read("workspace.json"))
        if manifest.get("application") != "BottleNeck" or manifest.get("format") != "workspace-package" or manifest.get("formatVersion") != 1:
            raise ValueError("unsupported package")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="بسته خروجی معتبر یا قابل پشتیبانی نیست.") from exc
    old_workspace = (rows.get("workspaces") or [{}])[0]
    if not old_workspace.get("id"):
        raise HTTPException(status_code=400, detail="شناسه فضای کاری در بسته پیدا نشد.")
    owner_id = importing_user["user_id"]
    new_workspace_id = new_id()
    id_map: dict[str, str] = {old_workspace["id"]: new_workspace_id}
    # Map member identities by email. Unknown people are attributed to the importer;
    # credentials are never imported as part of a workspace package.
    user_map: dict[str, str] = {}
    with db() as conn:
        for person in rows.get("users", []):
            if person.get("id") == owner_id:
                user_map[person["id"]] = owner_id
                continue
            matched = conn.execute("SELECT id FROM users WHERE email=? COLLATE NOCASE", (person.get("email", ""),)).fetchone()
            user_map[person["id"]] = matched["id"] if matched else owner_id
        for table_rows in rows.values():
            if not isinstance(table_rows, list): continue
            for row in table_rows:
                old_id = row.get("id") if isinstance(row, dict) else None
                if old_id and old_id not in user_map and old_id != old_workspace.get("id"):
                    id_map.setdefault(old_id, new_id())
        ordered_tables = ["teams", "projects", "workspace_custom_roles", "memberships", "workspace_settings", "workspace_status_labels",
                          "workspace_role_permissions", "workspace_custom_role_permissions", "tasks", "team_members",
                          "task_assignees", "task_comments", "task_checklists", "task_attachments", "time_entries",
                          "task_dependencies", "recurring_rules", "task_templates", "task_approvals", "shared_boards",
                          "shared_nodes", "shared_node_role_acl", "shared_board_items", "chat_messages", "chat_attachments",
                          "chat_message_mentions", "notifications", "activity_logs", "workspace_events", "workspace_presence",
                          "notification_preferences"]
        stamp = now_iso()
        base_name = str(old_workspace.get("name") or "فضای کاری واردشده")[:100]
        conn.execute("INSERT INTO workspaces(id,name,created_by,created_at) VALUES(?,?,?,?)",
                     (new_workspace_id, f"{base_name} (واردشده)", owner_id, stamp))
        conn.execute("INSERT INTO memberships(id,workspace_id,user_id,role,joined_at) VALUES(?,?,?,?,?)",
                     (new_id(), new_workspace_id, owner_id, "owner", stamp))
        for table in ordered_tables:
            table_rows = rows.get(table, [])
            if not table_rows: continue
            valid_cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for original in table_rows:
                row = {k: v for k, v in original.items() if k in valid_cols}
                for key, value in list(row.items()):
                    if key == "id" and value in id_map: row[key] = id_map[value]
                    elif key == "workspace_id": row[key] = new_workspace_id
                    elif key in {"user_id", "created_by", "updated_by", "uploaded_by", "assigned_by", "requested_by", "approved_by", "reviewed_by", "actor_id", "invited_by"} and value:
                        row[key] = user_map.get(value, owner_id)
                    elif key.endswith("_id") and value:
                        row[key] = id_map.get(value, user_map.get(value, value))
                if table == "memberships":
                    row["id"] = new_id()
                    row["workspace_id"] = new_workspace_id
                    row["user_id"] = user_map.get(original.get("user_id"), owner_id)
                    if row["user_id"] == owner_id:
                        row["role"] = "owner"
                        row["custom_role_id"] = None
                    elif row.get("role") == "owner":
                        row["role"] = "admin"
                    cols = list(row.keys())
                    placeholders = ",".join("?" for _ in cols)
                    conn.execute(f"INSERT OR IGNORE INTO memberships ({','.join(cols)}) VALUES ({placeholders})", [row[c] for c in cols])
                    continue
                if table == "workspace_custom_role_permissions":
                    row["workspace_id"] = new_workspace_id
                if table == "team_members":
                    row["user_id"] = user_map.get(original.get("user_id"), owner_id)
                if table == "notification_preferences":
                    row["user_id"] = user_map.get(original.get("user_id"), owner_id)
                if table == "workspace_presence":
                    row["user_id"] = user_map.get(original.get("user_id"), owner_id)
                if table == "workspace_role_permissions": row["workspace_id"] = new_workspace_id
                if not row: continue
                cols = list(row.keys())
                placeholders = ",".join("?" for _ in cols)
                try:
                    conn.execute(f"INSERT OR IGNORE INTO {table} ({','.join(cols)}) VALUES ({placeholders})", [row[c] for c in cols])
                except sqlite3.IntegrityError:
                    continue
        # Guarantee a valid owner and workspace setup even when the source owner was not a package member.
        conn.execute("INSERT OR IGNORE INTO memberships(id,workspace_id,user_id,role,joined_at) VALUES(?,?,?,?,?)",
                     (new_id(), new_workspace_id, owner_id, "owner", stamp))
        conn.execute("INSERT OR IGNORE INTO workspace_settings(workspace_id,created_at) VALUES(?,?)", (new_workspace_id, stamp))
        for key, label, color, position in [("todo","در صف","neutral",0),("in-progress","در حال انجام","blue",1),("review","در بررسی","gold",2),("blocked","متوقف‌شده","red",3),("done","تکمیل‌شده","green",4)]:
            conn.execute("INSERT OR IGNORE INTO workspace_status_labels(workspace_id,status_key,label,color,position,updated_at) VALUES(?,?,?,?,?,?)",
                         (new_workspace_id,key,label,color,position,stamp))
        # Copy bundled file payloads into the new workspace folders.
        file_roots = {"task_attachments": UPLOAD_DIR / new_workspace_id, "shared_nodes": SHARED_DIR / new_workspace_id, "chat_attachments": CHAT_DIR / new_workspace_id}
        for table, folder in file_roots.items():
            folder.mkdir(parents=True, exist_ok=True)
            prefix = f"files/{table}/"
            for info in infos:
                if info.filename.startswith(prefix):
                    name = Path(info.filename).name
                    if name and name not in {".", ".."}:
                        (folder / name).write_bytes(archive.read(info))
        server_audit(conn, owner_id, "workspace.import", new_workspace_id, {"sourceWorkspace": old_workspace.get("name"), "tables": len(ordered_tables)})
        log_activity(conn, new_workspace_id, owner_id, "workspace", new_workspace_id, "imported", "فضای کاری از بسته BottleNeck وارد شد.")
    return {"workspaceId": new_workspace_id, "workspaceName": f"{base_name} (واردشده)"}


@app.get("/api/me")
def me_server_admin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    # Re-register the enriched endpoint after the original for compatibility with older callers.
    return {"id": user["user_id"], "name": user["name"], "email": user["email"], "role": user["role"],
            "roleName": user.get("custom_role_name") or {"owner":"مالک","admin":"مدیر","member":"عضو"}.get(user["role"],"عضو"),
            "customRoleId": user.get("custom_role_id"), "roleColor": user.get("custom_role_color"),
            "avatarUrl": f"/api/users/{user['user_id']}/avatar?v={user.get('avatar_updated_at') or ''}" if user.get("avatar_key") else None,
            "workspaceId": user["workspace_id"], "workspaceName": user["workspace_name"],
            "onboardingCompleted": bool(user["onboarding_completed"]), "canManage": has_permission(user, "workspace.manage"),
            "permissions": permissions_for_user(user), "instanceAdmin": is_instance_admin(user["user_id"]),
            "serverAdminRole": (server_admin_record(user["user_id"]) or {}).get("role")}


@app.get("/api/server-admin/settings")
def server_admin_get_settings(user: dict[str, Any] = Depends(require_server_permission("overview"))) -> dict[str, Any]:
    return {"host": _server_setting("bind_host", os.getenv("BOTTLENECK_HOST") or "0.0.0.0"),
            "port": int(_server_setting("bind_port", os.getenv("BOTTLENECK_PORT") or "1939")),
            "backupIntervalHours": _server_setting_int("backup_interval_hours", BACKUP_INTERVAL_HOURS, 1, 720),
            "backupRetention": _server_setting_int("backup_retention", BACKUP_RETENTION, 2, 100),
            "httpsEnabled": COOKIE_SECURE, "restartRequired": True}


@app.put("/api/server-admin/settings")
def server_admin_update_settings(payload: dict[str, Any], user: dict[str, Any] = Depends(require_server_permission("settings.manage"))) -> dict[str, Any]:
    try:
        interval = int(payload.get("backupIntervalHours", BACKUP_INTERVAL_HOURS))
        retention = int(payload.get("backupRetention", BACKUP_RETENTION))
        port = int(payload.get("port", _server_setting("bind_port", "1939")))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="مقادیر زمان‌بندی و پورت باید عدد صحیح باشند.")
    host = str(payload.get("host", _server_setting("bind_host", "0.0.0.0"))).strip()
    if not 1 <= interval <= 720 or not 2 <= retention <= 100:
        raise HTTPException(status_code=422, detail="فاصله پشتیبان باید ۱ تا ۷۲۰ ساعت و تعداد نگهداری ۲ تا ۱۰۰ باشد.")
    if not 1024 <= port <= 65535:
        raise HTTPException(status_code=422, detail="پورت باید بین ۱۰۲۴ تا ۶۵۵۳۵ باشد.")
    try:
        ipaddress.ip_address(host)
    except ValueError as exc:
        if host not in {"localhost"}:
            raise HTTPException(status_code=422, detail="نشانی میزبان باید IP معتبر یا localhost باشد.") from exc
    stamp = now_iso()
    with db() as conn:
        for key, value in (("backup_interval_hours", interval), ("backup_retention", retention),
                           ("bind_host", host), ("bind_port", port)):
            conn.execute("INSERT INTO server_settings(setting_key,setting_value,updated_by,updated_at) VALUES(?,?,?,?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,updated_by=excluded.updated_by,updated_at=excluded.updated_at",
                         (key, str(value), user["user_id"], stamp))
        server_audit(conn, user["user_id"], "server.settings.update", "server", {"intervalHours": interval, "retention": retention, "host": host, "port": port})
    result = server_admin_get_settings(user)
    result["restartRequired"] = True
    return result


@app.get("/api/server-admin/overview")
def server_admin_overview(user: dict[str, Any] = Depends(require_server_permission("overview"))) -> dict[str, Any]:
    data = _server_overview()
    data["serverRole"] = user.get("server_admin_role", "auditor")
    return data


@app.get("/api/server-admin/workspaces")
def server_admin_workspaces(user: dict[str, Any] = Depends(require_server_permission("workspaces.view"))) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute("""SELECT w.id,w.name,w.created_at,u.name AS owner_name,u.email AS owner_email,
            (SELECT COUNT(*) FROM memberships m WHERE m.workspace_id=w.id) AS member_count,
            (SELECT COUNT(*) FROM tasks t WHERE t.workspace_id=w.id) AS task_count,
            (SELECT COUNT(*) FROM shared_nodes n WHERE n.workspace_id=w.id) AS shared_item_count
            FROM workspaces w JOIN users u ON u.id=w.created_by ORDER BY w.created_at DESC""").fetchall()
    return {"items": [dict(r) for r in rows]}


@app.get("/api/server-admin/users")
def server_admin_users(user: dict[str, Any] = Depends(require_server_permission("users.view"))) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute("""SELECT u.id,u.name,u.email,u.created_at,
            (SELECT COUNT(*) FROM memberships m WHERE m.user_id=u.id) AS workspace_count,
            (SELECT COUNT(*) FROM sessions s WHERE s.user_id=u.id AND s.expires_at>?) AS active_sessions,
            sa.role AS server_role,sa.enabled AS server_admin_enabled
            FROM users u LEFT JOIN server_admins sa ON sa.user_id=u.id ORDER BY u.created_at DESC LIMIT 500""", (now_iso(),)).fetchall()
    return {"items": [dict(r) for r in rows]}


@app.get("/api/server-admin/logs")
def server_admin_logs(limit: int = 100, user: dict[str, Any] = Depends(require_server_permission("logs.view"))) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    with db() as conn:
        rows = conn.execute("""SELECT l.*,u.name AS actor_name,u.email AS actor_email FROM server_audit_logs l
            LEFT JOIN users u ON u.id=l.actor_user_id ORDER BY l.id DESC LIMIT ?""", (limit,)).fetchall()
    try:
        lines = SERVER_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except OSError:
        lines = []
    return {"items": [dict(r) for r in rows], "serverLines": lines}


@app.get("/api/server-admin/backups")
def server_admin_backups(user: dict[str, Any] = Depends(require_server_permission("backups.view"))) -> dict[str, Any]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM backup_catalog ORDER BY created_at DESC LIMIT 100").fetchall()
    return {"items": [dict(r) for r in rows], "intervalHours": BACKUP_INTERVAL_HOURS, "retention": BACKUP_RETENTION}


@app.post("/api/server-admin/backups")
def server_admin_create_backup(user: dict[str, Any] = Depends(require_server_permission("backups.create"))) -> dict[str, Any]:
    result = _build_backup(user["user_id"], False)
    with db() as conn: server_audit(conn, user["user_id"], "backup.create", result["filename"], {"bytes": result["sizeBytes"]})
    return result


@app.get("/api/server-admin/export/workspaces/{workspace_id}")
def server_admin_export_workspace(workspace_id: str, user: dict[str, Any] = Depends(require_server_permission("exports"))) -> FileResponse:
    with db() as conn:
        exists = conn.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
        if not exists: raise HTTPException(status_code=404, detail="فضای کاری پیدا نشد.")
        row = conn.execute("SELECT name FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
        server_audit(conn, user["user_id"], "workspace.export", workspace_id, {"name": row["name"]})
    temp_dir = Path(tempfile.mkdtemp(prefix="bottleneck-export-"))
    target = temp_dir / f"workspace-{workspace_id}.zip"
    try: build_workspace_export(workspace_id, target)
    except Exception: shutil.rmtree(temp_dir, ignore_errors=True); raise
    from starlette.background import BackgroundTask
    return FileResponse(target, filename=target.name, media_type="application/zip", background=BackgroundTask(lambda: shutil.rmtree(temp_dir, ignore_errors=True)))


def _csv_response(rows: list[dict[str, Any]], fieldnames: list[str], filename: str) -> Response:
    buff = io.StringIO(newline="")
    writer = csv.DictWriter(buff, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    payload = "\ufeff" + buff.getvalue()
    return Response(payload, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/server-admin/export/tasks.csv")
def server_admin_export_tasks(workspace_id: str, user: dict[str, Any] = Depends(require_server_permission("exports"))) -> Response:
    with db() as conn:
        rows = conn.execute("""SELECT t.id,t.title,t.description,t.status,t.priority,t.due_date,t.estimate,
            COALESCE(p.name,'') AS project,COALESCE(tm.name,'') AS team,
            COALESCE((SELECT GROUP_CONCAT(u.email,';') FROM task_assignees ta JOIN users u ON u.id=ta.user_id WHERE ta.task_id=t.id),'') AS assignee_emails
            FROM tasks t LEFT JOIN projects p ON p.id=t.project_id LEFT JOIN teams tm ON tm.id=t.team_id
            WHERE t.workspace_id=? ORDER BY t.created_at DESC""", (workspace_id,)).fetchall()
        if not conn.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone(): raise HTTPException(status_code=404, detail="فضای کاری پیدا نشد.")
        server_audit(conn, user["user_id"], "tasks.export.csv", workspace_id, {"count": len(rows)})
    fields = ["id","title","description","status","priority","due_date","estimate","project","team","assignee_emails"]
    return _csv_response([dict(r) for r in rows], fields, f"bottleneck-tasks-{workspace_id[:8]}.csv")


@app.get("/api/server-admin/export/projects.csv")
def server_admin_export_projects(workspace_id: str, user: dict[str, Any] = Depends(require_server_permission("exports"))) -> Response:
    with db() as conn:
        rows = conn.execute("SELECT name,description,color,status FROM projects WHERE workspace_id=? ORDER BY name", (workspace_id,)).fetchall()
        if not conn.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone(): raise HTTPException(status_code=404, detail="فضای کاری پیدا نشد.")
        server_audit(conn, user["user_id"], "projects.export.csv", workspace_id, {"count": len(rows)})
    return _csv_response([dict(r) for r in rows], ["name","description","color","status"], f"bottleneck-projects-{workspace_id[:8]}.csv")


@app.post("/api/server-admin/import/tasks.csv")
async def server_admin_import_tasks(workspace_id: str, request: Request, user: dict[str, Any] = Depends(require_server_permission("imports"))) -> dict[str, Any]:
    raw = await request.body()
    if len(raw) > 20 * 1024 * 1024: raise HTTPException(status_code=413, detail="فایل CSV حداکثر ۲۰ مگابایت است.")
    try: text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc: raise HTTPException(status_code=400, detail="فایل باید UTF-8 باشد.") from exc
    reader = csv.DictReader(io.StringIO(text))
    required = {"title"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)): raise HTTPException(status_code=422, detail="ستون title در فایل CSV الزامی است.")
    created = 0; skipped = 0; stamp = now_iso()
    with db() as conn:
        if not conn.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone(): raise HTTPException(status_code=404, detail="فضای کاری پیدا نشد.")
        for item in reader:
            title = (item.get("title") or "").strip()
            if len(title) < 2: skipped += 1; continue
            status = item.get("status") or "todo"; priority = item.get("priority") or "medium"
            if status not in STATUSES: status = "todo"
            if priority not in PRIORITIES: priority = "medium"
            team_id = None; project_id = None
            if (item.get("team") or "").strip():
                team = conn.execute("SELECT id FROM teams WHERE workspace_id=? AND name=? COLLATE NOCASE", (workspace_id,item["team"].strip())).fetchone(); team_id = team["id"] if team else None
            if (item.get("project") or "").strip():
                project = conn.execute("SELECT id FROM projects WHERE workspace_id=? AND name=? COLLATE NOCASE", (workspace_id,item["project"].strip())).fetchone(); project_id = project["id"] if project else None
            task_id = new_id()
            due = (item.get("due_date") or "").strip() or None
            if due and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due): due = None
            try: estimate = float(item.get("estimate")) if item.get("estimate") else None
            except ValueError: estimate = None
            conn.execute("INSERT INTO tasks(id,workspace_id,title,description,status,priority,team_id,project_id,due_date,estimate,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (task_id,workspace_id,title,(item.get("description") or "")[:12000],status,priority,team_id,project_id,due,estimate,user["user_id"],stamp,stamp))
            for email in (item.get("assignee_emails") or "").split(";"):
                if email.strip():
                    member = conn.execute("SELECT u.id FROM users u JOIN memberships m ON m.user_id=u.id WHERE m.workspace_id=? AND u.email=? COLLATE NOCASE", (workspace_id,email.strip())).fetchone()
                    if member: conn.execute("INSERT OR IGNORE INTO task_assignees(task_id,user_id,assigned_by,created_at) VALUES(?,?,?,?)", (task_id,member["id"],user["user_id"],stamp))
            created += 1
        server_audit(conn,user["user_id"],"tasks.import.csv",workspace_id,{"created":created,"skipped":skipped})
    return {"created":created,"skipped":skipped}


@app.post("/api/server-admin/import/projects.csv")
async def server_admin_import_projects(workspace_id: str, request: Request, user: dict[str, Any] = Depends(require_server_permission("imports"))) -> dict[str, Any]:
    raw = await request.body()
    if len(raw) > 10 * 1024 * 1024: raise HTTPException(status_code=413, detail="فایل CSV حداکثر ۱۰ مگابایت است.")
    try: text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc: raise HTTPException(status_code=400, detail="فایل باید UTF-8 باشد.") from exc
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "name" not in reader.fieldnames: raise HTTPException(status_code=422, detail="ستون name در فایل CSV الزامی است.")
    created = updated = skipped = 0; stamp = now_iso()
    with db() as conn:
        if not conn.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone(): raise HTTPException(status_code=404, detail="فضای کاری پیدا نشد.")
        for item in reader:
            name = (item.get("name") or "").strip()
            if len(name) < 2: skipped += 1; continue
            status = item.get("status") or "active"
            if status not in {"active","completed","archived"}: status = "active"
            old = conn.execute("SELECT id FROM projects WHERE workspace_id=? AND name=? COLLATE NOCASE", (workspace_id,name)).fetchone()
            if old:
                conn.execute("UPDATE projects SET description=?,color=?,status=?,updated_at=? WHERE id=?", ((item.get("description") or "")[:4000],(item.get("color") or "rust")[:32],status,stamp,old["id"])); updated += 1
            else:
                conn.execute("INSERT INTO projects(id,workspace_id,name,description,color,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                             (new_id(),workspace_id,name,(item.get("description") or "")[:4000],(item.get("color") or "rust")[:32],status,user["user_id"],stamp,stamp)); created += 1
        server_audit(conn,user["user_id"],"projects.import.csv",workspace_id,{"created":created,"updated":updated,"skipped":skipped})
    return {"created":created,"updated":updated,"skipped":skipped}


@app.post("/api/server-admin/import/workspace")
async def server_admin_import_workspace(request: Request, user: dict[str, Any] = Depends(require_server_permission("imports"))) -> dict[str, Any]:
    raw = await request.body()
    result = import_workspace_package(raw, user)
    return result


@app.post("/api/server-admin/admins")
def server_admin_add_operator(payload: dict[str, str], user: dict[str, Any] = Depends(require_server_permission("admins.manage"))) -> dict[str, Any]:
    email = valid_email(payload.get("email", "")); role = payload.get("role", "operator")
    if role not in {"operator", "auditor"}: raise HTTPException(status_code=422, detail="نقش مدیر سرور باید operator یا auditor باشد.")
    with db() as conn:
        target = conn.execute("SELECT id,name,email FROM users WHERE email=? COLLATE NOCASE", (email,)).fetchone()
        if not target: raise HTTPException(status_code=404, detail="ابتدا کاربر باید یک‌بار در BottleNeck حساب بسازد.")
        existing = conn.execute("SELECT role FROM server_admins WHERE user_id=? AND enabled=1", (target["id"],)).fetchone()
        if existing and existing["role"] == "owner":
            raise HTTPException(status_code=409, detail="نقش مالک اصلی نصب قابل تبدیل به اپراتور یا ناظر نیست.")
        conn.execute("INSERT INTO server_admins(user_id,role,enabled,created_by,created_at) VALUES(?,?,1,?,?) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,enabled=1,created_by=excluded.created_by",
                     (target["id"],role,user["user_id"],now_iso()))
        server_audit(conn,user["user_id"],"server.admin.grant",email,{"role":role})
    return {"ok":True,"email":email,"role":role}


@app.delete("/api/server-admin/admins/{target_user_id}")
def server_admin_revoke_operator(target_user_id: str, user: dict[str, Any] = Depends(require_server_permission("admins.manage"))) -> dict[str, bool]:
    if target_user_id == user["user_id"]: raise HTTPException(status_code=400, detail="نمی‌توانید دسترسی مدیر اصلی خودتان را لغو کنید.")
    with db() as conn:
        row = conn.execute("SELECT role FROM server_admins WHERE user_id=?", (target_user_id,)).fetchone()
        if not row: raise HTTPException(status_code=404, detail="مدیر سرور پیدا نشد.")
        if row["role"] == "owner": raise HTTPException(status_code=403, detail="مالک اصلی فقط از CLI محلی قابل تغییر است.")
        conn.execute("DELETE FROM server_admins WHERE user_id=?", (target_user_id,))
        server_audit(conn,user["user_id"],"server.admin.revoke",target_user_id,{})
    return {"ok":True}
