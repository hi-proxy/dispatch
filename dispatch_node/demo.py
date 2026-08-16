from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .cmux import CmuxAdapter
from .pm import PMClient
from .pm_tui import run_pm_tui
from .registry import LocalRegistry
from .supervisor import NodeSupervisor
from .web import run_web


def _healthy(server_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{server_url.rstrip('/')}/health", timeout=1) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


@dataclass
class DemoLauncher:
    registry_path: Path
    server_db_path: Path
    server_url: str = "http://127.0.0.1:8787"
    send_wakes: bool = False
    pm_name: str = "PM"

    def _start_server(self) -> subprocess.Popen | None:
        if _healthy(self.server_url):
            return None
        if self.server_url.rstrip("/") != "http://127.0.0.1:8787":
            raise RuntimeError("custom server URL must already be running")
        environment = os.environ.copy()
        environment["DISPATCH_DB"] = str(self.server_db_path)
        process = subprocess.Popen(
            [sys.executable, "-m", "dispatch_server.main"],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if _healthy(self.server_url):
                return process
            if process.poll() is not None:
                raise RuntimeError("Dispatch server exited during startup")
            time.sleep(0.1)
        process.terminate()
        process.wait(timeout=3)
        raise RuntimeError("Dispatch server did not become healthy")

    def run(self) -> None:
        registry = LocalRegistry(self.registry_path)
        if not registry.list():
            registry.close()
            raise RuntimeError("no connected agents; run dispatch-node ui first")
        registry.close()
        owned_server = self._start_server()
        stop_event = threading.Event()
        supervisor = NodeSupervisor(
            registry_path=self.registry_path,
            server_url=self.server_url,
            cmux=CmuxAdapter(),
            send_wakes=self.send_wakes,
        )
        supervisor_thread = threading.Thread(
            target=supervisor.run_forever,
            args=(stop_event,),
            name="dispatch-supervisor",
            daemon=True,
        )
        supervisor_thread.start()
        chat_registry = LocalRegistry(self.registry_path)
        try:
            run_pm_tui(
                PMClient(
                    self.server_url,
                    chat_registry,
                    pm_name=self.pm_name,
                ),
                CmuxAdapter(),
            )
        finally:
            chat_registry.close()
            stop_event.set()
            supervisor_thread.join(timeout=5)
            if owned_server is not None and owned_server.poll() is None:
                owned_server.terminate()
                try:
                    owned_server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    owned_server.kill()
                    owned_server.wait(timeout=3)


@dataclass
class StackLauncher(DemoLauncher):
    def run(self) -> None:
        registry = LocalRegistry(self.registry_path)
        if not registry.list():
            registry.close()
            raise RuntimeError("no connected agents; run dispatch-node ui first")
        registry.close()
        owned_server = self._start_server()
        stop_event = threading.Event()
        supervisor = NodeSupervisor(
            registry_path=self.registry_path,
            server_url=self.server_url,
            cmux=CmuxAdapter(),
            send_wakes=self.send_wakes,
        )
        try:
            print(
                "Dispatch stack is running. Open chat in another terminal; "
                "Ctrl-C stops this stack.",
                flush=True,
            )
            supervisor.run_forever(stop_event)
        finally:
            stop_event.set()
            if owned_server is not None and owned_server.poll() is None:
                owned_server.terminate()
                try:
                    owned_server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    owned_server.kill()
                    owned_server.wait(timeout=3)


@dataclass
class DaemonLauncher(DemoLauncher):
    control_host: str = "127.0.0.1"
    control_port: int = 8790

    def run(self) -> None:
        # 연결된 에이전트가 없어도 뜬다. 앱이 이 daemon을 띄우고, 에이전트를
        # 연결하는 길은 그 앱뿐이라, 여기서 막으면 처음 켜는 사람은 영영
        # 아무것도 못 한다. supervisor는 빈 레지스트리를 견디고 새로 붙는
        # 것을 2초마다 알아서 집는다.
        owned_server = self._start_server()
        stop_event = threading.Event()
        supervisor = NodeSupervisor(
            registry_path=self.registry_path,
            server_url=self.server_url,
            cmux=CmuxAdapter(),
            send_wakes=self.send_wakes,
        )
        supervisor_thread = threading.Thread(
            target=supervisor.run_forever,
            args=(stop_event,),
            name="dispatch-supervisor",
            daemon=True,
        )
        supervisor_thread.start()
        try:
            print(
                f"Dispatch daemon is running at http://{self.control_host}:"
                f"{self.control_port}; Ctrl-C stops it.",
                flush=True,
            )
            run_web(
                self.registry_path,
                self.server_url,
                self.control_host,
                self.control_port,
            )
        finally:
            stop_event.set()
            supervisor_thread.join(timeout=5)
            if owned_server is not None and owned_server.poll() is None:
                owned_server.terminate()
                try:
                    owned_server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    owned_server.kill()
                    owned_server.wait(timeout=3)
