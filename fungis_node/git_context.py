from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any


def inspect_git_context(cwd: str | None) -> dict[str, Any] | None:
    """Return verified Git metadata for a session cwd, or None outside a worktree."""
    if not cwd:
        return None
    directory = Path(cwd).expanduser()
    if not directory.is_dir():
        return None

    root = _git(directory, "rev-parse", "--show-toplevel")
    if root is None:
        return None
    branch = _git(directory, "branch", "--show-current") or None
    head = _git(directory, "rev-parse", "--short=12", "HEAD") or None
    common_dir = _git(directory, "rev-parse", "--path-format=absolute", "--git-common-dir")
    status = _git(directory, "status", "--porcelain", "--untracked-files=normal")
    branch_output = _git(directory, "branch", "--format=%(refname:short)") or ""
    branches = [value for value in branch_output.splitlines() if value][:200]
    return {
        "repo_root": root,
        "worktree": root,
        "common_dir": common_dir,
        "branch": branch,
        "branches": branches,
        "head": head,
        "dirty": bool(status),
        "verified": True,
    }


@lru_cache(maxsize=2048)
def is_verified_commit(
    repo_root: str, repository_head: str | None, candidate: str
) -> bool:
    """Verify a commit prefix in one project repository.

    repository_head participates in the cache key so normal repository progress
    invalidates previous negative results without polling Git for every snapshot.
    """
    del repository_head
    return _git(
        Path(repo_root), "rev-parse", "--verify", "--quiet",
        f"{candidate}^{{commit}}",
    ) is not None


def _git(directory: Path, *args: str) -> str | None:
    try:
        process = subprocess.run(
            ["git", "-C", str(directory), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if process.returncode != 0:
        return None
    return process.stdout.strip()
