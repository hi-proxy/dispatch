from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

from .server_url import validate_server_url


def install_agent_cli(
    *,
    registry_path: Path,
    server_url: str,
    executable_path: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, str]:
    server_url = validate_server_url(server_url)
    executable_path = executable_path or Path.home() / ".local" / "bin" / "dispatch"
    config_path = config_path or Path.home() / ".config" / "dispatch" / "agent.json"
    executable_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper = (
        "#!/bin/sh\n"
        f"exec {json.dumps(sys.executable)} -m dispatch_node.agent_cli \"$@\"\n"
    )
    executable_path.write_text(wrapper)
    executable_path.chmod(
        executable_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    config_path.write_text(
        json.dumps(
            {
                "registry": str(registry_path.resolve()),
                "server": server_url,
            },
            indent=2,
        )
        + "\n"
    )
    os.chmod(config_path, 0o600)
    return {"executable": str(executable_path), "config": str(config_path)}
