#!/usr/bin/env python3
"""Mirror Hermes memory + skills into this git repo, then commit and push.

Usage:  python sync.py [--no-push]
Restore on a new machine:  python sync.py --restore
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    return Path(os.environ["LOCALAPPDATA"]) / "hermes" if os.name == "nt" else Path.home() / ".hermes"


def mirror(src: Path, dst: Path, skip: tuple[str, ...] = ()) -> int:
    """Copy src into dst, deleting files in dst that no longer exist in src."""
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    wanted: set[Path] = set()
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(src)
        if any(part.endswith(skip) for part in rel.parts):
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        wanted.add(target.resolve())
        if not target.exists() or target.stat().st_mtime < p.stat().st_mtime or target.stat().st_size != p.stat().st_size:
            shutil.copy2(p, target)
        count += 1
    for p in dst.rglob("*"):
        if p.is_file() and p.resolve() not in wanted:
            p.unlink()
    return count


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, text=True, capture_output=True, check=check)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--restore", action="store_true", help="copy repo files back into the Hermes home")
    args = ap.parse_args()

    home = hermes_home()
    mem_src, skills_src = home / "memories", home / "skills"
    mem_dst, skills_dst = REPO / "memories", REPO / "skills"

    if args.restore:
        if not mem_src.parent.exists():
            print(f"Hermes home not found at {home}", file=sys.stderr)
            return 1
        n1 = mirror(mem_dst, mem_src)
        n2 = mirror(skills_dst, skills_src)
        print(f"restored {n1} memory files and {n2} skill files into {home}")
        return 0

    if not mem_src.exists():
        print(f"No memory directory at {mem_src}", file=sys.stderr)
        return 1

    n1 = mirror(mem_src, mem_dst, skip=(".lock",))
    n2 = mirror(skills_src, skills_dst) if skills_src.exists() else 0
    print(f"mirrored {n1} memory files, {n2} skill files")

    git("add", "-A")
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("nothing changed, no commit")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    git("commit", "-q", "-m", f"sync {stamp} from {socket.gethostname()}")
    print(f"committed {stamp}")

    if args.no_push:
        print("skipped push")
        return 0
    try:
        git("push", "-q", "origin", "HEAD")
        print("pushed")
    except subprocess.CalledProcessError as e:
        print(f"push failed: {e.stderr.strip()}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())