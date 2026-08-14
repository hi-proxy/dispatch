from dispatch_node.cmux import CmuxAgentCandidate
from dispatch_node.registry import LocalRegistry
from dispatch_node.tui import ConnectionController


def candidate(*, verified=True):
    return CmuxAgentCandidate(
        provider="codex",
        agent_session_id="session-12345678",
        surface_id="surface-1",
        surface_ref="surface:1",
        workspace_ref="workspace:1",
        title="Agent terminal",
        tty="ttys001",
        cwd="/project",
        lifecycle="idle",
        binding_verified=verified,
        verification_reason=(
            "agent_tty_matches_surface"
            if verified
            else "agent_tty_surface_tty_mismatch"
        ),
    )


class FakeCmux:
    def __init__(self, candidates):
        self.candidates = candidates
        self.focused = []

    def discover_agents(self):
        return self.candidates

    def focus(self, selected):
        self.focused.append(selected.surface_id)


def test_toggle_adds_and_removes_connection_without_terminal_input(tmp_path):
    registry = LocalRegistry(tmp_path / "node.db")
    cmux = FakeCmux([candidate()])
    controller = ConnectionController(registry, cmux)
    controller.refresh()
    controller.toggle_selected()
    assert len(controller.bindings()) == 1
    assert controller.bindings()[0]["local_name"] == "codex-session1"
    controller.toggle_selected()
    assert controller.bindings() == []
    assert "terminal unchanged" in controller.message


def test_unverified_candidate_cannot_be_connected(tmp_path):
    registry = LocalRegistry(tmp_path / "node.db")
    controller = ConnectionController(registry, FakeCmux([candidate(verified=False)]))
    controller.refresh()
    controller.toggle_selected()
    assert controller.bindings() == []
    assert controller.message.startswith("cannot connect")
