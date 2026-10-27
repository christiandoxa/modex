#!/usr/bin/env python3
"""Run Python tests and reject skipped checks without a declared platform reason."""

import sys
import unittest
from pathlib import Path
import argparse


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
MANDATORY_SKIP_MARKERS = ("bubblewrap", "oracle unavailable", "reference unavailable")
PLATFORM_SKIP_MARKERS = ("IPv6 loopback", "RLIMIT_NOFILE is unavailable")


class StrictResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.invalid_skips = []

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if any(marker in reason for marker in MANDATORY_SKIP_MARKERS):
            self.invalid_skips.append((test.id(), reason, "required check"))
        elif any(marker in reason for marker in PLATFORM_SKIP_MARKERS):
            print(f"PLATFORM-INAPPLICABLE: {test.id()}: {reason}", file=sys.stderr)
        else:
            self.invalid_skips.append((test.id(), reason, "unclassified skip"))


class StrictRunner(unittest.TextTestRunner):
    resultclass = StrictResult


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("patterns", nargs="*", help="optional focused test filename patterns")
    patterns = parser.parse_args().patterns or ["test_*.py"]
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite(
        loader.discover(str(ROOT / "tests"), pattern=pattern, top_level_dir=str(ROOT / "tests"))
        for pattern in patterns
    )
    result = StrictRunner(verbosity=2).run(suite)
    if result.invalid_skips:
        print("CI rejected skipped tests:", file=sys.stderr)
        for test_id, reason, category in result.invalid_skips:
            print(f"- {category}: {test_id}: {reason}", file=sys.stderr)
    return 0 if result.wasSuccessful() and not result.invalid_skips else 1


if __name__ == "__main__":
    raise SystemExit(main())
