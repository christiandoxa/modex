#!/usr/bin/env python3
"""Run Python tests and reject skipped checks without a declared platform reason."""

import argparse
import hashlib
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
MANDATORY_SKIP_MARKERS = ("bubblewrap", "oracle unavailable", "reference unavailable")
PLATFORM_SKIP_MARKERS = ("IPv6 loopback", "RLIMIT_NOFILE is unavailable")


def classify_skip(reason: str) -> str:
    if any(marker in reason for marker in MANDATORY_SKIP_MARKERS):
        return "required check"
    if any(marker in reason for marker in PLATFORM_SKIP_MARKERS):
        return "platform-inapplicable"
    return "unclassified skip"


class StrictResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.invalid_skips = []

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if not isinstance(test, unittest.TestCase):
            self.invalid_skips.append((test.id(), reason, "fixture-level skip"))
            return
        if getattr(type(test), "__unittest_skip__", False):
            self.invalid_skips.append((test.id(), reason, "class-level skip"))
            return
        category = classify_skip(reason)
        if category == "platform-inapplicable":
            print(f"PLATFORM-INAPPLICABLE: {test.id()}: {reason}", file=sys.stderr)
        else:
            self.invalid_skips.append((test.id(), reason, category))


class StrictRunner(unittest.TextTestRunner):
    resultclass = StrictResult


def flatten_suite(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten_suite(test)
        else:
            yield test


def validate_unique_test_ids(tests):
    seen = set()
    duplicates = set()
    for test in tests:
        test_id = test.id()
        if test_id in seen:
            duplicates.add(test_id)
        seen.add(test_id)
    if duplicates:
        raise ValueError(f"duplicate discovered test IDs: {', '.join(sorted(duplicates))}")


def test_module_name(test):
    module_name = getattr(type(test), "__module__", None)
    test_id = test.id()
    if not isinstance(module_name, str) or not module_name:
        raise ValueError(f"discovered test has invalid module identity: {test_id} ({module_name!r})")
    module = sys.modules.get(module_name)
    if (
        not isinstance(module, types.ModuleType)
        or getattr(module, "__name__", None) != module_name
        or not test_id.startswith(module_name + ".")
    ):
        raise ValueError(f"discovered test has invalid module identity: {test_id} ({module_name!r})")
    return module_name


def discover_tests(patterns, loader=None, require_each_pattern=False, start_dir=None):
    loader = loader or unittest.TestLoader()
    start_dir = Path(start_dir) if start_dir is not None else ROOT / "tests"
    tests = []
    for pattern in patterns:
        errors_before = len(getattr(loader, "errors", ()))
        suite = loader.discover(
            str(start_dir), pattern=pattern, top_level_dir=str(start_dir)
        )
        errors = getattr(loader, "errors", ())
        if errors[errors_before:]:
            raise ValueError(
                f"test discovery import error for pattern {pattern!r}: "
                + "; ".join(errors[errors_before:])
            )
        pattern_tests = list(flatten_suite(suite))
        if require_each_pattern and not pattern_tests:
            raise ValueError(f"requested pattern {pattern!r} discovered no tests")
        for test in pattern_tests:
            test_module_name(test)
        tests.extend(pattern_tests)
    if not tests:
        raise ValueError("test discovery found no tests")
    validate_unique_test_ids(tests)
    return tests


def shard_for_module(module_name: str, shard_count: int) -> int:
    if shard_count < 1:
        raise ValueError("shard count must be positive")
    digest = hashlib.sha256(module_name.encode("utf-8")).digest()
    return int.from_bytes(digest, "big") % shard_count


def validate_partition(test_ids, shards):
    expected = set(test_ids)
    if len(expected) != len(test_ids):
        raise ValueError("duplicate discovered test IDs")

    ownership = {}
    for shard in shards:
        for test in shard:
            test_id = test.id()
            ownership[test_id] = ownership.get(test_id, 0) + 1

    missing = sorted(expected - ownership.keys())
    duplicated = sorted(test_id for test_id, count in ownership.items() if count > 1)
    unexpected = sorted(ownership.keys() - expected)
    if missing or duplicated or unexpected:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if duplicated:
            details.append(f"multiple owners: {', '.join(duplicated)}")
        if unexpected:
            details.append(f"unexpected: {', '.join(unexpected)}")
        raise ValueError("shard ownership mismatch (" + "; ".join(details) + ")")


def partition_tests(tests, shard_count: int):
    if shard_count < 1:
        raise ValueError("shard count must be positive")
    if not tests:
        raise ValueError("test discovery found no tests")
    if shard_count > len(tests):
        raise ValueError(
            f"shard count {shard_count} exceeds discovered test count {len(tests)}"
        )
    validate_unique_test_ids(tests)
    test_ids = [test.id() for test in tests]
    module_names = [test_module_name(test) for test in tests]
    shards = [[] for _ in range(shard_count)]
    for test, module_name in zip(tests, module_names):
        shards[shard_for_module(module_name, shard_count)].append(test)
    validate_partition(test_ids, shards)
    return shards


def validate_shard_options(shard_index, shard_count):
    if shard_index is None and shard_count is None:
        return
    if shard_index is None or shard_count is None:
        raise ValueError("--shard-index and --shard-count must be provided together")
    if shard_count < 1:
        raise ValueError("--shard-count must be positive")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("--shard-index must be between 0 and --shard-count - 1")


def select_shard(tests, shard_index: int, shard_count: int):
    validate_shard_options(shard_index, shard_count)
    selected = partition_tests(tests, shard_count)[shard_index]
    if not selected:
        raise ValueError(f"selected shard {shard_index} owns no discovered tests")
    return selected


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("patterns", nargs="*", help="optional focused test filename patterns")
    parser.add_argument("--shard-index", type=int, help="zero-based index of this test shard")
    parser.add_argument("--shard-count", type=int, help="total number of test shards")
    args = parser.parse_args(argv)
    try:
        validate_shard_options(args.shard_index, args.shard_count)
    except ValueError as error:
        parser.error(str(error))
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    patterns = args.patterns or ["test_*.py"]
    try:
        tests = discover_tests(patterns, require_each_pattern=bool(args.patterns))
        if args.shard_count is not None:
            tests = select_shard(tests, args.shard_index, args.shard_count)
    except ValueError as error:
        print(f"CI rejected test discovery or sharding: {error}", file=sys.stderr)
        return 1

    suite = unittest.TestSuite(tests)
    result = StrictRunner(verbosity=2).run(suite)
    if result.invalid_skips:
        print("CI rejected skipped tests:", file=sys.stderr)
        for test_id, reason, category in result.invalid_skips:
            print(f"- {category}: {test_id}: {reason}", file=sys.stderr)
    return 0 if result.wasSuccessful() and not result.invalid_skips else 1


if __name__ == "__main__":
    raise SystemExit(main())
