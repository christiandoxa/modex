#!/usr/bin/env python3
"""Ensure Makefile owns every native and Python test exactly once."""

from collections import Counter
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = (ROOT / "Makefile").read_text(encoding="utf-8")
RUNNER = (ROOT / "scripts/ci/run-unittest.py").read_text(encoding="utf-8")


def main() -> int:
    unit_match = re.search(r"(?ms)^unit:.*?\n(?P<body>.*?)(?=^[A-Za-z0-9_.-]+:|\Z)", MAKEFILE)
    if not unit_match:
        print("Makefile unit target is missing", file=sys.stderr)
        return 1
    native_files = sorted((ROOT / "tests").glob("test_*.mojo"))
    native_lines = re.findall(r"tests/[A-Za-z0-9_.-]+\.mojo", unit_match.group("body"))
    native_counts = Counter(native_lines)
    failures = []
    for path in native_files:
        relative = path.relative_to(ROOT).as_posix()
        count = native_counts[relative]
        if count != 1:
            failures.append(f"{relative}: expected one unit owner, found {count}")
        executable = f"$(BUILD_ROOT)/tests/{path.stem}"
        runs = [line.strip() for line in unit_match.group("body").splitlines()
                if line.strip() == executable or line.strip().startswith(executable + " ")]
        if len(runs) != 1:
            failures.append(f"{relative}: expected one unit execution, found {len(runs)}")

    python_tests = sorted((ROOT / "tests").glob("test_*.py"))
    suite_owners = MAKEFILE.count("scripts/ci/run-unittest.py")
    if suite_owners != 1:
        failures.append(f"Python test suite must have one strict-runner owner, found {suite_owners}")
    discovery_owners = RUNNER.count('"test_*.py"')
    if discovery_owners != 1:
        failures.append(f"Python discovery must have one test_*.py owner, found {discovery_owners}")
    if failures:
        print("test census: FAIL", file=sys.stderr)
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"test census: {len(native_files)} native test sources and {len(python_tests)} Python modules each have one suite owner")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
