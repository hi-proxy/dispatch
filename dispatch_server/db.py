from __future__ import annotations

import json
import hashlib
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS principals (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('human', 'agent')),
    display_name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    archived_at TEXT
);

CREATE TABLE IF NOT EXISTS pm_profiles (
    principal_id TEXT PRIMARY KEY REFERENCES principals(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL DEFAULT 'PM',
    avatar BLOB,
    avatar_media_type TEXT,
    avatar_updated_at TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS client_nodes (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    last_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS agent_bindings (
    agent_id TEXT PRIMARY KEY REFERENCES principals(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES client_nodes(id) ON DELETE CASCADE,
    agent_provider TEXT NOT NULL,
    agent_session_id TEXT NOT NULL,
    terminal_provider TEXT NOT NULL,
    terminal_session_id TEXT NOT NULL,
    lifecycle TEXT NOT NULL CHECK (
        lifecycle IN ('running', 'idle', 'needs_input', 'unknown')
    ),
    attached INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(node_id, terminal_provider, terminal_session_id)
);

CREATE TABLE IF NOT EXISTS messages (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    workspace_id TEXT NOT NULL,
    sender_id TEXT NOT NULL REFERENCES principals(id),
    body TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'message' CHECK (kind IN ('message', 'pm_request')),
    reply_level TEXT NOT NULL DEFAULT 'r1' CHECK (reply_level IN ('r1', 'r2', 'r3')),
    in_reply_to INTEGER REFERENCES messages(seq),
    track TEXT,
    project_seq INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS inbox (
    recipient_id TEXT NOT NULL REFERENCES principals(id),
    message_seq INTEGER NOT NULL REFERENCES messages(seq) ON DELETE CASCADE,
    received_at TEXT,
    processed_at TEXT,
    PRIMARY KEY (recipient_id, message_seq)
);

CREATE TABLE IF NOT EXISTS message_references (
    principal_id TEXT NOT NULL REFERENCES principals(id),
    message_seq INTEGER NOT NULL REFERENCES messages(seq) ON DELETE CASCADE,
    PRIMARY KEY (principal_id, message_seq)
);

CREATE TABLE IF NOT EXISTS permission_requests (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    agent_id TEXT REFERENCES principals(id),
    tool_name TEXT NOT NULL,
    tool_input TEXT NOT NULL,
    suggestions TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'allowed', 'denied', 'expired')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    resolved_at TEXT,
    resolved_by TEXT REFERENCES principals(id)
);

CREATE TABLE IF NOT EXISTS message_tags (
    message_seq INTEGER NOT NULL REFERENCES messages(seq) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (message_seq, tag)
);

CREATE INDEX IF NOT EXISTS message_tags_tag_seq
ON message_tags(tag, message_seq);

CREATE TABLE IF NOT EXISTS message_bookmarks (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    message_seq INTEGER NOT NULL REFERENCES messages(seq) ON DELETE CASCADE,
    label TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES principals(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(workspace_id, message_seq, label)
);

CREATE INDEX IF NOT EXISTS message_bookmarks_workspace_seq
ON message_bookmarks(workspace_id, message_seq);

CREATE TABLE IF NOT EXISTS timeline_pins (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    after_message_seq INTEGER NOT NULL REFERENCES messages(seq) ON DELETE CASCADE,
    label TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES principals(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(workspace_id, after_message_seq)
);

CREATE INDEX IF NOT EXISTS timeline_pins_workspace_seq
ON timeline_pins(workspace_id, after_message_seq);

CREATE TABLE IF NOT EXISTS workspace_roles (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    onboarding_prompt TEXT NOT NULL DEFAULT '',
    avatar BLOB,
    avatar_media_type TEXT,
    avatar_updated_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    deleted_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS unique_active_role_name
ON workspace_roles(workspace_id, name) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS role_assignments (
    id TEXT PRIMARY KEY,
    role_id TEXT NOT NULL REFERENCES workspace_roles(id),
    workspace_id TEXT NOT NULL,
    agent_id TEXT NOT NULL REFERENCES principals(id),
    assigned_by TEXT NOT NULL REFERENCES principals(id),
    assigned_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ended_at TEXT,
    onboarding_sent INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_assignment_per_role
ON role_assignments(role_id) WHERE ended_at IS NULL;

CREATE TABLE IF NOT EXISTS message_role_recipients (
    role_id TEXT NOT NULL REFERENCES workspace_roles(id),
    message_seq INTEGER NOT NULL REFERENCES messages(seq) ON DELETE CASCADE,
    delivered_agent_id TEXT REFERENCES principals(id),
    delivered_at TEXT,
    PRIMARY KEY (role_id, message_seq)
);

CREATE INDEX IF NOT EXISTS inbox_recipient_seq
ON inbox(recipient_id, message_seq);

CREATE TABLE IF NOT EXISTS delivery_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    recipient_id TEXT NOT NULL REFERENCES principals(id),
    kind TEXT NOT NULL,
    through_message_seq INTEGER NOT NULL REFERENCES messages(seq),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS delivery_recipient_seq
ON delivery_events(recipient_id, seq);

CREATE TABLE IF NOT EXISTS shared_values (
    workspace_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated_by TEXT NOT NULL REFERENCES principals(id),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (workspace_id, key)
);

CREATE TABLE IF NOT EXISTS work_items (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    agent_id TEXT NOT NULL REFERENCES principals(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'done')),
    last_report TEXT,
    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ended_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_work_per_agent
ON work_items(agent_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS work_reports (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id TEXT NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('report', 'done')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""


class DispatchDB:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.path, check_same_thread=False, isolation_level=None
        )
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.executescript(SCHEMA)
            self._migrate()

    def _migrate(self) -> None:
        columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(messages)")
        }
        if "kind" not in columns:
            self._connection.execute(
                "ALTER TABLE messages ADD COLUMN kind TEXT NOT NULL DEFAULT 'message'"
            )
        if "reply_level" not in columns:
            self._connection.execute(
                "ALTER TABLE messages ADD COLUMN reply_level TEXT NOT NULL DEFAULT 'r1'"
            )
        if "in_reply_to" not in columns:
            self._connection.execute(
                "ALTER TABLE messages ADD COLUMN in_reply_to INTEGER"
            )
        if "track" not in columns:
            self._connection.execute("ALTER TABLE messages ADD COLUMN track TEXT")
        if "project_seq" not in columns:
            # seq는 전역 단조 번호라 한 방만 보면 띄엄띄엄해진다. 에이전트가
            # 그걸 누락으로 읽고 확인 작업을 하므로 방마다 1부터 세는 표시
            # 번호를 따로 둔다. 저장된 참조(핀·북마크·in_reply_to)는 전역
            # seq를 그대로 쓴다.
            self._connection.execute(
                "ALTER TABLE messages ADD COLUMN project_seq INTEGER"
            )
            self._connection.execute(
                """UPDATE messages SET project_seq = (
                       SELECT COUNT(*) FROM messages older
                       WHERE older.workspace_id = messages.workspace_id
                         AND older.seq <= messages.seq
                   ) WHERE project_seq IS NULL"""
            )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_project_seq"
            " ON messages(workspace_id, project_seq)"
        )
        role_columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(workspace_roles)")
        }
        if "avatar" not in role_columns:
            self._connection.execute("ALTER TABLE workspace_roles ADD COLUMN avatar BLOB")
        if "avatar_media_type" not in role_columns:
            self._connection.execute(
                "ALTER TABLE workspace_roles ADD COLUMN avatar_media_type TEXT"
            )
        if "avatar_updated_at" not in role_columns:
            self._connection.execute(
                "ALTER TABLE workspace_roles ADD COLUMN avatar_updated_at TEXT"
            )
        assignment_columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(role_assignments)")
        }
        if "workspace_id" not in assignment_columns:
            self._connection.execute(
                "ALTER TABLE role_assignments ADD COLUMN workspace_id TEXT"
            )
            self._connection.execute(
                """UPDATE role_assignments SET workspace_id = (
                       SELECT workspace_id FROM workspace_roles
                       WHERE workspace_roles.id = role_assignments.role_id
                   ) WHERE workspace_id IS NULL"""
            )
        self._connection.execute("DROP INDEX IF EXISTS one_active_role_per_agent")
        self._connection.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS one_active_role_per_agent_per_project
               ON role_assignments(workspace_id, agent_id) WHERE ended_at IS NULL"""
        )
        self._connection.execute(
            "INSERT OR IGNORE INTO projects(id, name) VALUES ('local', 'Local')"
        )
        for table in ("workspace_roles", "messages", "shared_values", "work_items"):
            rows = self._connection.execute(
                f"SELECT DISTINCT workspace_id FROM {table} WHERE workspace_id IS NOT NULL"
            ).fetchall()
            for row in rows:
                workspace_id = str(row["workspace_id"])
                self._connection.execute(
                    "INSERT OR IGNORE INTO projects(id, name) VALUES (?, ?)",
                    (workspace_id, workspace_id if workspace_id != "local" else "Local"),
                )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                yield self._connection
            except Exception:
                self._connection.execute("ROLLBACK")
                raise
            else:
                self._connection.execute("COMMIT")

    def create_principal(
        self, *, kind: str, display_name: str, principal_id: str | None = None
    ) -> dict[str, Any]:
        principal_id = principal_id or str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO principals(id, kind, display_name) VALUES (?, ?, ?)",
                (principal_id, kind, display_name),
            )
            row = conn.execute(
                "SELECT * FROM principals WHERE id = ?", (principal_id,)
            ).fetchone()
        return dict(row)

    def upsert_principal(
        self, *, principal_id: str, kind: str, display_name: str
    ) -> dict[str, Any]:
        with self.transaction() as conn:
            if kind == "human":
                profile = conn.execute(
                    "SELECT display_name FROM pm_profiles WHERE principal_id = ?",
                    (principal_id,),
                ).fetchone()
                if profile is not None:
                    display_name = str(profile["display_name"])
            conn.execute(
                """
                INSERT INTO principals(id, kind, display_name) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  kind = excluded.kind,
                  display_name = excluded.display_name
                """,
                (principal_id, kind, display_name),
            )
            row = conn.execute(
                "SELECT * FROM principals WHERE id = ?", (principal_id,)
            ).fetchone()
        return dict(row)

    def create_permission_request(
        self, *, workspace_id: str, session_id: str, agent_id: str | None,
        tool_name: str, tool_input: str, suggestions: str | None,
    ) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO permission_requests(
                       id, workspace_id, session_id, agent_id,
                       tool_name, tool_input, suggestions
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    request_id, workspace_id, session_id, agent_id,
                    tool_name, tool_input, suggestions,
                ),
            )
            row = conn.execute(
                "SELECT * FROM permission_requests WHERE id = ?", (request_id,)
            ).fetchone()
        return dict(row)

    def permission_request(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                """SELECT r.*, p.display_name AS agent_name
                   FROM permission_requests r
                   LEFT JOIN principals p ON p.id = r.agent_id
                   WHERE r.id = ?""",
                (request_id,),
            ).fetchone()
        return dict(row) if row else None

    def pending_permission_requests(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT r.*, p.display_name AS agent_name
                   FROM permission_requests r
                   LEFT JOIN principals p ON p.id = r.agent_id
                   WHERE r.workspace_id = ? AND r.status = 'pending'
                   ORDER BY r.created_at ASC""",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def resolve_permission_request(
        self, *, request_id: str, status: str, resolved_by: str | None,
    ) -> dict[str, Any] | None:
        if status not in ("allowed", "denied", "expired"):
            raise ValueError(f"unknown status: {status}")
        with self.transaction() as conn:
            # 이미 답이 나온 요청은 덮어쓰지 않는다. 사람이 누른 답과 시간
            # 초과가 겹쳤을 때 먼저 온 쪽을 지킨다.
            conn.execute(
                """UPDATE permission_requests
                   SET status = ?,
                       resolved_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                       resolved_by = ?
                   WHERE id = ? AND status = 'pending'""",
                (status, resolved_by, request_id),
            )
            row = conn.execute(
                "SELECT * FROM permission_requests WHERE id = ?", (request_id,)
            ).fetchone()
        return dict(row) if row else None

    def global_seq(self, *, workspace_id: str, project_seq: int) -> int | None:
        """방별 표시 번호를 전역 seq로 되돌린다. 경계에서만 쓴다."""
        with self._lock:
            row = self._connection.execute(
                "SELECT seq FROM messages WHERE workspace_id = ? AND project_seq = ?",
                (workspace_id, project_seq),
            ).fetchone()
        return int(row["seq"]) if row else None

    def projects(self) -> list[dict[str, Any]]:
        # last_message_seq는 방마다 어디까지 왔는지 알리는 파생값이다. 읽음
        # 여부는 클라이언트가 자기 커서와 대조해 판단한다.
        with self._lock:
            rows = self._connection.execute(
                """SELECT p.*,
                          (SELECT MAX(seq) FROM messages m WHERE m.workspace_id = p.id)
                              AS last_message_seq
                   FROM projects p
                   WHERE p.archived_at IS NULL
                   ORDER BY p.created_at, p.name"""
            ).fetchall()
        return [dict(row) for row in rows]

    def create_project(self, *, name: str, project_id: str | None = None) -> dict[str, Any]:
        project_id = project_id or str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO projects(id, name) VALUES (?, ?)",
                (project_id, name.strip()),
            )
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row)

    def update_project(self, *, project_id: str, name: str) -> dict[str, Any]:
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE projects SET name = ? WHERE id = ? AND archived_at IS NULL",
                (name.strip(), project_id),
            )
            if cursor.rowcount != 1:
                raise LookupError("project not found")
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row)

    def ensure_project(self, project_id: str) -> None:
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM projects WHERE id = ? AND archived_at IS NULL", (project_id,)
            ).fetchone()
        if row is None:
            raise LookupError("project not found")

    def pm_profile(self, principal_id: str) -> dict[str, Any]:
        with self.transaction() as conn:
            principal = conn.execute(
                "SELECT display_name FROM principals WHERE id = ? AND kind = 'human'",
                (principal_id,),
            ).fetchone()
            if principal is None:
                raise LookupError("PM principal not found")
            conn.execute(
                "INSERT OR IGNORE INTO pm_profiles(principal_id, display_name) VALUES (?, ?)",
                (principal_id, principal["display_name"]),
            )
            row = conn.execute(
                """SELECT principal_id, display_name,
                          CASE WHEN avatar IS NULL THEN 0 ELSE 1 END AS has_avatar,
                          avatar_updated_at, updated_at
                   FROM pm_profiles WHERE principal_id = ?""",
                (principal_id,),
            ).fetchone()
        value = dict(row)
        value["has_avatar"] = bool(value["has_avatar"])
        return value

    def update_pm_profile(self, *, principal_id: str, display_name: str) -> dict[str, Any]:
        self.pm_profile(principal_id)
        with self.transaction() as conn:
            conn.execute(
                """UPDATE pm_profiles SET display_name = ?,
                   updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE principal_id = ?""",
                (display_name.strip(), principal_id),
            )
            conn.execute(
                "UPDATE principals SET display_name = ? WHERE id = ?",
                (display_name.strip(), principal_id),
            )
        return self.pm_profile(principal_id)

    def set_pm_avatar(
        self, *, principal_id: str, data: bytes | None, media_type: str | None
    ) -> dict[str, Any]:
        self.pm_profile(principal_id)
        with self.transaction() as conn:
            conn.execute(
                """UPDATE pm_profiles SET avatar = ?, avatar_media_type = ?,
                   avatar_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
                   updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE principal_id = ?""",
                (data, media_type, principal_id),
            )
        return self.pm_profile(principal_id)

    def pm_avatar(self, principal_id: str) -> tuple[bytes, str] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT avatar, avatar_media_type FROM pm_profiles WHERE principal_id = ?",
                (principal_id,),
            ).fetchone()
        if row is None or row["avatar"] is None:
            return None
        return bytes(row["avatar"]), str(row["avatar_media_type"])

    def upsert_node(self, *, node_id: str, display_name: str) -> dict[str, Any]:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO client_nodes(id, display_name) VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  display_name = excluded.display_name,
                  last_seen_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                (node_id, display_name),
            )
            row = conn.execute(
                "SELECT * FROM client_nodes WHERE id = ?", (node_id,)
            ).fetchone()
        return dict(row)

    def upsert_binding(self, binding: dict[str, Any]) -> dict[str, Any]:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO agent_bindings(
                  agent_id, node_id, agent_provider, agent_session_id,
                  terminal_provider, terminal_session_id, lifecycle, attached
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(agent_id) DO UPDATE SET
                  node_id = excluded.node_id,
                  agent_provider = excluded.agent_provider,
                  agent_session_id = excluded.agent_session_id,
                  terminal_provider = excluded.terminal_provider,
                  terminal_session_id = excluded.terminal_session_id,
                  lifecycle = excluded.lifecycle,
                  attached = 1,
                  updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                (
                    binding["agent_id"],
                    binding["node_id"],
                    binding["agent_provider"],
                    binding["agent_session_id"],
                    binding["terminal_provider"],
                    binding["terminal_session_id"],
                    binding["lifecycle"],
                ),
            )
            row = conn.execute(
                "SELECT * FROM agent_bindings WHERE agent_id = ?",
                (binding["agent_id"],),
            ).fetchone()
        result = dict(row)
        result["attached"] = bool(result["attached"])
        return result

    def detach_binding(self, agent_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE agent_bindings
                SET attached = 0,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE agent_id = ? AND attached = 1
                """,
                (agent_id,),
            )
        return cursor.rowcount == 1

    def roles(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT r.id, r.workspace_id, r.name, r.onboarding_prompt,
                       r.created_at, r.deleted_at,
                       CASE WHEN r.avatar IS NULL THEN 0 ELSE 1 END AS has_avatar,
                       r.avatar_updated_at,
                       a.id AS assignment_id, a.agent_id, a.assigned_at,
                       a.onboarding_sent, p.display_name AS agent_name
                FROM workspace_roles r
                LEFT JOIN role_assignments a ON a.role_id = r.id AND a.ended_at IS NULL
                LEFT JOIN principals p ON p.id = a.agent_id
                WHERE r.workspace_id = ? AND r.deleted_at IS NULL
                ORDER BY r.name
                """,
                (workspace_id,),
            ).fetchall()
        return [self._role_dict(row) for row in rows]

    def role(self, role_id: str) -> dict[str, Any]:
        with self._lock:
            return self._role_by_id(self._connection, role_id)

    def create_role(
        self, *, workspace_id: str, name: str, onboarding_prompt: str = ""
    ) -> dict[str, Any]:
        self.ensure_project(workspace_id)
        role_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO workspace_roles(id, workspace_id, name, onboarding_prompt)
                VALUES (?, ?, ?, ?)
                """,
                (role_id, workspace_id, name.strip(), onboarding_prompt),
            )
        return next(role for role in self.roles(workspace_id) if role["id"] == role_id)

    def update_role(
        self, *, role_id: str, name: str | None, onboarding_prompt: str | None
    ) -> dict[str, Any]:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM workspace_roles WHERE id = ? AND deleted_at IS NULL",
                (role_id,),
            ).fetchone()
            if row is None:
                raise LookupError("role not found")
            conn.execute(
                """
                UPDATE workspace_roles SET name = ?, onboarding_prompt = ? WHERE id = ?
                """,
                (
                    name.strip() if name is not None else row["name"],
                    onboarding_prompt if onboarding_prompt is not None else row["onboarding_prompt"],
                    role_id,
                ),
            )
            workspace_id = row["workspace_id"]
        return next(role for role in self.roles(workspace_id) if role["id"] == role_id)

    def set_role_avatar(
        self, *, role_id: str, data: bytes | None, media_type: str | None
    ) -> dict[str, Any]:
        with self.transaction() as conn:
            cursor = conn.execute(
                """UPDATE workspace_roles SET avatar = ?, avatar_media_type = ?,
                   avatar_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE id = ? AND deleted_at IS NULL""",
                (data, media_type, role_id),
            )
            if cursor.rowcount != 1:
                raise LookupError("role not found")
        return self.role(role_id)

    def role_avatar(self, role_id: str) -> tuple[bytes, str] | None:
        with self._lock:
            row = self._connection.execute(
                """SELECT avatar, avatar_media_type FROM workspace_roles
                   WHERE id = ? AND deleted_at IS NULL""",
                (role_id,),
            ).fetchone()
        if row is None or row["avatar"] is None:
            return None
        return bytes(row["avatar"]), str(row["avatar_media_type"])

    def delete_role(self, role_id: str) -> bool:
        with self.transaction() as conn:
            pending = conn.execute(
                """SELECT COUNT(*) AS count FROM message_role_recipients
                   WHERE role_id = ? AND delivered_agent_id IS NULL""",
                (role_id,),
            ).fetchone()["count"]
            if pending:
                raise ValueError("role has undelivered messages; assign it before deletion")
            conn.execute(
                """
                UPDATE role_assignments
                SET ended_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE role_id = ? AND ended_at IS NULL
                """,
                (role_id,),
            )
            cursor = conn.execute(
                """
                UPDATE workspace_roles
                SET deleted_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ? AND deleted_at IS NULL
                """,
                (role_id,),
            )
        return cursor.rowcount == 1

    def assign_role(
        self, *, role_id: str, agent_id: str, assigned_by: str,
        onboarding_sent: bool = False,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        events: list[dict[str, Any]] = []
        with self.transaction() as conn:
            role = conn.execute(
                "SELECT * FROM workspace_roles WHERE id = ? AND deleted_at IS NULL",
                (role_id,),
            ).fetchone()
            if role is None:
                raise LookupError("role not found")
            agent = conn.execute(
                "SELECT 1 FROM principals WHERE id = ? AND kind = 'agent'", (agent_id,)
            ).fetchone()
            if agent is None:
                raise LookupError("agent not found")
            current = conn.execute(
                "SELECT * FROM role_assignments WHERE role_id = ? AND ended_at IS NULL",
                (role_id,),
            ).fetchone()
            if current is not None and current["agent_id"] == agent_id:
                return self._role_by_id(conn, role_id), events
            conn.execute(
                """UPDATE role_assignments SET ended_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE ended_at IS NULL AND
                     (role_id = ? OR (agent_id = ? AND workspace_id = ?))""",
                (role_id, agent_id, role["workspace_id"]),
            )
            assignment_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO role_assignments(
                       id, role_id, workspace_id, agent_id, assigned_by, onboarding_sent
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (assignment_id, role_id, role["workspace_id"], agent_id,
                 assigned_by, onboarding_sent),
            )
            pending = conn.execute(
                """SELECT message_seq FROM message_role_recipients
                   WHERE role_id = ? AND delivered_agent_id IS NULL ORDER BY message_seq""",
                (role_id,),
            ).fetchall()
            for pending_row in pending:
                message_seq = int(pending_row["message_seq"])
                inserted = conn.execute(
                    "INSERT OR IGNORE INTO inbox(recipient_id, message_seq) VALUES (?, ?)",
                    (agent_id, message_seq),
                ).rowcount
                conn.execute(
                    """UPDATE message_role_recipients SET delivered_agent_id = ?,
                       delivered_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                       WHERE role_id = ? AND message_seq = ?""",
                    (agent_id, role_id, message_seq),
                )
                if inserted:
                    events.append(self._create_delivery_event(conn, agent_id, message_seq))
            result = self._role_by_id(conn, role_id)
        return result, events

    def unassign_role(self, role_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute(
                """UPDATE role_assignments
                   SET ended_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE role_id = ? AND ended_at IS NULL""",
                (role_id,),
            )
        return cursor.rowcount == 1

    def assignment_history(self, role_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT a.*, p.display_name AS agent_name
                   FROM role_assignments a JOIN principals p ON p.id = a.agent_id
                   WHERE a.role_id = ? ORDER BY a.assigned_at DESC""",
                (role_id,),
            ).fetchall()
        result = [dict(row) for row in rows]
        for item in result:
            item["onboarding_sent"] = bool(item["onboarding_sent"])
        return result

    def active_agent_roles(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT a.agent_id, r.id AS role_id, r.name AS role_name,
                          r.workspace_id AS project_id, p.name AS project_name,
                          a.assigned_at
                   FROM role_assignments a
                   JOIN workspace_roles r ON r.id = a.role_id
                   JOIN projects p ON p.id = r.workspace_id
                   WHERE a.ended_at IS NULL AND r.deleted_at IS NULL
                   ORDER BY p.name, r.name"""
            ).fetchall()
        return [dict(row) for row in rows]

    def project_bootstrap(
        self, *, project_id: str, agent_id: str, pm_id: str
    ) -> dict[str, Any]:
        self.ensure_project(project_id)
        with self._lock:
            project = self._connection.execute(
                "SELECT id, name FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            agent = self._connection.execute(
                "SELECT id, display_name FROM principals WHERE id = ? AND kind = 'agent'",
                (agent_id,),
            ).fetchone()
            if agent is None:
                raise LookupError("agent not found")
            pm = self._connection.execute(
                """SELECT p.id, COALESCE(profile.display_name, p.display_name) AS display_name
                   FROM principals p
                   LEFT JOIN pm_profiles profile ON profile.principal_id = p.id
                   WHERE p.id = ? AND p.kind = 'human'""",
                (pm_id,),
            ).fetchone()
            if pm is None:
                raise LookupError("PM not found")
            rows = self._connection.execute(
                """SELECT r.id, r.name, a.agent_id, principal.display_name AS agent_name,
                          a.assigned_at
                   FROM workspace_roles r
                   LEFT JOIN role_assignments a
                     ON a.role_id = r.id AND a.ended_at IS NULL
                   LEFT JOIN principals principal ON principal.id = a.agent_id
                   WHERE r.workspace_id = ? AND r.deleted_at IS NULL
                   ORDER BY r.name""",
                (project_id,),
            ).fetchall()
        roles = []
        own_role = None
        for row in rows:
            role = dict(row)
            role["assigned"] = role["agent_id"] is not None
            role["self"] = role["agent_id"] == agent_id
            roles.append(role)
            if role["self"]:
                own_role = {"id": role["id"], "name": role["name"]}
        result = {
            "project": dict(project),
            "agent": {"id": agent["id"], "display_name": agent["display_name"]},
            "own_role": own_role,
            "pm": dict(pm),
            "roles": roles,
            "usage": {
                "inbox": "dispatch inbox",
                "history": "dispatch history 20",
                "reply_pm": 'dispatch reply "내용"',
                "message_role": 'dispatch reply --role 역할명 "내용"',
                "copy_role": 'dispatch reply --ref 역할명 "내용"',
                "request_review": 'dispatch request --level r2 "내용"',
                "request_approval": 'dispatch request --level r3 "내용"',
                "work_start": 'dispatch work start "작업명"',
                "work_report": 'dispatch work report "진행 내용"',
                "work_done": 'dispatch work done "완료 결과"',
                "recovery": "inbox 출력 처리 실패 시 dispatch history 20",
            },
        }
        encoded = json.dumps(result, ensure_ascii=False, sort_keys=True).encode()
        result["revision"] = hashlib.sha256(encoded).hexdigest()[:12]
        return result

    @staticmethod
    def _role_dict(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["assigned"] = value.get("assignment_id") is not None
        value["onboarding_sent"] = bool(value.get("onboarding_sent", 0))
        value["has_avatar"] = bool(value.get("has_avatar", 0))
        return value

    def _role_by_id(self, conn: sqlite3.Connection, role_id: str) -> dict[str, Any]:
        row = conn.execute(
            """SELECT r.id, r.workspace_id, r.name, r.onboarding_prompt,
                      r.created_at, r.deleted_at,
                      CASE WHEN r.avatar IS NULL THEN 0 ELSE 1 END AS has_avatar,
                      r.avatar_updated_at,
                      a.id AS assignment_id, a.agent_id, a.assigned_at,
                      a.onboarding_sent, p.display_name AS agent_name
               FROM workspace_roles r
               LEFT JOIN role_assignments a ON a.role_id = r.id AND a.ended_at IS NULL
               LEFT JOIN principals p ON p.id = a.agent_id
               WHERE r.id = ?""",
            (role_id,),
        ).fetchone()
        if row is None:
            raise LookupError("role not found")
        return self._role_dict(row)

    @staticmethod
    def _create_delivery_event(
        conn: sqlite3.Connection, recipient_id: str, message_seq: int
    ) -> dict[str, Any]:
        event_id = str(uuid.uuid4())
        cursor = conn.execute(
            """INSERT INTO delivery_events(id, recipient_id, kind, through_message_seq)
               VALUES (?, ?, 'inbox_available', ?)""",
            (event_id, recipient_id, message_seq),
        )
        return {
            "event_id": event_id, "event_seq": int(cursor.lastrowid),
            "kind": "inbox_available", "recipient_id": recipient_id,
            "through_seq": message_seq,
        }

    def send_message(
        self,
        *,
        workspace_id: str,
        sender_id: str,
        recipient_ids: list[str],
        role_ids: list[str] | None = None,
        reference_ids: list[str] | None = None,
        body: str,
        message_id: str | None = None,
        kind: str = "message",
        reply_level: str = "r1",
        in_reply_to: int | None = None,
        track: str | None = None,
        tags: list[str] | None = None,
        inherit_context: bool = True,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        message_id = message_id or str(uuid.uuid4())
        unique_recipients = list(dict.fromkeys(recipient_ids))
        unique_roles = list(dict.fromkeys(role_ids or []))
        unique_references = [
            value
            for value in dict.fromkeys(reference_ids or [])
            if value not in unique_recipients
        ]
        normalized_track = track.strip() if track and track.strip() else None
        normalized_tags = self._normalize_tags(tags) if tags is not None else None
        with self.transaction() as conn:
            resolved_roles: list[tuple[str, str | None]] = []
            for role_id in unique_roles:
                role = conn.execute(
                    """SELECT r.workspace_id, a.agent_id FROM workspace_roles r
                       LEFT JOIN role_assignments a ON a.role_id = r.id AND a.ended_at IS NULL
                       WHERE r.id = ? AND r.deleted_at IS NULL""",
                    (role_id,),
                ).fetchone()
                if role is None or role["workspace_id"] != workspace_id:
                    raise LookupError(f"role {role_id} not found in workspace")
                resolved_roles.append((role_id, role["agent_id"]))
                if role["agent_id"] and role["agent_id"] not in unique_recipients:
                    unique_recipients.append(role["agent_id"])
            if in_reply_to is not None and inherit_context:
                parent = conn.execute(
                    "SELECT track FROM messages WHERE seq = ?", (in_reply_to,)
                ).fetchone()
                if parent is None:
                    raise ValueError(f"parent message {in_reply_to} not found")
                if normalized_track is None:
                    normalized_track = parent["track"]
                if normalized_tags is None:
                    normalized_tags = self._message_tags(in_reply_to)
            normalized_tags = normalized_tags or []
            normalized_tags = [tag for tag in normalized_tags if tag != normalized_track]
            next_project_seq = int(
                conn.execute(
                    "SELECT COALESCE(MAX(project_seq), 0) + 1 FROM messages"
                    " WHERE workspace_id = ?",
                    (workspace_id,),
                ).fetchone()[0]
            )
            cursor = conn.execute(
                """
                INSERT INTO messages(
                  id, workspace_id, sender_id, body, kind, reply_level, in_reply_to,
                  track, project_seq
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id, workspace_id, sender_id, body,
                    kind, reply_level, in_reply_to, normalized_track,
                    next_project_seq,
                ),
            )
            message_seq = int(cursor.lastrowid)
            for role_id, agent_id in resolved_roles:
                conn.execute(
                    """INSERT INTO message_role_recipients(
                           role_id, message_seq, delivered_agent_id, delivered_at
                       ) VALUES (?, ?, ?, CASE WHEN ? IS NULL THEN NULL
                           ELSE strftime('%Y-%m-%dT%H:%M:%fZ', 'now') END)""",
                    (role_id, message_seq, agent_id, agent_id),
                )
            for tag in normalized_tags:
                conn.execute(
                    "INSERT INTO message_tags(message_seq, tag) VALUES (?, ?)",
                    (message_seq, tag),
                )
            events: list[dict[str, Any]] = []
            for principal_id in unique_references:
                conn.execute(
                    "INSERT INTO message_references(principal_id, message_seq) VALUES (?, ?)",
                    (principal_id, message_seq),
                )
                # 참조도 배달한다. 배달하지 않으면 보는 사람이 참조 대신 수신자
                # 자리에 넣게 되고, 받는 쪽은 그것을 지시로 읽는다. 읽을 수는
                # 있되 답할 자리는 아니라는 구분이 필요해서 자리를 나눠 둔다.
                conn.execute(
                    "INSERT INTO inbox(recipient_id, message_seq) VALUES (?, ?)",
                    (principal_id, message_seq),
                )
                events.append(
                    self._create_delivery_event(conn, principal_id, message_seq)
                )
            for recipient_id in unique_recipients:
                conn.execute(
                    "INSERT INTO inbox(recipient_id, message_seq) VALUES (?, ?)",
                    (recipient_id, message_seq),
                )
                events.append(self._create_delivery_event(conn, recipient_id, message_seq))
            row = conn.execute(
                "SELECT * FROM messages WHERE seq = ?", (message_seq,)
            ).fetchone()
        message = dict(row)
        message["recipient_ids"] = unique_recipients
        message["reference_ids"] = unique_references
        message["role_ids"] = unique_roles
        message["tags"] = normalized_tags
        return message, events

    def messages_after(self, *, recipient_id: str, after: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT m.*, p.display_name AS sender_name,
                              parent.project_seq AS in_reply_to_project_seq,
                              EXISTS (
                                SELECT 1 FROM message_references r
                                WHERE r.message_seq = m.seq
                                  AND r.principal_id = i.recipient_id
                              ) AS is_reference
                FROM messages m
                JOIN inbox i ON i.message_seq = m.seq
                JOIN principals p ON p.id = m.sender_id
                LEFT JOIN messages parent ON parent.seq = m.in_reply_to
                WHERE i.recipient_id = ? AND m.seq > ?
                ORDER BY m.seq ASC
                """,
                (recipient_id, after),
            ).fetchall()
        result = []
        for row in rows:
            message = dict(row)
            message["tags"] = self._message_tags(message["seq"])
            message["role_recipients"] = self._message_roles(message["seq"])
            result.append(message)
        return result

    def timeline(self, principal_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT DISTINCT m.*, p.display_name AS sender_name
                FROM messages m
                JOIN principals p ON p.id = m.sender_id
                LEFT JOIN messages parent ON parent.seq = m.in_reply_to
                LEFT JOIN inbox own ON own.message_seq = m.seq
                  AND own.recipient_id = ?
                WHERE m.sender_id = ? OR own.recipient_id IS NOT NULL
                ORDER BY m.seq DESC LIMIT ?
                """,
                (principal_id, principal_id, limit),
            ).fetchall()
            result = []
            for row in reversed(rows):
                message = dict(row)
                message["recipients"] = self._message_recipients(message["seq"])
                message["references"] = self._message_references(message["seq"])
                message["tags"] = self._message_tags(message["seq"])
                message["role_recipients"] = self._message_roles(message["seq"])
                result.append(message)
        return result

    def workspace_timeline(
        self, workspace_id: str, limit: int = 100,
        after: int | None = None, before: int | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            if before is not None:
                rows = self._connection.execute(
                    """SELECT m.*, p.display_name AS sender_name,
                              parent.project_seq AS in_reply_to_project_seq
                       FROM messages m JOIN principals p ON p.id = m.sender_id
                       LEFT JOIN messages parent ON parent.seq = m.in_reply_to
                       WHERE m.workspace_id = ? AND m.seq < ?
                       ORDER BY m.seq DESC LIMIT ?""",
                    (workspace_id, before, limit),
                ).fetchall()
                rows = list(reversed(rows))
            elif after is None:
                rows = self._connection.execute(
                    """SELECT m.*, p.display_name AS sender_name,
                              parent.project_seq AS in_reply_to_project_seq
                       FROM messages m JOIN principals p ON p.id = m.sender_id
                       LEFT JOIN messages parent ON parent.seq = m.in_reply_to
                       WHERE m.workspace_id = ?
                       ORDER BY m.seq DESC LIMIT ?""",
                    (workspace_id, limit),
                ).fetchall()
                rows = list(reversed(rows))
            else:
                rows = self._connection.execute(
                    """SELECT m.*, p.display_name AS sender_name,
                              parent.project_seq AS in_reply_to_project_seq
                       FROM messages m JOIN principals p ON p.id = m.sender_id
                       LEFT JOIN messages parent ON parent.seq = m.in_reply_to
                       WHERE m.workspace_id = ? AND m.seq > ?
                       ORDER BY m.seq ASC LIMIT ?""",
                    (workspace_id, after, limit),
                ).fetchall()
            result = []
            for row in rows:
                message = dict(row)
                message["recipients"] = self._message_recipients(message["seq"])
                message["references"] = self._message_references(message["seq"])
                message["tags"] = self._message_tags(message["seq"])
                message["role_recipients"] = self._message_roles(message["seq"])
                result.append(message)
        return result

    def bookmarks(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT b.*, p.display_name AS created_by_name,
                          m.project_seq AS message_project_seq
                   FROM message_bookmarks b
                   JOIN principals p ON p.id = b.created_by
                   LEFT JOIN messages m ON m.seq = b.message_seq
                   WHERE b.workspace_id = ?
                   ORDER BY b.message_seq ASC, b.created_at ASC""",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_bookmark(
        self, *, workspace_id: str, message_seq: int,
        label: str, created_by: str,
    ) -> dict[str, Any]:
        bookmark_id = str(uuid.uuid4())
        with self.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO message_bookmarks(
                       id, workspace_id, message_seq, label, created_by
                   )
                   SELECT ?, ?, m.seq, ?, ? FROM messages m
                   WHERE m.seq = ? AND m.workspace_id = ?""",
                (
                    bookmark_id, workspace_id, label, created_by,
                    message_seq, workspace_id,
                ),
            )
            if cursor.rowcount != 1:
                raise LookupError("message not found in project")
            row = conn.execute(
                "SELECT * FROM message_bookmarks WHERE id = ?", (bookmark_id,)
            ).fetchone()
        return dict(row)

    def delete_bookmark(self, *, workspace_id: str, bookmark_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM message_bookmarks WHERE workspace_id = ? AND id = ?",
                (workspace_id, bookmark_id),
            )
        return cursor.rowcount == 1

    def timeline_pins(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT t.*, p.display_name AS created_by_name,
                          m.project_seq AS after_message_project_seq
                   FROM timeline_pins t
                   JOIN principals p ON p.id = t.created_by
                   LEFT JOIN messages m ON m.seq = t.after_message_seq
                   WHERE t.workspace_id = ?
                   ORDER BY t.after_message_seq ASC""",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_timeline_pin(
        self, *, workspace_id: str, after_message_seq: int,
        label: str, created_by: str,
    ) -> dict[str, Any]:
        pin_id = str(uuid.uuid4())
        with self.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO timeline_pins(
                       id, workspace_id, after_message_seq, label, created_by
                   )
                   SELECT ?, ?, m.seq, ?, ? FROM messages m
                   WHERE m.seq = ? AND m.workspace_id = ?""",
                (
                    pin_id, workspace_id, label, created_by,
                    after_message_seq, workspace_id,
                ),
            )
            if cursor.rowcount != 1:
                raise LookupError("message not found in project")
            row = conn.execute(
                "SELECT * FROM timeline_pins WHERE id = ?", (pin_id,)
            ).fetchone()
        return dict(row)

    def delete_timeline_pin(self, *, workspace_id: str, pin_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM timeline_pins WHERE workspace_id = ? AND id = ?",
                (workspace_id, pin_id),
            )
        return cursor.rowcount == 1

    def _message_references(self, message_seq: int) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """
            SELECT r.principal_id, p.display_name
            FROM message_references r
            JOIN principals p ON p.id = r.principal_id
            WHERE r.message_seq = ? ORDER BY p.display_name
            """,
            (message_seq,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _message_tags(self, message_seq: int) -> list[str]:
        rows = self._connection.execute(
            "SELECT tag FROM message_tags WHERE message_seq = ? ORDER BY rowid",
            (message_seq,),
        ).fetchall()
        return [str(row["tag"]) for row in rows]

    def _message_roles(self, message_seq: int) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """SELECT mr.role_id, r.name, mr.delivered_agent_id, mr.delivered_at
               FROM message_role_recipients mr
               JOIN workspace_roles r ON r.id = mr.role_id
               WHERE mr.message_seq = ? ORDER BY r.name""",
            (message_seq,),
        ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _normalize_tags(tags: list[str]) -> list[str]:
        normalized = [tag.strip() for tag in tags if tag.strip()]
        if len(normalized) > 20:
            raise ValueError("a message may have at most 20 tags")
        if any(len(tag) > 120 for tag in normalized):
            raise ValueError("tags may be at most 120 characters")
        return list(dict.fromkeys(normalized))

    def attention(self, principal_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT m.*, p.display_name AS sender_name,
                              parent.project_seq AS in_reply_to_project_seq
                FROM messages m
                JOIN principals p ON p.id = m.sender_id
                LEFT JOIN messages parent ON parent.seq = m.in_reply_to
                JOIN inbox i ON i.message_seq = m.seq
                WHERE i.recipient_id = ? AND m.kind = 'pm_request'
                  AND NOT EXISTS (
                    SELECT 1 FROM messages answer
                    WHERE answer.in_reply_to = m.seq
                      AND answer.sender_id = ?
                  )
                ORDER BY CASE m.reply_level
                  WHEN 'r3' THEN 3 WHEN 'r2' THEN 2 ELSE 1 END DESC,
                  m.seq ASC
                """,
                (principal_id, principal_id),
            ).fetchall()
            result = []
            for row in rows:
                message = dict(row)
                message["recipients"] = self._message_recipients(message["seq"])
                message["references"] = self._message_references(message["seq"])
                message["tags"] = self._message_tags(message["seq"])
                message["role_recipients"] = self._message_roles(message["seq"])
                result.append(message)
        return result

    def workspace_attention(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT m.*, p.display_name AS sender_name,
                              parent.project_seq AS in_reply_to_project_seq
                FROM messages m JOIN principals p ON p.id = m.sender_id
                       LEFT JOIN messages parent ON parent.seq = m.in_reply_to
                WHERE m.workspace_id = ? AND m.kind = 'pm_request'
                  AND NOT EXISTS (
                    SELECT 1 FROM messages answer
                    JOIN principals answerer ON answerer.id = answer.sender_id
                    WHERE answer.in_reply_to = m.seq
                      AND answerer.kind = 'human'
                  )
                ORDER BY CASE m.reply_level
                  WHEN 'r3' THEN 3 WHEN 'r2' THEN 2 ELSE 1 END DESC,
                  m.seq ASC
                """,
                (workspace_id,),
            ).fetchall()
            result = []
            for row in rows:
                message = dict(row)
                message["recipients"] = self._message_recipients(message["seq"])
                message["references"] = self._message_references(message["seq"])
                message["tags"] = self._message_tags(message["seq"])
                message["role_recipients"] = self._message_roles(message["seq"])
                result.append(message)
        return result

    def _message_recipients(self, message_seq: int) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """
            SELECT i.recipient_id, p.display_name,
                   i.received_at, i.processed_at
            FROM inbox i JOIN principals p ON p.id = i.recipient_id
            WHERE i.message_seq = ?
              AND NOT EXISTS (
                SELECT 1 FROM message_references r
                WHERE r.message_seq = i.message_seq
                  AND r.principal_id = i.recipient_id
              )
            ORDER BY p.display_name
            """,
            (message_seq,),
        ).fetchall()
        return [dict(row) for row in rows]

    def shared_values(
        self, *, workspace_id: str, keys: list[str] | None = None
    ) -> list[dict[str, Any]]:
        with self._lock:
            if keys:
                placeholders = ",".join("?" for _ in keys)
                rows = self._connection.execute(
                    f"""
                    SELECT * FROM shared_values
                    WHERE workspace_id = ? AND key IN ({placeholders})
                    ORDER BY key
                    """,
                    (workspace_id, *keys),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """
                    SELECT * FROM shared_values
                    WHERE workspace_id = ? ORDER BY key
                    """,
                    (workspace_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def upsert_shared_value(
        self, *, workspace_id: str, key: str, value: str, updated_by: str
    ) -> dict[str, Any]:
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO shared_values(workspace_id, key, value, updated_by)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(workspace_id, key) DO UPDATE SET
                  value = excluded.value,
                  version = shared_values.version + 1,
                  updated_by = excluded.updated_by,
                  updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                (workspace_id, key, value, updated_by),
            )
            row = conn.execute(
                """
                SELECT * FROM shared_values WHERE workspace_id = ? AND key = ?
                """,
                (workspace_id, key),
            ).fetchone()
        return dict(row)

    def delete_shared_value(self, *, workspace_id: str, key: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM shared_values WHERE workspace_id = ? AND key = ?",
                (workspace_id, key),
            )
        return cursor.rowcount == 1

    def start_work(
        self, *, workspace_id: str, agent_id: str, title: str
    ) -> dict[str, Any]:
        work_id = str(uuid.uuid4())
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO work_items(id, workspace_id, agent_id, title)
                VALUES (?, ?, ?, ?)
                """,
                (work_id, workspace_id, agent_id, title),
            )
            row = conn.execute(
                "SELECT * FROM work_items WHERE id = ?", (work_id,)
            ).fetchone()
        return self._work_dict(row)

    def update_active_work(
        self, *, agent_id: str, report: str, done: bool
    ) -> dict[str, Any]:
        with self.transaction() as conn:
            row = conn.execute(
                """
                SELECT * FROM work_items
                WHERE agent_id = ? AND status = 'active'
                """,
                (agent_id,),
            ).fetchone()
            if row is None:
                raise LookupError("active work not found")
            kind = "done" if done else "report"
            conn.execute(
                "INSERT INTO work_reports(work_id, body, kind) VALUES (?, ?, ?)",
                (row["id"], report, kind),
            )
            conn.execute(
                """
                UPDATE work_items SET last_report = ?,
                  status = CASE WHEN ? THEN 'done' ELSE status END,
                  ended_at = CASE WHEN ? THEN strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                                  ELSE ended_at END,
                  updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (report, done, done, row["id"]),
            )
            updated = conn.execute(
                "SELECT * FROM work_items WHERE id = ?", (row["id"],)
            ).fetchone()
        return self._work_dict(updated)

    def work_items(self, *, workspace_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT w.*, p.display_name AS agent_name
                FROM work_items w JOIN principals p ON p.id = w.agent_id
                WHERE w.workspace_id = ?
                ORDER BY CASE w.status WHEN 'active' THEN 0 ELSE 1 END,
                         w.started_at DESC LIMIT ?
                """,
                (workspace_id, limit),
            ).fetchall()
        return [self._work_dict(row) for row in rows]

    @staticmethod
    def _work_dict(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        with sqlite3.connect(":memory:") as conn:
            elapsed = conn.execute(
                """
                SELECT CAST((julianday(COALESCE(?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))
                  - julianday(?)) * 86400 AS INTEGER)
                """,
                (value.get("ended_at"), value["started_at"]),
            ).fetchone()[0]
        value["elapsed_seconds"] = max(0, int(elapsed or 0))
        value["token_usage"] = None
        return value

    def delivery_events_after(
        self, *, recipient_id: str, after: int
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT id AS event_id, seq AS event_seq, kind, recipient_id,
                       through_message_seq AS through_seq
                FROM delivery_events
                WHERE recipient_id = ? AND seq > ?
                ORDER BY seq ASC
                """,
                (recipient_id, after),
            ).fetchall()
        return [dict(row) for row in rows]

    def ack(self, *, recipient_id: str, through_seq: int, processed: bool) -> dict[str, int]:
        column = "processed_at" if processed else "received_at"
        with self.transaction() as conn:
            exists = conn.execute(
                """
                SELECT 1 FROM inbox
                WHERE recipient_id = ? AND message_seq = ?
                """,
                (recipient_id, through_seq),
            ).fetchone()
            if exists is None:
                raise LookupError("through_seq is not in the recipient inbox")
            conn.execute(
                f"""
                UPDATE inbox
                SET {column} = COALESCE({column}, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                WHERE recipient_id = ? AND message_seq <= ?
                """,
                (recipient_id, through_seq),
            )
            if processed:
                conn.execute(
                    """
                    UPDATE inbox
                    SET received_at = COALESCE(received_at, processed_at)
                    WHERE recipient_id = ? AND message_seq <= ?
                    """,
                    (recipient_id, through_seq),
                )
            state = self._inbox_state(conn, recipient_id)
        return state

    def inbox_state(self, recipient_id: str) -> dict[str, int]:
        with self._lock:
            return self._inbox_state(self._connection, recipient_id)

    @staticmethod
    def _inbox_state(conn: sqlite3.Connection, recipient_id: str) -> dict[str, int]:
        row = conn.execute(
            """
            SELECT
              COALESCE(MAX(CASE WHEN received_at IS NOT NULL THEN message_seq END), 0)
                AS received_seq,
              COALESCE(MAX(CASE WHEN processed_at IS NOT NULL THEN message_seq END), 0)
                AS processed_seq,
              COUNT(CASE WHEN processed_at IS NULL THEN 1 END) AS pending_count
            FROM inbox WHERE recipient_id = ?
            """,
            (recipient_id,),
        ).fetchone()
        return {key: int(row[key]) for key in row.keys()}
