#!/usr/bin/env python3
"""Ensure Makefile owns every native and Python test exactly once."""

from collections import Counter
from pathlib import Path
import re
import shlex
import sys


ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
RUNNER = ROOT / "scripts/ci/run-unittest.py"
MANIFEST_NAME = re.compile(r"[A-Za-z0-9_-]+")
RUN_NAME = re.compile(r"[A-Za-z0-9_-]+(?::[A-Za-z0-9_-]+)?")


def parse_manifest(makefile: str, name: str) -> tuple[list[str], list[str]]:
    """Return one Make variable's tokens and any syntax/ownership errors."""
    definitions = []
    for index, line in enumerate(makefile.splitlines()):
        match = re.match(rf"^{re.escape(name)}\s*(?:\?=|:=|=)\s*(.*)$", line)
        if match:
            definitions.append((index, match.group(1)))

    errors = []
    if len(definitions) != 1:
        errors.append(f"{name}: expected one Makefile definition, found {len(definitions)}")
        return [], errors

    lines = makefile.splitlines()
    index, value = definitions[0]
    while True:
        stripped = value.rstrip()
        if not stripped.endswith("\\"):
            break
        if index + 1 >= len(lines):
            errors.append(f"{name}: continuation reaches end of Makefile")
            break
        index += 1
        value = stripped[:-1] + " " + lines[index].strip()

    try:
        entries = shlex.split(value, comments=True, posix=True)
    except ValueError as error:
        errors.append(f"{name}: cannot parse manifest: {error}")
        return [], errors

    pattern = MANIFEST_NAME if name == "UNIT_BUILD_PROGRAMS" else RUN_NAME
    invalid = [entry for entry in entries if not pattern.fullmatch(entry)]
    if invalid:
        errors.append(f"{name}: invalid manifest entries: {', '.join(invalid)}")
    return entries, errors


def census(makefile: str, root: Path, runner: str) -> tuple[list[str], int, int]:
    failures = []
    build_entries, build_errors = parse_manifest(makefile, "UNIT_BUILD_PROGRAMS")
    run_entries, run_errors = parse_manifest(makefile, "UNIT_RUNS")
    failures.extend(build_errors)
    failures.extend(run_errors)

    build_counts = Counter(build_entries)
    for target, count in sorted(build_counts.items()):
        if count != 1:
            failures.append(f"UNIT_BUILD_PROGRAMS {target}: expected one build, found {count}")
        source = root / "tests" / f"{target}.mojo"
        if not source.is_file():
            failures.append(f"UNIT_BUILD_PROGRAMS {target}: missing source {source.relative_to(root)}")

    run_targets = [entry.split(":", 1)[0] for entry in run_entries]
    run_counts = Counter(run_targets)
    for target, count in sorted(run_counts.items()):
        if count != 1:
            failures.append(f"UNIT_RUNS {target}: expected one execution, found {count}")
        if target not in build_counts:
            failures.append(f"UNIT_RUNS {target}: executable is not built by UNIT_BUILD_PROGRAMS")

    native_files = sorted((root / "tests").glob("test_*.mojo"))
    for path in native_files:
        relative = path.relative_to(root).as_posix()
        build_count = build_counts[path.stem]
        if build_count != 1:
            failures.append(f"{relative}: expected one unit build, found {build_count}")
        run_count = run_counts[path.stem]
        if run_count != 1:
            failures.append(f"{relative}: expected one unit execution, found {run_count}")

    python_tests = sorted((root / "tests").glob("test_*.py"))
    suite_owners = makefile.count("scripts/ci/run-unittest.py")
    if suite_owners != 1:
        failures.append(f"Python test suite must have one strict-runner owner, found {suite_owners}")
    discovery_owners = runner.count('"test_*.py"')
    if discovery_owners != 1:
        failures.append(f"Python discovery must have one test_*.py owner, found {discovery_owners}")
    return failures, len(native_files), len(python_tests)


def main() -> int:
    failures, native_count, python_count = census(
        MAKEFILE.read_text(encoding="utf-8"),
        ROOT,
        RUNNER.read_text(encoding="utf-8"),
    )
    if failures:
        print("test census: FAIL", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"test census: {native_count} native test sources and {python_count} Python modules each have one suite owner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
