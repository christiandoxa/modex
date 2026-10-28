#!/usr/bin/env python3
"""Reject modified or untracked checkout inputs without removing ignored outputs."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def dirty_paths(root, environment=None):
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    return result.stdout


def main(root=ROOT, environment=None):
    try:
        dirty = dirty_paths(root, environment)
    except (OSError, RuntimeError) as error:
        print(f"cannot verify the build input checkout: {error}", file=sys.stderr)
        return 1
    if dirty:
        print("build input checkout is modified or has untracked nonignored files:", file=sys.stderr)
        print(dirty, end="" if dirty.endswith("\n") else "\n", file=sys.stderr)
        return 1
    print("build input checkout is clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
