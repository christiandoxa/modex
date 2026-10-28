"""Regression tests for native test ownership in the Make manifests."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CENSUS_PATH = ROOT / "scripts/ci/check-test-census.py"
SPEC = importlib.util.spec_from_file_location("modex_test_census", CENSUS_PATH)
CENSUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CENSUS)
MAKEFILE = (ROOT / "Makefile").read_text(encoding="utf-8")
RUNNER = (ROOT / "scripts/ci/run-unittest.py").read_text(encoding="utf-8")
PROBE = "test_provider_sse_wire"
RUNNER_SPEC = importlib.util.spec_from_file_location(
    "modex_test_runner", ROOT / "scripts/ci/run-unittest.py"
)
RUNNER_DISCOVERY = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER_DISCOVERY)


def mutate_entry(makefile: str, variable: str, operation: str) -> str:
    line = f"\t{PROBE} \\\n"
    if operation == "duplicate":
        replacement = line + line
    elif operation == "omit":
        replacement = ""
    else:
        raise AssertionError(operation)
    start = makefile.index(f"{variable} ?= \\\n")
    first, remainder = makefile[:start], makefile[start:]
    if line not in remainder:
        raise AssertionError(f"{PROBE} entry not found in {variable}")
    return first + remainder.replace(line, replacement, 1)


class NativeTestCensusTests(unittest.TestCase):
    def test_current_make_manifests_cover_the_native_tests(self):
        failures, native_count, python_count = CENSUS.census(MAKEFILE, ROOT, RUNNER)

        self.assertEqual(failures, [])
        self.assertEqual(native_count, len(list((ROOT / "tests").glob("test_*.mojo"))))
        self.assertGreater(python_count, 0)

    def test_current_reference_model_toml_module_is_discovered(self):
        tests = RUNNER_DISCOVERY.discover_tests(
            ["test_super_model_toml_01651.py"], require_each_pattern=True
        )

        self.assertEqual(len(tests), 2)
        self.assertTrue(
            all(test.__class__.__module__ == "test_super_model_toml_01651" for test in tests)
        )

    def test_current_reference_super_probe_module_is_discovered(self):
        tests = RUNNER_DISCOVERY.discover_tests(
            ["test_super_launch_01651.py"], require_each_pattern=True
        )

        self.assertEqual(len(tests), 1)
        self.assertTrue(
            all(test.__class__.__module__ == "test_super_launch_01651" for test in tests)
        )

    def test_duplicate_or_omitted_native_build_is_reported(self):
        for operation, expected in (("duplicate", "found 2"), ("omit", "found 0")):
            with self.subTest(operation=operation):
                makefile = mutate_entry(MAKEFILE, "UNIT_BUILD_PROGRAMS", operation)
                failures, _, _ = CENSUS.census(makefile, ROOT, RUNNER)
                self.assertTrue(any("test_provider_sse_wire.mojo" in error and expected in error
                                    for error in failures), failures)

    def test_duplicate_or_omitted_native_execution_is_reported(self):
        for operation, expected in (("duplicate", "found 2"), ("omit", "found 0")):
            with self.subTest(operation=operation):
                makefile = mutate_entry(MAKEFILE, "UNIT_RUNS", operation)
                failures, _, _ = CENSUS.census(makefile, ROOT, RUNNER)
                self.assertTrue(any("test_provider_sse_wire.mojo" in error and expected in error
                                    for error in failures), failures)


if __name__ == "__main__":
    unittest.main()
