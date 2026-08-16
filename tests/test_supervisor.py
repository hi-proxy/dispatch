import threading

from dispatch_node.cmux import CmuxAgentCandidate
from dispatch_node.registry import LocalRegistry
from dispatch_node.supervisor import NodeSupervisor
from dispatch_node.inbox import InboxWatcher


def candidate():
    return CmuxAgentCandidate(
        provider="codex",
        agent_session_id="session-1",
        surface_id="surface-1",
        surface_ref="surface:1",
        workspace_ref="workspace:1",
        title="Agent",
        tty="ttys001",
        cwd="/project",
        lifecycle="idle",
        binding_verified=True,
        verification_reason="agent_tty_matches_surface",
    )


class RecordingSupervisor(NodeSupervisor):
    def __post_init__(self):
        self.started = []
        self.gated = []

    def _inbox_worker(self, recipient_id, stop_event):
        self.started.append(recipient_id)
        stop_event.wait(2)

    def _completion_worker(self, stop_event):
        stop_event.wait(2)

    def _run_gate(self, registry, recipient_id):
        self.gated.append(recipient_id)
        self.test_stop.set()


class WakeCmux:
    def __init__(self, current):
        self.current = current
        self.wakes = []

    def resolve_binding_candidate(self, **binding):
        return self.current

    def wake(self, surface_id, text):
        self.wakes.append((surface_id, text))

    def prompt_ready(self, surface_id):
        return True


def test_supervisor_discovers_attached_binding_and_stops_cleanly(tmp_path):
    path = tmp_path / "node.db"
    registry = LocalRegistry(path)
    registry.attach("agent-1", candidate())
    registry.close()
    stop = threading.Event()
    supervisor = RecordingSupervisor(path, "http://server", cmux=object())
    supervisor.__post_init__()
    supervisor.test_stop = stop
    supervisor.run_forever(stop)
    assert supervisor.started == ["agent-1"]
    assert supervisor.gated == ["agent-1"]


def test_supervisor_recipient_filter(tmp_path):
    path = tmp_path / "node.db"
    registry = LocalRegistry(path)
    registry.attach("agent-1", candidate())
    registry.close()
    stop = threading.Event()
    supervisor = RecordingSupervisor(
        path,
        "http://server",
        cmux=object(),
        recipients={"agent-2"},
        gate_interval=0.01,
    )
    supervisor.__post_init__()
    supervisor.test_stop = stop
    timer = threading.Timer(0.05, stop.set)
    timer.start()
    supervisor.run_forever(stop)
    timer.cancel()
    assert supervisor.started == []
    assert supervisor.gated == []


def test_supervisor_wake_contains_only_short_stable_command(tmp_path):
    path = tmp_path / "node.db"
    registry = LocalRegistry(path)
    current = candidate()
    registry.attach("agent-1", current)
    registry.record_event(
        {
            "event_id": "event-1",
            "event_seq": 1,
            "recipient_id": "agent-1",
            "through_seq": 1,
            "kind": "inbox_available",
        }
    )
    cmux = WakeCmux(current)
    supervisor = NodeSupervisor(
        path,
        "http://server",
        cmux,
        settle_seconds=0,
        send_wakes=True,
    )
    supervisor._run_gate(registry, "agent-1")
    assert cmux.wakes == [
        ("surface-1", "[dispatch] inbox — run: dispatch inbox")
    ]
    registry.close()


def test_supervisor_recovers_claim_when_reading_turn_ended_while_down(
    tmp_path, monkeypatch
):
    path = tmp_path / "node.db"
    registry = LocalRegistry(path)
    current = candidate()
    registry.attach("agent-1", current)
    registry.record_event(
        {
            "event_id": "event-1",
            "event_seq": 1,
            "recipient_id": "agent-1",
            "through_seq": 1,
            "kind": "inbox_available",
        }
    )
    registry.claim_inbox("agent-1", 1, "session-1")
    registry.record_wake("agent-1", 1)
    calls = []

    def fake_ack(self, through_seq):
        calls.append(through_seq)
        self.registry.clear_processed(self.recipient_id, through_seq)
        self.registry.mark_wake_processed(self.recipient_id, through_seq)
        self.registry.clear_claim(self.recipient_id, through_seq)
        return {"processed_seq": through_seq}

    monkeypatch.setattr(InboxWatcher, "ack_processed", fake_ack)
    cmux = WakeCmux(current)
    NodeSupervisor(path, "http://dispatch.test", cmux)._run_gate(registry, "agent-1")
    assert calls == [1]
    assert registry.claim("agent-1") is None
    assert registry.outstanding_wake("agent-1") is None
    registry.close()


def test_daemon_starts_with_no_connected_agents(tmp_path, monkeypatch):
    """앱이 이 daemon을 띄우고, 에이전트를 연결하는 길은 그 앱뿐이다.

    여기서 막으면 처음 켜는 사람은 daemon도 못 띄우고 에이전트도 못 붙인다.
    앱은 stderr를 버려서 화면에는 이유 없는 실패만 남는다.
    """
    from dispatch_node import demo

    served = threading.Event()
    monkeypatch.setattr(demo.DaemonLauncher, "_start_server", lambda self: None)
    monkeypatch.setattr(demo.NodeSupervisor, "run_forever", lambda *a, **k: None)
    monkeypatch.setattr(demo, "run_web", lambda *a, **k: served.set())

    demo.DaemonLauncher(
        registry_path=tmp_path / "node.db",
        server_db_path=tmp_path / "server.db",
        server_url="http://127.0.0.1:8787",
    ).run()

    assert served.is_set()
