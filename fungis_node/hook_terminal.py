"""에이전트 hook이 알려주는 것만으로 세션을 찾는 어댑터.

cmux 없이 도는 것이 목적이다. cmux도 결국 표준 hook을 받아 파일에 적어 두고
그것을 읽을 뿐이라, 그 자리를 직접 맡으면 같은 일을 할 수 있다.

화면을 읽지 않는다. lifecycle과 무엇을 기다리는지는 에이전트가 신호로 준다.
그래서 provider의 화면이 바뀌어도 이 어댑터는 깨지지 않는다.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from threading import Event
from typing import Any, Iterator

from .terminal import AgentCandidate

SESSION_ID_PATTERN = re.compile(r"--session-id\s+([0-9a-fA-F-]{8,})")


class HookTerminalAdapter:
    """hook이 남긴 세션 장부와 프로세스 목록을 맞춰 본다.

    장부에는 session_id와 cwd가 있고 tty는 없다. hook payload가 pid를 주지
    않기 때문이다. 대신 실행 중인 프로세스의 명령줄에 --session-id가 그대로
    들어 있어서, 그 값으로 tty를 찾는다.
    """

    provider = "hook"

    def __init__(self, *, store_dir: str | Path = Path.home() / ".fungis") -> None:
        self.store_dir = Path(store_dir)

    # 발견 ---------------------------------------------------------------

    def sessions(self) -> dict[str, dict[str, Any]]:
        path = self.store_dir / "sessions.json"
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _process_index() -> dict[str, dict[str, str]]:
        """실행 중인 에이전트를 session_id로 찾을 수 있게 훑는다."""
        try:
            done = subprocess.run(
                ["ps", "-eo", "pid=,tty=,command="],
                check=False, capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return {}
        index: dict[str, dict[str, str]] = {}
        for line in done.stdout.splitlines():
            match = SESSION_ID_PATTERN.search(line)
            if not match:
                continue
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            pid, tty, command = parts
            index[match.group(1)] = {"pid": pid, "tty": tty, "command": command}
        return index

    def discover_agents(
        self, *, include_hidden: bool = False
    ) -> list[AgentCandidate]:
        processes = self._process_index()
        found: list[AgentCandidate] = []
        for session_id, record in self.sessions().items():
            process = processes.get(session_id)
            if process is None and not include_hidden:
                # 장부에는 있으나 지금 도는 프로세스가 없다. 끝난 세션이다.
                continue
            tty = (process or {}).get("tty")
            found.append(
                AgentCandidate(
                    provider=str(record.get("provider") or "claude"),
                    agent_session_id=session_id,
                    # 이 어댑터에서는 tty가 표면 식별자다. 창을 찾는 유일한 단서다.
                    surface_id=tty or session_id,
                    surface_ref=None,
                    workspace_ref=None,
                    title=str(record.get("title") or record.get("cwd") or session_id),
                    tty=tty,
                    cwd=record.get("cwd"),
                    lifecycle=str(record.get("lifecycle") or "unknown"),
                    binding_verified=bool(tty),
                    verification_reason="tty_matched" if tty else "process_not_found",
                    hidden_reason=None if process else "process_not_found",
                )
            )
        return found

    def current_surface_id(self) -> str | None:
        try:
            done = subprocess.run(
                ["ps", "-o", "tty=", "-p", str(__import__("os").getppid())],
                check=False, capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        tty = done.stdout.strip()
        return tty or None

    def canonical_surface_for_context(self, surface_id: str) -> str | None:
        # tty는 창 하나에 하나뿐이라 대표를 고를 일이 없다.
        return surface_id

    def resolve_binding_candidate(
        self, surface_id: str, *args: Any, **kwargs: Any
    ) -> AgentCandidate | None:
        for candidate in self.discover_agents():
            if candidate.surface_id == surface_id:
                return candidate
        return None

    # 상태와 조작 ---------------------------------------------------------

    def agent_events(
        self, stop_event: Event | None = None
    ) -> Iterator[dict[str, Any]]:
        # hook이 장부를 갱신하므로 흘려보낼 이벤트 스트림이 따로 없다.
        # 상태는 discover_agents로 읽는다.
        return iter(())

    def focus(self, candidate: AgentCandidate) -> None:
        """터미널 창을 앞으로 가져온다.

        tty만으로는 창을 특정할 수 없어 provider별 스크립팅이 필요하다.
        Terminal.app과 iTerm2 어댑터를 붙이기 전까지는 하지 않는다.
        """
        raise NotImplementedError("focus는 터미널 앱별 구현이 필요하다")

    def wake(self, surface_id: str, text: str = "") -> None:
        # 터미널에 아무것도 넣지 않는다. 전달은 stop hook이 맡는다.
        return None

    def prompt_ready(self, surface_id: str) -> bool:
        # 화면을 읽지 않으므로 안전한 쪽으로 답한다. 이 어댑터는 터미널에
        # 입력하지 않으니 이 값으로 무언가를 밀어 넣는 일도 없다.
        return False
