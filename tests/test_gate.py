import sqlite3

from dispatch_node.cmux import CmuxAdapter, CmuxAgentCandidate
from dispatch_node.gate import IdleGate
from dispatch_node.registry import LocalRegistry


class GateCmux(CmuxAdapter):
    def __init__(self, candidate, prompt_ready=False):
        self.candidate = candidate
        self.wakes = []
        self._prompt_ready = prompt_ready

    def discover_agents(self):
        return [self.candidate]

    def resolve_binding_candidate(self, **binding):
        if (
            self.candidate.provider == binding["provider"]
            and self.candidate.agent_session_id == binding["agent_session_id"]
            and self.candidate.surface_id == binding["surface_id"]
        ):
            return self.candidate
        return None

    def wake(self, surface_id, text="[dispatch] inbox"):
        self.wakes.append((surface_id, text))

    def prompt_ready(self, surface_id):
        return self._prompt_ready


def candidate(lifecycle="idle"):
    return CmuxAgentCandidate(
        provider="codex",
        agent_session_id="session-1",
        surface_id="surface-uuid",
        surface_ref="surface:7",
        workspace_ref="workspace:1",
        title="Agent",
        tty="ttys007",
        cwd="/project",
        lifecycle=lifecycle,
        binding_verified=True,
        verification_reason="agent_tty_matches_surface",
    )


def record_pending(registry):
    registry.record_event(
        {
            "event_id": "event-1",
            "event_seq": 1,
            "recipient_id": "agent-1",
            "through_seq": 4,
            "kind": "inbox_available",
        }
    )


def test_running_never_wakes(tmp_path):
    registry = LocalRegistry(tmp_path / "node.db")
    current = candidate("running")
    registry.attach("agent-1", current)
    record_pending(registry)
    cmux = GateCmux(current)
    decision = IdleGate(registry, cmux, settle_seconds=0).run(
        "agent-1", send=True
    )
    assert decision.reason == "lifecycle_running"
    assert cmux.wakes == []


def test_needs_input_wakes_only_at_bare_prompt(tmp_path):
    registry = LocalRegistry(tmp_path / "node.db")
    waiting = candidate("needs_input")
    registry.attach("agent-1", waiting)
    record_pending(registry)
    blocked = GateCmux(waiting, prompt_ready=False)
    assert IdleGate(registry, blocked, settle_seconds=0).run(
        "agent-1", send=True
    ).reason == "lifecycle_needs_input"
    assert blocked.wakes == []

    ready = GateCmux(waiting, prompt_ready=True)
    decision = IdleGate(registry, ready, settle_seconds=0).run(
        "agent-1", send=True
    )
    assert decision.eligible is True
    assert ready.wakes == [("surface-uuid", "[dispatch] inbox")]


def test_fresh_session_wakes_at_bare_prompt(tmp_path):
    """한 턴도 안 돈 세션의 lifecycle은 믿을 수 없다.

    8/16 실측: 같은 조건에서 tester1은 unknown, tester2는 running이었고 둘 다
    화면은 빈 프롬프트였다. lifecycle만 보면 배정 직후 첫 메시지가 영원히
    도착하지 않고, 사람이 터미널을 건드려 줘야만 풀린다. 화면이 판단한다.
    """
    for lifecycle in ("unknown", "running"):
        registry = LocalRegistry(tmp_path / f"node-{lifecycle}.db")
        fresh = candidate(lifecycle)
        registry.attach("agent-1", fresh)
        record_pending(registry)

        busy = GateCmux(fresh, prompt_ready=False)
        assert IdleGate(registry, busy, settle_seconds=0).run(
            "agent-1", send=True
        ).reason == f"lifecycle_{lifecycle}"
        assert busy.wakes == []

        ready = GateCmux(fresh, prompt_ready=True)
        decision = IdleGate(registry, ready, settle_seconds=0).run(
            "agent-1", send=True
        )
        assert decision.eligible is True
        assert ready.wakes == [("surface-uuid", "[dispatch] inbox")]
        registry.close()


