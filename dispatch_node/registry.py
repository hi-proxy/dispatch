from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .cmux import CmuxAgentCandidate


SCHEMA = """
CREATE TABLE IF NOT EXISTS bindings (
    local_name TEXT PRIMARY KEY,
    principal_id TEXT UNIQUE,
    nickname TEXT,
    provider TEXT NOT NULL,
    agent_session_id TEXT NOT NULL,
    surface_id TEXT NOT NULL,
    lifecycle TEXT NOT NULL,
    attached INTEGER NOT NULL DEFAULT 1,
    data_json TEXT NOT NULL,
    lifecycle_changed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS node_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_events (
    event_id TEXT PRIMARY KEY,
    event_seq INTEGER NOT NULL,
    recipient_id TEXT NOT NULL,
    through_seq INTEGER NOT NULL,
    kind TEXT NOT NULL,
    received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(recipient_id, event_seq)
);

CREATE TABLE IF NOT EXISTS wake_attempts (
    recipient_id TEXT PRIMARY KEY,
    through_seq INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('sent', 'processed', 'superseded')),
    sent_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    processed_at TEXT
);

CREATE TABLE IF NOT EXISTS inbox_claims (
    recipient_id TEXT PRIMARY KEY,
    through_seq INTEGER NOT NULL,
    agent_session_id TEXT NOT NULL,
    claimed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS project_repositories (
    project_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""


class LocalRegistry:
    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.execute("PRAGMA busy_timeout = 5000")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def _migrate(self) -> None:
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(bindings)").fetchall()
        }
        if "lifecycle_changed_at" not in columns:
            self.connection.execute(
                "ALTER TABLE bindings ADD COLUMN lifecycle_changed_at TEXT"
            )
            self.connection.execute(
                """
                UPDATE bindings
                SET lifecycle_changed_at = COALESCE(
                  updated_at, strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                )
                """
            )
            self.connection.commit()
        if "principal_id" not in columns:
            self.connection.execute(
                "ALTER TABLE bindings ADD COLUMN principal_id TEXT"
            )
            self.connection.execute(
                "UPDATE bindings SET principal_id = local_name WHERE principal_id IS NULL"
            )
            self.connection.commit()
        if "nickname" not in columns:
            self.connection.execute("ALTER TABLE bindings ADD COLUMN nickname TEXT")
            self.connection.commit()
        wake_schema = self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'wake_attempts'"
        ).fetchone()["sql"]
        if "superseded" not in wake_schema:
            self.connection.executescript(
                """
                ALTER TABLE wake_attempts RENAME TO wake_attempts_legacy;
                CREATE TABLE wake_attempts (
                    recipient_id TEXT PRIMARY KEY,
                    through_seq INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('sent', 'processed', 'superseded')
                    ),
                    sent_at TEXT NOT NULL DEFAULT (
                        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    ),
                    processed_at TEXT
                );
                INSERT INTO wake_attempts(
                    recipient_id, through_seq, status, sent_at, processed_at
                ) SELECT recipient_id, through_seq, status, sent_at, processed_at
                  FROM wake_attempts_legacy;
                DROP TABLE wake_attempts_legacy;
                """
            )
        self._ensure_identity()

    def _ensure_identity(self) -> None:
        existing = self.connection.execute(
            "SELECT COUNT(*) AS count FROM bindings"
        ).fetchone()["count"]
        values = {
            row["key"]: row["value"]
            for row in self.connection.execute(
                "SELECT key, value FROM node_state WHERE key IN (?, ?)",
                ("node_id", "pm_principal_id"),
            )
        }
        if "node_id" not in values:
            node_id = "node-local" if existing else f"node-{uuid.uuid4()}"
            self.set_state("node_id", node_id)
        if "pm_principal_id" not in values:
            pm_id = "pm-local" if existing else f"pm-{self.node_id().removeprefix('node-')}"
            self.set_state("pm_principal_id", pm_id)

    def set_state(self, key: str, value: str) -> None:
        self.connection.execute(
            """
            INSERT INTO node_state(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        self.connection.commit()

    def state(self, key: str) -> str | None:
        row = self.connection.execute(
            "SELECT value FROM node_state WHERE key = ?", (key,)
        ).fetchone()
        return str(row["value"]) if row else None

    def node_id(self) -> str:
        value = self.state("node_id")
        assert value is not None
        return value

    def pm_principal_id(self) -> str:
        value = self.state("pm_principal_id")
        assert value is not None
        return value

    def new_agent_principal_id(self, local_name: str) -> str:
        return f"agent-{self.node_id().removeprefix('node-')}-{local_name}"

    def set_project_repository(self, project_id: str, path: str) -> dict[str, Any]:
        self.connection.execute(
            """INSERT INTO project_repositories(project_id, path) VALUES (?, ?)
               ON CONFLICT(project_id) DO UPDATE SET
                 path = excluded.path,
                 updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')""",
            (project_id, path),
        )
        self.connection.commit()
        return self.project_repository(project_id) or {}

    def project_repository(self, project_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM project_repositories WHERE project_id = ?", (project_id,)
        ).fetchone()
        return dict(row) if row else None

    def project_repositories(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM project_repositories ORDER BY project_id"
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_project_repository(self, project_id: str) -> bool:
        cursor = self.connection.execute(
            "DELETE FROM project_repositories WHERE project_id = ?", (project_id,)
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def attach(self, local_name: str, candidate: CmuxAgentCandidate) -> dict[str, Any]:
        data = asdict(candidate)
        # 창 하나에 에이전트 하나다. 같은 창을 다시 써서 새 세션을 띄우면 옛
        # binding은 갈 곳이 없다. 놔두면 서버의 창 단위 유일 제약에 걸려
        # sync가 통째로 409를 내고, 배정도 연결도 전부 막힌다. 화면에는
        # SQLite 제약 문구가 그대로 뜬다.
        self.connection.execute(
            """
            UPDATE bindings SET attached = 0,
              updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE surface_id = ? AND local_name != ? AND attached = 1
            """,
            (candidate.surface_id, local_name),
        )
        self.connection.execute(
            """
            INSERT INTO bindings(
              local_name, principal_id, provider, agent_session_id, surface_id,
              lifecycle, attached, data_json, lifecycle_changed_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            ON CONFLICT(local_name) DO UPDATE SET
              principal_id = COALESCE(bindings.principal_id, excluded.principal_id),
              provider = excluded.provider,
              agent_session_id = excluded.agent_session_id,
              surface_id = excluded.surface_id,
              lifecycle = excluded.lifecycle,
              attached = 1,
              data_json = excluded.data_json,
              lifecycle_changed_at = CASE
                WHEN bindings.lifecycle != excluded.lifecycle
                THEN strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                ELSE bindings.lifecycle_changed_at
              END,
              updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            """,
            (
                local_name,
                self.new_agent_principal_id(local_name),
                candidate.provider,
                candidate.agent_session_id,
                candidate.surface_id,
                candidate.lifecycle,
                json.dumps(data),
            ),
        )
        self.connection.commit()
        return {"local_name": local_name, **candidate.public_dict()}

    def refresh_candidate(
        self, local_name: str, candidate: CmuxAgentCandidate
    ) -> dict[str, Any]:
        row = self.connection.execute(
            """SELECT principal_id, surface_id FROM bindings
               WHERE local_name = ? AND attached = 1""",
            (local_name,),
        ).fetchone()
        if row is None:
            raise LookupError(f"active binding not found: {local_name}")
        if row["surface_id"] != candidate.surface_id:
            self.connection.execute(
                """UPDATE wake_attempts SET status = 'superseded',
                   processed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE recipient_id = ? AND status = 'sent'""",
                (row["principal_id"],),
            )
            self.connection.commit()
        return self.attach(local_name, candidate)

    def detach(self, local_name: str) -> bool:
        cursor = self.connection.execute(
            """
            UPDATE bindings SET attached = 0,
              updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE local_name = ? AND attached = 1
            """,
            (local_name,),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def set_nickname(self, local_name: str, nickname: str | None) -> dict[str, Any]:
        value = nickname.strip() if nickname else None
        cursor = self.connection.execute(
            """
            UPDATE bindings SET nickname = ?,
              updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE local_name = ? AND attached = 1
            """,
            (value or None, local_name),
        )
        self.connection.commit()
        if cursor.rowcount != 1:
            raise LookupError(f"active binding not found: {local_name}")
        return self.binding(local_name) or {}

    def list(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM bindings WHERE attached = 1 ORDER BY local_name"
        ).fetchall()
        return [dict(row) for row in rows]

    def binding(self, local_name: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT * FROM bindings
            WHERE local_name = ? AND attached = 1
            """,
            (local_name,),
        ).fetchone()
        return dict(row) if row else None

    def binding_for_surface(self, surface_id: str) -> dict[str, Any] | None:
        rows = self.connection.execute(
            "SELECT * FROM bindings WHERE surface_id = ? AND attached = 1",
            (surface_id,),
        ).fetchall()
        if len(rows) > 1:
            raise LookupError("multiple active bindings for current surface")
        return dict(rows[0]) if rows else None

    def binding_for_principal(self, principal_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT * FROM bindings
            WHERE principal_id = ? AND attached = 1
            """,
            (principal_id,),
        ).fetchone()
        return dict(row) if row else None

    def recipient_key(self, identity: str) -> str:
        binding = self.binding(identity)
        return str(binding["principal_id"]) if binding else identity

    def claim_inbox(
        self, recipient_id: str, through_seq: int, agent_session_id: str
    ) -> dict[str, Any]:
        recipient_id = self.recipient_key(recipient_id)
        self.connection.execute(
            """
            INSERT INTO inbox_claims(recipient_id, through_seq, agent_session_id)
            VALUES (?, ?, ?)
            ON CONFLICT(recipient_id) DO UPDATE SET
              through_seq = MAX(inbox_claims.through_seq, excluded.through_seq),
              agent_session_id = excluded.agent_session_id,
              claimed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            """,
            (recipient_id, through_seq, agent_session_id),
        )
        self.connection.commit()
        return self.claim(recipient_id) or {}

    def claim(self, recipient_id: str) -> dict[str, Any] | None:
        recipient_id = self.recipient_key(recipient_id)
        row = self.connection.execute(
            "SELECT * FROM inbox_claims WHERE recipient_id = ?", (recipient_id,)
        ).fetchone()
        return dict(row) if row else None

    def claim_for_session(self, agent_session_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT inbox_claims.* FROM inbox_claims
            JOIN bindings ON bindings.principal_id = inbox_claims.recipient_id
            WHERE bindings.attached = 1
              AND bindings.agent_session_id = ?
              AND inbox_claims.agent_session_id = ?
            ORDER BY inbox_claims.claimed_at LIMIT 1
            """,
            (agent_session_id, agent_session_id),
        ).fetchone()
        return dict(row) if row else None

    def clear_claim(self, recipient_id: str, through_seq: int) -> int:
        recipient_id = self.recipient_key(recipient_id)
        cursor = self.connection.execute(
            """
            DELETE FROM inbox_claims
            WHERE recipient_id = ? AND through_seq <= ?
            """,
            (recipient_id, through_seq),
        )
        self.connection.commit()
        return cursor.rowcount

    def record_event(self, event: dict[str, Any]) -> bool:
        recipient_id = self.recipient_key(event["recipient_id"])
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO pending_events(
              event_id, event_seq, recipient_id, through_seq, kind
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                event["event_id"],
                event["event_seq"],
                recipient_id,
                event["through_seq"],
                event["kind"],
            ),
        )
        self.connection.execute(
            """
            INSERT INTO node_state(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value =
              CAST(MAX(CAST(value AS INTEGER), CAST(excluded.value AS INTEGER)) AS TEXT)
            """,
            (
                f"server_event_cursor:{recipient_id}",
                str(event["event_seq"]),
            ),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def event_cursor(self, recipient_id: str) -> int:
        recipient_id = self.recipient_key(recipient_id)
        row = self.connection.execute(
            "SELECT value FROM node_state WHERE key = ?",
            (f"server_event_cursor:{recipient_id}",),
        ).fetchone()
        return int(row["value"]) if row else 0

    def pending(self, recipient_id: str | None = None) -> list[dict[str, Any]]:
        if recipient_id is None:
            rows = self.connection.execute(
                "SELECT * FROM pending_events ORDER BY event_seq"
            ).fetchall()
        else:
            recipient_id = self.recipient_key(recipient_id)
            rows = self.connection.execute(
                """
                SELECT * FROM pending_events
                WHERE recipient_id = ? ORDER BY event_seq
                """,
                (recipient_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_processed(self, recipient_id: str, through_seq: int) -> int:
        recipient_id = self.recipient_key(recipient_id)
        cursor = self.connection.execute(
            """
            DELETE FROM pending_events
            WHERE recipient_id = ? AND through_seq <= ?
            """,
            (recipient_id, through_seq),
        )
        self.connection.commit()
        return cursor.rowcount

    def pending_summary(self, recipient_id: str) -> dict[str, int]:
        recipient_id = self.recipient_key(recipient_id)
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS pending_count,
                   COALESCE(MAX(through_seq), 0) AS through_seq
            FROM pending_events WHERE recipient_id = ?
            """,
            (recipient_id,),
        ).fetchone()
        return {
            "pending_count": int(row["pending_count"]),
            "through_seq": int(row["through_seq"]),
        }

    def outstanding_wake(self, recipient_id: str) -> dict[str, Any] | None:
        recipient_id = self.recipient_key(recipient_id)
        row = self.connection.execute(
            """
            SELECT * FROM wake_attempts
            WHERE recipient_id = ? AND status = 'sent'
            """,
            (recipient_id,),
        ).fetchone()
        return dict(row) if row else None

    def record_wake(self, recipient_id: str, through_seq: int) -> None:
        recipient_id = self.recipient_key(recipient_id)
        self.connection.execute(
            """
            INSERT INTO wake_attempts(recipient_id, through_seq, status)
            VALUES (?, ?, 'sent')
            ON CONFLICT(recipient_id) DO UPDATE SET
              through_seq = excluded.through_seq,
              status = 'sent',
              sent_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
              processed_at = NULL
            """,
            (recipient_id, through_seq),
        )
        self.connection.commit()

    def mark_wake_processed(self, recipient_id: str, through_seq: int) -> None:
        recipient_id = self.recipient_key(recipient_id)
        self.connection.execute(
            """
            UPDATE wake_attempts SET
              status = 'processed',
              processed_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE recipient_id = ? AND through_seq <= ?
            """,
            (recipient_id, through_seq),
        )
        self.connection.commit()
