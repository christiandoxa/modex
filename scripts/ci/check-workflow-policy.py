#!/usr/bin/env python3
"""Enforce pinned actions and the repository's narrow read-only permission form."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
ACTION = re.compile(
    r"^\s*(?:-\s*)?['\"]?uses['\"]?\s*:\s*(?P<block>[^\s,}\]#]+)"
    r"|[\[{,]\s*['\"]?uses['\"]?\s*:\s*(?P<flow>[^\s,}\]#]+)"
)
ACTION_KEY = re.compile(r"^\s*(?:-\s*)?uses(?=\s|:|$)|[\[{,]\s*uses(?=\s|:|$)")
PINNED = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[^@\s]+)?@[0-9a-f]{40}$")
PERMISSION_KEY = re.compile(r"^\s*['\"]?permissions['\"]?\s*:|[,{]\s*['\"]?permissions['\"]?\s*:")
RUN_KEY = re.compile(r"^\s*(?:-\s*)?['\"]?run['\"]?\s*:")
BLOCK_SCALAR = re.compile(r"^\s*(?:-\s*)?[^#{}:\n][^:\n]*:\s*[|>](?:[+-][1-9]?|[1-9][+-]?)?\s*(?:#.*)?$")
UNSUPPORTED_YAML_KEY = re.compile(
    r"(?:^|[\s,{])(?:<<\s*:|[&*][^\s,\[\]{}]+|\?(?=\s))"
    r"|(?:^|[{,])\s*(?:-\s*)?['\"][^'\"]+['\"]\s*:"
    r"|(?:^|[\s,{])(?:!![^\s,{]+|!<[^>]+>|![^\s,{]+)\s+['\"]?[^:\s'\"]+['\"]?\s*:"
)


def workflow_yaml_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Return config lines, excluding comments and run/block-scalar text."""
    config_lines = []
    scalar_indent = None
    for line_number, line in enumerate(lines, 1):
        indent = len(line) - len(line.lstrip(" "))
        if scalar_indent is not None:
            if not line.strip() or indent > scalar_indent:
                continue
            scalar_indent = None
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if RUN_KEY.match(line):
            if BLOCK_SCALAR.fullmatch(line):
                scalar_indent = indent
            continue
        config_lines.append((line_number, line))
        if BLOCK_SCALAR.fullmatch(line):
            scalar_indent = indent
    return config_lines


def has_read_only_permissions(lines: list[str]) -> bool:
    """Accept only the canonical workflow-level permissions mapping."""
    config_lines = [line for _, line in workflow_yaml_lines(lines)]
    if any(UNSUPPORTED_YAML_KEY.search(line) for line in config_lines):
        return False
    if [line for line in config_lines if PERMISSION_KEY.search(line)] != ["permissions:"]:
        return False
    index = lines.index("permissions:")
    if index + 1 >= len(lines) or lines[index + 1] != "  contents: read":
        return False
    for line in lines[index + 2:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        return not line.startswith((" ", "\t"))
    return True


def main() -> int:
    files = sorted(WORKFLOWS.glob("*.yml"))
    if not files:
        print("no GitHub Actions workflows found", file=sys.stderr)
        return 1
    failures = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        if not has_read_only_permissions(lines):
            failures.append(f"{path.name}: permissions must use the single canonical read-only block")
        if "secrets." in text:
            failures.append(f"{path.name}: workflow must not expose secrets")
        for line_number, line in workflow_yaml_lines(lines):
            matches = list(ACTION.finditer(line))
            for match in matches:
                reference = match.group("block") or match.group("flow")
                if reference.startswith("./"):
                    continue
                if not PINNED.fullmatch(reference):
                    failures.append(f"{path.name}:{line_number}: action must use a full immutable commit SHA: {reference}")
            if not matches and ACTION_KEY.search(line):
                failures.append(f"{path.name}:{line_number}: action uses key has unsupported YAML syntax")
    if failures:
        print("workflow policy: FAIL", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"workflow policy: PASS ({len(files)} workflows; canonical permissions and checked action references)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
