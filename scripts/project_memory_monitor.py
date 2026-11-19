#!/usr/bin/env python3
"""Quiet-gate for project memory.

Prints a line for each tracked project whose repo has new commits that are at
least THRESHOLD minutes old and not yet reflected in its project file. Prints
nothing otherwise, so the scheduler stays silent and no model is called.

Deterministic by design: no timestamps, no clock values in the output, so the
same state always produces byte-identical stdout and never re-wakes the agent.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

THRESHOLD_MINUTES = int(os.environ.get("PROJECT_MEMORY_QUIET_MINUTES", "60"))


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "hermes"
    return Path.home() / ".hermes"


MEMORY_REPO = Path(os.environ.get("HERMES_MEMORY_REPO") or (Path.home() / "hermes-memory"))
REGISTRY = MEMORY_REPO / "projects" / "repos.json"


def git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            text=True,
            capture_output=True,
            timeout=30,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def resolve_path(cfg: dict) -> Path | None:
    """Per-host override wins, so one registry can serve several machines."""
    overrides = cfg.get("paths") or {}
    chosen = str(overrides.get(socket.gethostname()) or cfg.get("path") or "").strip()
    return Path(chosen).expanduser() if chosen else None


def main() -> int:
    if not REGISTRY.exists():
        return 0
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"project-memory registry unreadable: {exc}")
        return 0

    lines: list[str] = []
    for slug, cfg in sorted(data.get("projects", {}).items()):
        path = resolve_path(cfg)
        if path is None:
            continue
        if not (path / ".git").exists():
            continue
        # refresh remote-tracking refs so a push from anywhere counts as activity
        git(path, "fetch", "--quiet", "--prune")
        # newest of local HEAD and upstream: covers both an unpushed local commit and a
        # push made elsewhere that has not been pulled here yet
        candidates = [sha for sha in (
            git(path, "rev-parse", "--short", "HEAD"),
            git(path, "rev-parse", "--short", "@{u}"),
        ) if sha]
        if not candidates:
            continue
        head = max(candidates, key=lambda sha: int(git(path, "log", "-1", "--format=%ct", sha) or 0))
        recorded = str(cfg.get("recorded_sha", "")).strip()
        if recorded and (head.startswith(recorded) or recorded.startswith(head)):
            continue
        age = git(path, "log", "-1", "--format=%ct", head) or git(path, "log", "-1", "--format=%ct")
        if not age or not age.isdigit():
            continue
        import time

        quiet_minutes = int((time.time() - int(age)) / 60)
        if quiet_minutes < THRESHOLD_MINUTES:
            continue
        subject = git(path, "log", "-1", "--format=%s", head)
        count = git(path, "rev-list", "--count", f"{recorded}..{head}") if recorded else ""
        changed = git(path, "diff", "--name-only", f"{recorded}..{head}") if recorded else ""
        files = len([f for f in changed.splitlines() if f.strip()])
        detail = f"{count or '?'} commit(s), {files} file(s)" if recorded else "no baseline recorded"
        lines.append(f"{slug} ({cfg.get('name', slug)}): HEAD {head}, {detail} | last: {subject}")

    if lines:
        print(f"Project repos with unrecorded work, quiet {THRESHOLD_MINUTES}m+:")
        print("\n".join(lines))
        print(f"registry: {REGISTRY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())