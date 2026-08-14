from __future__ import annotations

import curses
import json
import time
from dataclasses import dataclass, field
from typing import Any

from .cmux import CmuxAdapter, CmuxAgentCandidate
from .registry import LocalRegistry


@dataclass
class ConnectionController:
    registry: LocalRegistry
    cmux: CmuxAdapter
    candidates: list[CmuxAgentCandidate] = field(default_factory=list)
    selected: int = 0
    message: str = ""

    def refresh(self) -> None:
        try:
            self.candidates = self.cmux.discover_agents()
            self.selected = min(self.selected, max(0, len(self.candidates) - 1))
            self.message = f"found {len(self.candidates)} open agent terminal(s)"
        except Exception as error:
            self.message = f"refresh failed: {error}"

    def bindings(self) -> list[dict[str, Any]]:
        return self.registry.list()

    def binding_for(self, candidate: CmuxAgentCandidate) -> dict[str, Any] | None:
        return next(
            (
                binding
                for binding in self.bindings()
                if binding["agent_session_id"] == candidate.agent_session_id
                and binding["surface_id"] == candidate.surface_id
            ),
            None,
        )

    def move(self, delta: int) -> None:
        if self.candidates:
            self.selected = (self.selected + delta) % len(self.candidates)

    def toggle_selected(self) -> None:
        if not self.candidates:
            self.message = "no open agent terminal selected"
            return
        candidate = self.candidates[self.selected]
        binding = self.binding_for(candidate)
        if binding:
            self.registry.detach(binding["local_name"])
            self.message = f"disconnected {binding['local_name']} (terminal unchanged)"
            return
        if not candidate.binding_verified:
            self.message = f"cannot connect: {candidate.verification_reason}"
            return
        local_name = self._available_name(candidate)
        self.registry.attach(local_name, candidate)
        self.message = f"connected {local_name}"

    def focus_selected(self) -> None:
        if not self.candidates:
            self.message = "no open agent terminal selected"
            return
        try:
            self.cmux.focus(self.candidates[self.selected])
            self.message = "focused selected terminal"
        except Exception as error:
            self.message = f"focus failed: {error}"

    def _available_name(self, candidate: CmuxAgentCandidate) -> str:
        short_session = candidate.agent_session_id.replace("-", "")[:8]
        base = f"{candidate.provider}-{short_session}"
        names = {binding["local_name"] for binding in self.bindings()}
        if base not in names:
            return base
        suffix = 2
        while f"{base}-{suffix}" in names:
            suffix += 1
        return f"{base}-{suffix}"


def _clip(value: object, width: int) -> str:
    text = str(value or "-").replace("\n", " ")
    if width <= 1:
        return ""
    return text if len(text) < width else text[: width - 1] + "…"


def _put(screen: Any, row: int, column: int, text: str, style: int = 0) -> None:
    height, width = screen.getmaxyx()
    if row < 0 or row >= height or column >= width:
        return
    try:
        screen.addstr(row, column, _clip(text, width - column), style)
    except curses.error:
        pass


def _draw(screen: Any, controller: ConnectionController) -> None:
    screen.erase()
    height, width = screen.getmaxyx()
    _put(screen, 0, 0, "Dispatch · cmux connections", curses.A_BOLD)
    _put(screen, 1, 0, "↑/↓ select   Enter connect/disconnect   f focus   r refresh   q quit")
    _put(screen, 3, 0, "OPEN AGENT TERMINALS", curses.A_BOLD)
    row = 4
    if not controller.candidates:
        _put(screen, row, 2, "No agent terminal discovered")
        row += 1
    for index, candidate in enumerate(controller.candidates):
        connected = controller.binding_for(candidate)
        marker = "●" if connected else "○"
        verified = "verified" if candidate.binding_verified else "unsafe"
        line = (
            f"{marker} {candidate.provider:<7} {candidate.lifecycle:<11} "
            f"{verified:<8} {candidate.title}  {candidate.cwd or '-'}"
        )
        style = curses.A_REVERSE if index == controller.selected else 0
        _put(screen, row, 0, line, style)
        row += 1
        if row >= height - 5:
            break

    row += 1
    _put(screen, row, 0, "CONNECTED TO DISPATCH", curses.A_BOLD)
    row += 1
    bindings = controller.bindings()
    if not bindings:
        _put(screen, row, 2, "No connections")
        row += 1
    for binding in bindings:
        data = json.loads(binding["data_json"])
        line = (
            f"● {binding['local_name']:<20} {binding['provider']:<7} "
            f"{binding['lifecycle']:<11} {data.get('title', '-')}"
        )
        _put(screen, row, 0, line)
        row += 1
        if row >= height - 2:
            break

    _put(screen, height - 1, 0, controller.message, curses.A_DIM)
    screen.refresh()


def run_tui(registry: LocalRegistry, cmux: CmuxAdapter) -> None:
    controller = ConnectionController(registry, cmux)

    def session(screen: Any) -> None:
        curses.curs_set(0)
        screen.keypad(True)
        screen.timeout(500)
        controller.refresh()
        refreshed_at = time.monotonic()
        while True:
            _draw(screen, controller)
            key = screen.getch()
            if key in (ord("q"), 27):
                return
            if key in (curses.KEY_UP, ord("k")):
                controller.move(-1)
            elif key in (curses.KEY_DOWN, ord("j")):
                controller.move(1)
            elif key in (curses.KEY_ENTER, 10, 13, ord(" ")):
                controller.toggle_selected()
            elif key == ord("f"):
                controller.focus_selected()
            elif key == ord("r"):
                controller.refresh()
                refreshed_at = time.monotonic()
            if time.monotonic() - refreshed_at >= 2:
                controller.refresh()
                refreshed_at = time.monotonic()

    curses.wrapper(session)
