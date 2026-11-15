-- BottleNeck v0.9.0 SQLite schema
-- Existing MVP databases are upgraded automatically when the application starts.
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  onboarding_completed INTEGER NOT NULL DEFAULT 0,
  avatar_key TEXT,
  avatar_updated_at TEXT,
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
  custom_role_id TEXT,
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
CREATE TABLE IF NOT EXISTS workspace_join_links (
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
);
CREATE INDEX IF NOT EXISTS idx_workspace_join_links_active ON workspace_join_links(workspace_id, revoked_at, expires_at);
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
CREATE TABLE IF NOT EXISTS task_assignees (
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  assigned_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(task_id, user_id)
);
CREATE TABLE IF NOT EXISTS task_comments (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_checklists (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  is_done INTEGER NOT NULL DEFAULT 0,
  position INTEGER NOT NULL DEFAULT 0,
  created_by TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS task_attachments (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  uploaded_by TEXT NOT NULL REFERENCES users(id),
  original_name TEXT NOT NULL,
  stored_name TEXT NOT NULL,
  content_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  actor_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  entity_type TEXT,
  entity_id TEXT,
  is_read INTEGER NOT NULL DEFAULT 0,
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
CREATE TABLE IF NOT EXISTS workspace_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  kind TEXT NOT NULL,
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
CREATE INDEX IF NOT EXISTS idx_task_assignees_user ON task_assignees(user_id, task_id);
CREATE INDEX IF NOT EXISTS idx_checklists_task ON task_checklists(task_id, position);
CREATE INDEX IF NOT EXISTS idx_attachments_task ON task_attachments(task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_workspace_time ON activity_logs(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_workspace_id ON workspace_events(workspace_id, id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_invites_token ON invitations(token_hash);


-- BottleNeck v0.4.0 productivity modules.
CREATE TABLE IF NOT EXISTS time_entries (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  duration_seconds INTEGER,
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_dependencies (
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  depends_on_task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(task_id, depends_on_task_id),
  CHECK(task_id <> depends_on_task_id)
);
CREATE TABLE IF NOT EXISTS recurring_rules (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high','urgent')),
  assignee_ids TEXT NOT NULL DEFAULT '[]',
  team_id TEXT REFERENCES teams(id) ON DELETE SET NULL,
  project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
  cadence TEXT NOT NULL CHECK(cadence IN ('daily','weekly','monthly')),
  interval_count INTEGER NOT NULL DEFAULT 1 CHECK(interval_count BETWEEN 1 AND 90),
  next_run_on TEXT NOT NULL,
  due_offset_days INTEGER NOT NULL DEFAULT 0 CHECK(due_offset_days BETWEEN 0 AND 365),
  is_active INTEGER NOT NULL DEFAULT 1,
  created_by TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_templates (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  priority TEXT NOT NULL DEFAULT 'medium',
  estimate REAL,
  checklist_json TEXT NOT NULL DEFAULT '[]',
  assignee_ids TEXT NOT NULL DEFAULT '[]',
  team_id TEXT REFERENCES teams(id) ON DELETE SET NULL,
  project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
  created_by TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_approvals (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  requested_by TEXT NOT NULL REFERENCES users(id),
  reviewer_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
  comment TEXT NOT NULL DEFAULT '',
  requested_at TEXT NOT NULL,
  reviewed_at TEXT
);
CREATE TABLE IF NOT EXISTS workspace_status_labels (
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  status_key TEXT NOT NULL CHECK(status_key IN ('todo','in-progress','review','blocked','done')),
  label TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT 'neutral',
  position INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(workspace_id, status_key)
);
CREATE INDEX IF NOT EXISTS idx_time_workspace_started ON time_entries(workspace_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_time_user_active ON time_entries(user_id, ended_at);
CREATE INDEX IF NOT EXISTS idx_dependencies_task ON task_dependencies(task_id, depends_on_task_id);
CREATE INDEX IF NOT EXISTS idx_recurring_due ON recurring_rules(workspace_id, is_active, next_run_on);
CREATE INDEX IF NOT EXISTS idx_templates_workspace ON task_templates(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_approvals_workspace_status ON task_approvals(workspace_id, status, requested_at DESC);

-- BottleNeck v0.5.0 shared knowledge and collaboration modules.
CREATE TABLE IF NOT EXISTS shared_boards (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  access_mode TEXT NOT NULL DEFAULT 'workspace' CHECK(access_mode IN ('workspace','team','password')),
  team_id TEXT REFERENCES teams(id) ON DELETE SET NULL,
  password_hash TEXT,
  created_by TEXT NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shared_board_items (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  board_id TEXT NOT NULL REFERENCES shared_boards(id) ON DELETE CASCADE,
  item_type TEXT NOT NULL CHECK(item_type IN ('note','text','link','task')),
  title TEXT NOT NULL DEFAULT '',
  content TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '',
  task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
  x REAL NOT NULL DEFAULT 24,
  y REAL NOT NULL DEFAULT 24,
  width REAL NOT NULL DEFAULT 260,
  color TEXT NOT NULL DEFAULT 'butter',
  created_by TEXT NOT NULL REFERENCES users(id),
  updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shared_nodes (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  parent_id TEXT REFERENCES shared_nodes(id) ON DELETE CASCADE,
  node_type TEXT NOT NULL CHECK(node_type IN ('folder','file','text')),
  title TEXT NOT NULL,
  content TEXT NOT NULL DEFAULT '',
  stored_name TEXT,
  original_name TEXT,
  content_type TEXT,
  size_bytes INTEGER NOT NULL DEFAULT 0,
  access_mode TEXT NOT NULL DEFAULT 'workspace' CHECK(access_mode IN ('workspace','team','password')),
  team_id TEXT REFERENCES teams(id) ON DELETE SET NULL,
  password_hash TEXT,
  created_by TEXT NOT NULL REFERENCES users(id),
  updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_messages (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  channel_type TEXT NOT NULL DEFAULT 'workspace' CHECK(channel_type IN ('workspace','team')),
  team_id TEXT REFERENCES teams(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  reply_to_id TEXT REFERENCES chat_messages(id) ON DELETE SET NULL,
  edited_at TEXT,
  deleted_at TEXT,
  resource_type TEXT,
  resource_id TEXT
);
CREATE TABLE IF NOT EXISTS workspace_presence (
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  page TEXT NOT NULL DEFAULT 'overview',
  last_seen TEXT NOT NULL,
  active_team_id TEXT,
  cursor_x_pct REAL,
  cursor_y_pct REAL,
  cursor_page TEXT,
  cursor_color TEXT,
  PRIMARY KEY(workspace_id,user_id)
);
CREATE INDEX IF NOT EXISTS idx_boards_workspace ON shared_boards(workspace_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_board_items_board ON shared_board_items(board_id,y,x);
CREATE INDEX IF NOT EXISTS idx_shared_nodes_parent ON shared_nodes(workspace_id,parent_id,node_type,updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_channel ON chat_messages(workspace_id,channel_type,team_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_presence_last_seen ON workspace_presence(workspace_id,last_seen DESC);

-- BottleNeck v0.7.0: identity, team presence, join codes and granular workspace permissions.
CREATE TABLE IF NOT EXISTS login_challenges (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  remember_me INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_security (
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  totp_secret TEXT,
  totp_enabled INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS totp_recovery_codes (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  code_hash TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(user_id,code_hash)
);
CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workspace_role_permissions (
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('owner','admin','member')),
  permission_key TEXT NOT NULL,
  allowed INTEGER NOT NULL DEFAULT 0,
  updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(workspace_id,role,permission_key)
);
CREATE TABLE IF NOT EXISTS shared_node_role_acl (
  node_id TEXT NOT NULL REFERENCES shared_nodes(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('owner','admin','member')),
  can_read INTEGER NOT NULL DEFAULT 1,
  can_write INTEGER NOT NULL DEFAULT 0,
  updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(node_id,role)
);
CREATE TABLE IF NOT EXISTS backup_catalog (
  id TEXT PRIMARY KEY,
  filename TEXT NOT NULL UNIQUE,
  size_bytes INTEGER NOT NULL,
  created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  is_automatic INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS notification_preferences (
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  email_enabled INTEGER NOT NULL DEFAULT 0,
  assigned_enabled INTEGER NOT NULL DEFAULT 1,
  mentions_enabled INTEGER NOT NULL DEFAULT 1,
  deadlines_enabled INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notification_email_jobs (
  id TEXT PRIMARY KEY,
  notification_id TEXT NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sent','failed','skipped')),
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  sent_at TEXT,
  UNIQUE(notification_id)
);
CREATE INDEX IF NOT EXISTS idx_login_challenges_expiry ON login_challenges(expires_at);
CREATE INDEX IF NOT EXISTS idx_totp_recovery_user ON totp_recovery_codes(user_id,used_at);
CREATE INDEX IF NOT EXISTS idx_password_reset_expiry ON password_reset_tokens(expires_at,used_at);
CREATE INDEX IF NOT EXISTS idx_backup_catalog_created ON backup_catalog(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_jobs_status ON notification_email_jobs(status,created_at);


-- BottleNeck v0.7.0: persistent sessions, custom roles, 15-minute join codes and presence cursors.
CREATE TABLE IF NOT EXISTS workspace_custom_roles (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#8b6bb1', base_role TEXT NOT NULL DEFAULT 'member' CHECK(base_role IN ('admin','member')),
  created_by TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, UNIQUE(workspace_id,name)
);
CREATE TABLE IF NOT EXISTS workspace_custom_role_permissions (
  workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE, role_id TEXT NOT NULL REFERENCES workspace_custom_roles(id) ON DELETE CASCADE,
  permission_key TEXT NOT NULL, allowed INTEGER NOT NULL DEFAULT 0, updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  updated_at TEXT NOT NULL, PRIMARY KEY(role_id,permission_key)
);
CREATE TABLE IF NOT EXISTS workspace_join_codes (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('admin','member')), token_hash TEXT NOT NULL UNIQUE,
  created_by TEXT NOT NULL REFERENCES users(id), expires_at TEXT NOT NULL, max_uses INTEGER NOT NULL DEFAULT 1,
  use_count INTEGER NOT NULL DEFAULT 0, revoked_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS join_code_attempts (
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, window_started TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0
);


-- BottleNeck v0.8.0: threaded chat, mentions, media and resource references.
CREATE TABLE IF NOT EXISTS chat_attachments (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  uploaded_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  channel_type TEXT NOT NULL CHECK(channel_type IN ('workspace','team')),
  team_id TEXT REFERENCES teams(id) ON DELETE CASCADE,
  message_id TEXT REFERENCES chat_messages(id) ON DELETE CASCADE,
  original_name TEXT NOT NULL, stored_name TEXT NOT NULL, content_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_message_mentions (
  message_id TEXT NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  PRIMARY KEY(message_id,user_id)
);
CREATE INDEX IF NOT EXISTS idx_chat_attachments_message ON chat_attachments(message_id);
CREATE INDEX IF NOT EXISTS idx_chat_attachments_staging ON chat_attachments(uploaded_by,message_id,created_at);
CREATE INDEX IF NOT EXISTS idx_chat_mentions_user ON chat_message_mentions(user_id,message_id);

-- BottleNeck v0.9.0 instance-level administration. This is distinct from workspace roles.
CREATE TABLE IF NOT EXISTS server_instance (
  id INTEGER PRIMARY KEY CHECK(id=1),
  install_id TEXT NOT NULL,
  owner_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  initialized_at TEXT NOT NULL,
  version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS server_admins (
  user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('owner','operator','auditor')),
  enabled INTEGER NOT NULL DEFAULT 1,
  created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS server_settings (
  setting_key TEXT PRIMARY KEY,
  setting_value TEXT NOT NULL,
  updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS server_audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  target TEXT NOT NULL DEFAULT '',
  details_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_server_audit_created ON server_audit_logs(created_at DESC);
