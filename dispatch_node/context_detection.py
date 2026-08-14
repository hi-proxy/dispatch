from __future__ import annotations

import re
from typing import Any, Iterable


COMMIT = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{7,40})(?![0-9a-fA-F])")


def detect_contexts(
    body: str, git_contexts: Iterable[dict[str, Any] | None],
    *, verified_commits: Iterable[str] = (),
) -> list[dict[str, Any]]:
    contexts = [context for context in git_contexts if context]
    known_branches = {
        str(branch)
        for context in contexts
        for branch in context.get("branches", [])
        if branch
    }
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    known_commits = {value.lower() for value in verified_commits}

    for branch in sorted(known_branches, key=len, reverse=True):
        if _contains_verified_branch(body, branch):
            _append(found, seen, "branch", branch, verified=True)
    for match in COMMIT.finditer(body):
        value = match.group(1).lower()
        if value in known_commits:
            _append(found, seen, "commit", value, verified=True)
    return found


def commit_candidates(body: str) -> set[str]:
    return {match.group(1).lower() for match in COMMIT.finditer(body)}


def _contains_token(body: str, value: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9_./-]){re.escape(value)}(?![A-Za-z0-9_./-])"
    return re.search(pattern, body) is not None


def _contains_verified_branch(body: str, branch: str) -> bool:
    if "/" in branch:
        return _contains_token(body, branch)
    explicit = rf"(?:branch\s*[:/]\s*|브랜치\s*[:：]?\s*)`?{re.escape(branch)}`?"
    return re.search(explicit, body, flags=re.IGNORECASE) is not None or (
        f"`{branch}`" in body
    )


def _append(
    found: list[dict[str, Any]], seen: set[tuple[str, str]],
    kind: str, value: str, *, verified: bool,
) -> None:
    key = (kind, value)
    if key not in seen:
        seen.add(key)
        found.append({"kind": kind, "value": value, "verified": verified})
