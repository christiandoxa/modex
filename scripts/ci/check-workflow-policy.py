#!/usr/bin/env python3
"""Enforce immutable actions and read-only workflows without a YAML dependency."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
ACTION = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)\s*(?:#.*)?$")
PINNED = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[^@\s]+)?@[0-9a-f]{40}$")


def main() -> int:
    files = sorted(WORKFLOWS.glob("*.yml"))
    if not files:
        print("no GitHub Actions workflows found", file=sys.stderr)
        return 1
    failures = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not any(line == "permissions:" for line in lines):
            failures.append(f"{path.name}: missing top-level permissions")
        if not re.search(r"(?m)^permissions:\n\s+contents: read\s*$", text):
            failures.append(f"{path.name}: top-level contents permission must be read-only")
        if re.search(r"(?m)^\s*[A-Za-z_-]+:\s*write\s*$", text):
            failures.append(f"{path.name}: write permission is not allowed")
        if "secrets." in text:
            failures.append(f"{path.name}: workflow must not expose secrets")
        for line_number, line in enumerate(lines, 1):
            match = ACTION.match(line)
            if not match:
                continue
            reference = match.group(1)
            if reference.startswith("./"):
                continue
            if not PINNED.fullmatch(reference):
                failures.append(f"{path.name}:{line_number}: action must use a full immutable commit SHA: {reference}")
    if failures:
        print("workflow policy: FAIL", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"workflow policy: PASS ({len(files)} read-only workflows; every external action pinned to a commit SHA)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
