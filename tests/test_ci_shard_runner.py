"""Regression tests for deterministic ownership in the Python CI runner."""

import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/ci/run-unittest.py"
SPEC = importlib.util.spec_from_file_location("modex_unittest_runner", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class IdentifiedTest:
    def __init__(self, test_id):
        self.test_id = test_id

    def id(self):
        return self.test_id

    def shortDescription(self):
        return None


def identified_test(module_name, test_id):
    if module_name not in sys.modules:
        module = types.ModuleType(module_name)
        module.__file__ = str(ROOT / (module_name.replace(".", "/") + ".py"))
        sys.modules[module_name] = module
    class_name = "Identified_" + module_name.replace(".", "_")
    test_type = type(class_name, (IdentifiedTest,), {"__module__": module_name})
    return test_type(test_id)


class FakeLoader:
    def __init__(self, suites):
        self.suites = suites

    def discover(self, start_dir, pattern, top_level_dir):
        return self.suites[pattern]


class TestStream(io.StringIO):
    def writeln(self, line=""):
        self.write(line + "\n")


class ShardPartitionTests(unittest.TestCase):
    def test_hash_assignment_is_stable(self):
        self.assertEqual(
            RUNNER.shard_for_module("tests.synthetic", 17), 6
        )

    def test_partition_owns_each_discovered_test_once(self):
        modules_by_shard = {}
        for index in range(500):
            module_name = f"synthetic_test_module_{index}"
            shard_index = RUNNER.shard_for_module(module_name, 5)
            modules_by_shard.setdefault(shard_index, module_name)
            if len(modules_by_shard) == 5:
                break
        modules = [modules_by_shard[index] for index in range(5)]
        tests = [
            identified_test(module, f"{module}.TestCase.test_{index:03}")
            for module in modules
            for index in range(16)
        ]
        shards = RUNNER.partition_tests(tests, 5)

        RUNNER.validate_partition([test.id() for test in tests], shards)
        self.assertEqual(sum(map(len, shards)), len(tests))
        self.assertTrue(all(shards))
        for shard_index, module in enumerate(modules):
            self.assertTrue(all(type(test).__module__ == module for test in shards[shard_index]))

    def test_module_assignment_is_stable_and_keeps_discovered_order(self):
        modules = ("synthetic_order_alpha", "synthetic_order_beta")
        tests = [
            identified_test(module, f"{module}.TestCase.test_{index:03}")
            for index in range(20)
            for module in modules
        ]
        first = RUNNER.partition_tests(tests, 4)
        reversed_tests = list(reversed(tests))
        second = RUNNER.partition_tests(reversed_tests, 4)

        def owners(shards):
            return {
                test.id(): shard_index
                for shard_index, shard in enumerate(shards)
                for test in shard
            }

        self.assertEqual(owners(first), owners(second))
        for source, shards in ((tests, first), (reversed_tests, second)):
            for module in modules:
                expected_order = [test.id() for test in source if type(test).__module__ == module]
                shard_index = owners(shards)[expected_order[0]]
                actual_order = [
                    test.id() for test in shards[shard_index]
                    if type(test).__module__ == module
                ]
                self.assertEqual(actual_order, expected_order)

    def test_overlapping_patterns_reject_duplicate_ids(self):
        test = identified_test("synthetic_duplicate", "synthetic_duplicate.TestCase.test_same")
        loader = FakeLoader({"test_*.py": [test], "test_synthetic*.py": [
            identified_test("synthetic_duplicate", test.id())
        ]})

        with self.assertRaisesRegex(ValueError, "duplicate discovered test IDs"):
            RUNNER.discover_tests(["test_*.py", "test_synthetic*.py"], loader)

    def test_missing_and_duplicate_partition_ownership_is_rejected(self):
        first = IdentifiedTest("tests.synthetic.TestCase.test_first")
        second = IdentifiedTest("tests.synthetic.TestCase.test_second")

        with self.assertRaisesRegex(ValueError, "missing: .*test_second"):
            RUNNER.validate_partition([first.id(), second.id()], [[first]])
        with self.assertRaisesRegex(ValueError, "multiple owners: .*test_first"):
            RUNNER.validate_partition([first.id()], [[first], [IdentifiedTest(first.id())]])

    def test_empty_selected_shard_is_rejected(self):
        module = "synthetic_empty_shard"
        tests = [identified_test(module, f"{module}.TestCase.test_{name}")
                 for name in ("single", "second")]
        owning_shard = RUNNER.shard_for_module(type(tests[0]).__module__, 2)
        empty_shard = 1 - owning_shard

        with self.assertRaisesRegex(ValueError, "owns no discovered tests"):
            RUNNER.select_shard(tests, empty_shard, 2)

    def test_shard_count_above_test_count_fails_before_partition_allocation(self):
        with self.assertRaisesRegex(ValueError, "exceeds discovered test count"):
            RUNNER.partition_tests([IdentifiedTest("tests.synthetic.test_one")], 10**9)

    def test_empty_discovery_and_empty_requested_patterns_fail(self):
        empty_loader = FakeLoader({"test_missing.py": []})
        with self.assertRaisesRegex(ValueError, "test discovery found no tests"):
            RUNNER.discover_tests(["test_missing.py"], empty_loader)

        loader = FakeLoader({"test_present.py": [identified_test(
                                 "synthetic_present", "synthetic_present.test_one"
                             )],
                             "test_missing.py": []})
        with self.assertRaisesRegex(ValueError, "requested pattern 'test_missing.py' discovered no tests"):
            RUNNER.discover_tests(
                ["test_present.py", "test_missing.py"], loader, require_each_pattern=True
            )

    def test_loader_import_errors_fail_before_shard_selection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "test_broken_shard_import.py").write_text(
                "import modex_missing_shard_runner_dependency_572a\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "test discovery import error"):
                RUNNER.discover_tests(
                    ["test_broken_shard_import.py"], start_dir=temp_dir
                )

    def test_module_identity_must_match_imported_test_class_module(self):
        unloaded_type = type("UnloadedModuleTest", (IdentifiedTest,), {
            "__module__": "unloaded_synthetic_test_module",
        })
        with self.assertRaisesRegex(ValueError, "invalid module identity"):
            RUNNER.test_module_name(
                unloaded_type("unloaded_synthetic_test_module.TestCase.test_fake")
            )

        matching_module = type("MatchingModuleTest", (IdentifiedTest,), {
            "__module__": __name__,
        })("synthetic_fake_module.TestCase.test_fake")
        with self.assertRaisesRegex(ValueError, "invalid module identity"):
            RUNNER.test_module_name(matching_module)

        valid_module = identified_test(
            "synthetic_valid_identity", "synthetic_valid_identity.TestCase.test_valid"
        )
        self.assertEqual(RUNNER.test_module_name(valid_module), "synthetic_valid_identity")


class ShardArgumentTests(unittest.TestCase):
    def test_sharding_is_optional_and_valid_pair_is_accepted(self):
        unsharded = RUNNER.parse_args([])
        sharded = RUNNER.parse_args(["--shard-index", "1", "--shard-count", "3"])

        self.assertIsNone(unsharded.shard_index)
        self.assertIsNone(unsharded.shard_count)
        self.assertEqual((sharded.shard_index, sharded.shard_count), (1, 3))

    def test_malformed_shard_arguments_fail_cli_parsing(self):
        invalid_args = (
            ["--shard-index", "0"],
            ["--shard-count", "2"],
            ["--shard-index", "-1", "--shard-count", "2"],
            ["--shard-index", "0", "--shard-count", "0"],
            ["--shard-index", "2", "--shard-count", "2"],
            ["--shard-index", "first", "--shard-count", "2"],
        )
        for args in invalid_args:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    RUNNER.parse_args(args)
            self.assertEqual(error.exception.code, 2)


class StrictSkipTests(unittest.TestCase):
    def run_strict(self, suite):
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            result = RUNNER.StrictRunner(stream=TestStream(), verbosity=0).run(suite)
        return result, stderr.getvalue()

    def test_required_and_unclassified_skips_fail_but_platform_skips_are_reported(self):
        result = RUNNER.StrictResult(TestStream(), True, 2)
        class SkipMarkerCases(unittest.TestCase):
            def test_required(self):
                pass

            def test_unclassified(self):
                pass

            def test_platform(self):
                pass

        cases = [
            SkipMarkerCases("test_required"),
            SkipMarkerCases("test_unclassified"),
            SkipMarkerCases("test_platform"),
        ]
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            result.addSkip(cases[0], "bubblewrap unavailable")
            result.addSkip(cases[1], "temporary skip")
            result.addSkip(cases[2], "IPv6 loopback disabled")

        self.assertEqual(
            result.invalid_skips,
            [
                (cases[0].id(), "bubblewrap unavailable", "required check"),
                (cases[1].id(), "temporary skip", "unclassified skip"),
            ],
        )
        self.assertIn(f"PLATFORM-INAPPLICABLE: {cases[2].id()}", stderr.getvalue())

    def test_platform_marked_set_up_class_skip_fails_closed(self):
        class FixtureSkippedTests(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise unittest.SkipTest("IPv6 loopback unavailable")

            def test_first(self):
                self.fail("fixture skip should prevent test execution")

            def test_second(self):
                self.fail("fixture skip should prevent test execution")

        result, stderr = self.run_strict(unittest.defaultTestLoader.loadTestsFromTestCase(
            FixtureSkippedTests
        ))

        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(len(result.invalid_skips), 1)
        test_id, reason, category = result.invalid_skips[0]
        self.assertTrue(test_id.startswith("setUpClass ("), test_id)
        self.assertEqual((reason, category), ("IPv6 loopback unavailable", "fixture-level skip"))
        self.assertNotIn("PLATFORM-INAPPLICABLE", stderr)

    def test_platform_marked_whole_class_skip_fails_closed(self):
        @unittest.skip("IPv6 loopback unavailable")
        class WholeClassSkippedTests(unittest.TestCase):
            def test_first(self):
                self.fail("class skip should prevent test execution")

            def test_second(self):
                self.fail("class skip should prevent test execution")

        result, stderr = self.run_strict(unittest.defaultTestLoader.loadTestsFromTestCase(
            WholeClassSkippedTests
        ))

        self.assertEqual(len(result.skipped), 2)
        self.assertEqual(len(result.invalid_skips), 2)
        self.assertTrue(all(category == "class-level skip"
                            for _, _, category in result.invalid_skips))
        self.assertNotIn("PLATFORM-INAPPLICABLE", stderr)

    def test_platform_marked_method_skip_remains_allowed(self):
        class MethodSkippedTests(unittest.TestCase):
            @unittest.skip("IPv6 loopback unavailable")
            def test_platform_method(self):
                self.fail("method skip should prevent test execution")

        result, stderr = self.run_strict(unittest.defaultTestLoader.loadTestsFromTestCase(
            MethodSkippedTests
        ))

        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(result.invalid_skips, [])
        self.assertIn("PLATFORM-INAPPLICABLE:", stderr)


if __name__ == "__main__":
    unittest.main()