def test_idle_collapses_pending_and_sends_once(tmp_path):
    registry = LocalRegistry(tmp_path / "node.db")
    current = candidate("idle")
    registry.attach("agent-1", current)
    record_pending(registry)
    registry.record_event(
        {
            "event_id": "event-2",
            "event_seq": 2,
            "recipient_id": "agent-1",
            "through_seq": 5,
            "kind": "inbox_available",
        }
    )
    cmux = GateCmux(current)
    gate = IdleGate(registry, cmux, settle_seconds=0)
    first = gate.run("agent-1", send=True)
    second = gate.run("agent-1", send=True)
    assert first.eligible is True
    assert first.pending_count == 2
    assert first.through_seq == 5
    assert second.reason == "wake_unconfirmed"
    assert cmux.wakes == [("surface-uuid", "[dispatch] inbox")]


def test_dry_run_never_records_or_sends(tmp_path):
    registry = LocalRegistry(tmp_path / "node.db")
    current = candidate("idle")
    registry.attach("agent-1", current)
    record_pending(registry)
    cmux = GateCmux(current)
    decision = IdleGate(registry, cmux, settle_seconds=0).run(
        "agent-1", send=False
    )
    assert decision.eligible is True
    assert cmux.wakes == []
    assert registry.outstanding_wake("agent-1") is None


def test_unverified_binding_is_rejected(tmp_path):
    registry = LocalRegistry(tmp_path / "node.db")
    unverified = CmuxAgentCandidate(
        **{
            **candidate("idle").__dict__,
            "binding_verified": False,
            "verification_reason": "agent_tty_surface_tty_mismatch",
        }
    )
    registry.attach("agent-1", unverified)
    record_pending(registry)
    gate = IdleGate(registry, GateCmux(unverified), settle_seconds=0)
    try:
        gate.run("agent-1", send=True)
    except LookupError as error:
        assert "PID/TTY verification" in str(error)
    else:
        raise AssertionError("unverified binding was allowed")


def test_registry_migrates_pre_gate_binding_table(tmp_path):
    path = tmp_path / "old-node.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE bindings (
          local_name TEXT PRIMARY KEY, provider TEXT NOT NULL,
          agent_session_id TEXT NOT NULL, surface_id TEXT NOT NULL,
          lifecycle TEXT NOT NULL, attached INTEGER NOT NULL,
          data_json TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO bindings VALUES (
          'agent-1', 'codex', 'session-1', 'surface-1',
          'idle', 1, '{}', '2026-08-14T00:00:00.000Z'
        )
        """
    )
    connection.commit()
    connection.close()
    registry = LocalRegistry(path)
    assert registry.binding("agent-1")["lifecycle_changed_at"] == (
        "2026-08-14T00:00:00.000Z"
    )


def test_gate_migrates_one_internal_codex_binding_to_canonical_session(tmp_path):
    registry = LocalRegistry(tmp_path / "node.db")
    internal = CmuxAgentCandidate(
        **{
            **candidate("idle").__dict__,
            "agent_session_id": "internal-session",
            "surface_id": "surface-internal",
        }
    )
    canonical = candidate("idle")
    registry.attach("agent-1", internal)

    class MigratingCmux(GateCmux):
        def resolve_binding_candidate(self, **binding):
            assert binding["surface_id"] == "surface-internal"
            return canonical

    decision = IdleGate(
        registry, MigratingCmux(canonical), settle_seconds=0
    ).run("agent-1", send=False)
    assert decision.reason == "no_pending"
    repaired = registry.binding("agent-1")
    assert repaired["agent_session_id"] == "session-1"
    assert repaired["surface_id"] == "surface-uuid"


def test_surface_move_supersedes_wake_sent_to_old_terminal(tmp_path):
    registry = LocalRegistry(tmp_path / "node.db")
    old = CmuxAgentCandidate(
        **{**candidate("idle").__dict__, "surface_id": "surface-old"}
    )
    moved = CmuxAgentCandidate(
        **{**candidate("idle").__dict__, "surface_id": "surface-new"}
    )
    registry.attach("agent-1", old)
    registry.record_wake("agent-1", 7)
    assert registry.outstanding_wake("agent-1") is not None
    registry.refresh_candidate("agent-1", moved)
    assert registry.outstanding_wake("agent-1") is None
    row = registry.connection.execute(
        "SELECT status FROM wake_attempts WHERE recipient_id = ?",
        (registry.binding("agent-1")["principal_id"],),
    ).fetchone()
    assert row["status"] == "superseded"
