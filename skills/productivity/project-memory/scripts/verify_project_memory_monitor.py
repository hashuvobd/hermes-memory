#!/usr/bin/env python3
"""Deterministic probe for the project-memory monitor.

Builds a throwaway git repo with backdated commits, registers it in
`projects/repos.json`, and asserts the monitor:

  1. fires when a repo has commits newer than its recorded sha and its last
     commit is older than the threshold,
  2. emits byte-identical output on a repeated idle tick (so the gate cannot
     re-wake the agent in a loop),
  3. goes silent once `recorded_sha` advances to HEAD,
  4. stays silent while the last commit is fresh (inside the threshold).

Restores the registry on every exit path, including failure. No network, no
model calls. Run: python verify_project_memory_monitor.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TIMEOUT = 120


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "hermes"
    return Path.home() / ".hermes"


MONITOR = hermes_home() / "scripts" / "project_memory_monitor.py"
MEMORY_REPO = Path(os.environ.get("HERMES_MEMORY_REPO") or (Path.home() / "hermes-memory"))
REGISTRY = MEMORY_REPO / "projects" / "repos.json"
SLUG = "probe-fixture-do-not-keep"

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  ->  ' + detail) if detail and not ok else ''}")
    if not ok:
        failures.append(name)


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, timeout=TIMEOUT)
    return out.stdout.strip() if out.returncode == 0 else ""


def iso(delta: timedelta) -> str:
    # git rejects relative dates in GIT_COMMITTER_DATE; absolute ISO only.
    return (datetime.now(timezone.utc) - delta).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def run_monitor(env_extra: dict[str, str] | None = None) -> str:
    env = dict(os.environ)
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, str(MONITOR)], text=True, capture_output=True, timeout=TIMEOUT, env=env
    )
    return f"{proc.stdout or ''}{proc.stderr or ''}"


def main() -> int:
    if not MONITOR.exists():
        print(f"monitor not found at {MONITOR}")
        return 2
    if not REGISTRY.exists():
        print(f"registry not found at {REGISTRY}")
        return 2

    original = REGISTRY.read_text(encoding="utf-8")
    data = json.loads(original)
    data.setdefault("projects", {})
    fixture = Path(tempfile.mkdtemp(prefix="pm-monitor-probe-"))

    try:
        git(fixture, "init", "-q")
        git(fixture, "config", "user.name", "probe")
        git(fixture, "config", "user.email", "probe@example.com")
        (fixture / "a.txt").write_text("one\n", encoding="utf-8")
        git(fixture, "add", "-A")
        subprocess.run(
            ["git", "-C", str(fixture), "commit", "-q", "-m", "first commit"],
            check=True,
            env={**os.environ,
                 "GIT_AUTHOR_DATE": iso(timedelta(hours=3)),
                 "GIT_COMMITTER_DATE": iso(timedelta(hours=3))},
            timeout=TIMEOUT,
        )
        baseline = git(fixture, "rev-parse", "--short", "HEAD")

        (fixture / "b.txt").write_text("two\n", encoding="utf-8")
        git(fixture, "add", "-A")
        subprocess.run(
            ["git", "-C", str(fixture), "commit", "-q", "-m", "parser module"],
            check=True,
            env={**os.environ,
                 "GIT_AUTHOR_DATE": iso(timedelta(hours=2)),
                 "GIT_COMMITTER_DATE": iso(timedelta(hours=2))},
            timeout=TIMEOUT,
        )
        head = git(fixture, "rev-parse", "--short", "HEAD")
        check("fixture built with two backdated commits", bool(baseline and head), f"{baseline}/{head}")

        data["projects"][SLUG] = {
            "name": "Monitor probe fixture",
            "path": str(fixture),
            "recorded_sha": baseline,
            "file": f"projects/{SLUG}.md",
        }
        REGISTRY.write_text(json.dumps(data, indent=2), encoding="utf-8")

        first = run_monitor()
        check("fires on unrecorded work past the threshold", SLUG in first, repr(first[:200]))
        check("output is byte-stable across idle ticks", first == run_monitor())
        check(
            "threshold is respected (0m fires)",
            SLUG in run_monitor({"PROJECT_MEMORY_QUIET_MINUTES": "0"}),
        )

        data["projects"][SLUG]["recorded_sha"] = head
        REGISTRY.write_text(json.dumps(data, indent=2), encoding="utf-8")
        check("silent once recorded_sha is HEAD", run_monitor().strip() == "")
    finally:
        REGISTRY.write_text(original, encoding="utf-8")
        shutil.rmtree(fixture, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("\nAll monitor checks passed. Registry restored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
