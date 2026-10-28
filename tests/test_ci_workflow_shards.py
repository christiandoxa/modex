"""Run helper tests independently and keep artifact verification success-gated."""

import importlib.util
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUN_FAST = (ROOT / "scripts/ci/run-fast.sh").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/ci-fast.yml").read_text(encoding="utf-8")
RUNNER_PATH = ROOT / "scripts/ci/run-unittest.py"
SPEC = importlib.util.spec_from_file_location("modex_ci_workflow_shard_runner", RUNNER_PATH)
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
HELPER_MODULES = (
    "test_ci_artifact_manifest.py",
    "test_ci_shard_runner.py",
    "test_ci_test_census.py",
    "test_ci_workflow_shards.py",
)


def shell_command_after(lines, start, needle):
    for index in range(start, len(lines)):
        if needle in lines[index]:
            command = [lines[index].strip()]
            while command[-1].endswith("\\"):
                index += 1
                command.append(lines[index].strip())
            return " ".join(part.removesuffix("\\") for part in command)
    raise AssertionError(f"workflow command not found: {needle}")


class FastWorkflowHelperTests(unittest.TestCase):
    def test_helper_tests_run_in_independent_two_shard_job_exactly_once(self):
        helper_job = WORKFLOW.split("  ci-helper-tests:\n", 1)[1].split(
            "\n  artifact-consumer:", 1
        )[0]
        workflow_lines = WORKFLOW.splitlines()
        helper_start = next(
            index for index, line in enumerate(workflow_lines)
            if line == "      - name: Run deterministic CI helper shard"
        )
        command = shell_command_after(
            workflow_lines, helper_start, '"$PYTHON" scripts/ci/run-unittest.py'
        )
        helper_modules = re.findall(r"test_[A-Za-z0-9_]+\.py", command)
        local_helper_line = next(
            line for line in RUN_FAST.splitlines()
            if line.startswith("    run_logged focused-helper-python ")
        )
        local_modules = re.findall(r"test_[A-Za-z0-9_]+\.py", local_helper_line)
        focused_line = next(
            line for line in RUN_FAST.splitlines()
            if line.startswith("run_logged focused-python ")
        )
        producer_step_start = WORKFLOW.index("      - name: Run fast CI")
        producer_step_end = WORKFLOW.index("      - name: Package the verified Modex executable")
        producer_step = WORKFLOW[producer_step_start:producer_step_end]
        helper_gate_start = RUN_FAST.index(
            'if [[ "${MODEX_CI_FAST_HELPER_TESTS_IN_SHARDS:-0}" == 1 ]]; then'
        )
        helper_gate_end = RUN_FAST.index("\nfi", helper_gate_start)
        helper_gate = RUN_FAST[helper_gate_start:helper_gate_end]

        self.assertEqual(helper_modules, list(HELPER_MODULES))
        self.assertEqual(local_modules, list(HELPER_MODULES))
        self.assertNotIn("needs:", helper_job)
        self.assertIn("shard: [0, 1]", helper_job)
        self.assertIn("--shard-index \"$SHARD_INDEX\" --shard-count 2", command)
        self.assertIn("ref: ${{ github.sha }}", helper_job)
        self.assertIn("EXPECTED_SOURCE_SHA: ${{ github.sha }}", helper_job)
        self.assertIn('checkout_sha="$(git rev-parse HEAD)"', helper_job)
        self.assertIn('git status --porcelain --untracked-files=all', helper_job)
        self.assertIn("persist-credentials: false", helper_job)
        self.assertIn("python-version: '3.14.10'", helper_job)
        self.assertIn("MODEX_CI_FAST_HELPER_TESTS_IN_SHARDS: '1'", producer_step)
        self.assertIn("focused-helper-python: SHARDED", helper_gate)
        self.assertIn("else", helper_gate)
        self.assertIn("run_logged focused-helper-python", helper_gate)
        self.assertLess(helper_gate.index("else"), helper_gate.index("run_logged focused-helper-python"))
        self.assertEqual(
            {RUNNER.shard_for_module(module.removesuffix(".py"), 2) for module in HELPER_MODULES},
            {0, 1},
        )
        self.assertEqual(
            [module for module in HELPER_MODULES if module in focused_line], []
        )
        for module in HELPER_MODULES:
            with self.subTest(module=module):
                self.assertEqual(RUN_FAST.count(module), 1)
                self.assertEqual(WORKFLOW.count(module), 1)

    def test_artifact_consumer_only_verifies_a_successful_producer_artifact(self):
        consumer = WORKFLOW.split("  artifact-consumer:\n", 1)[1]

        self.assertEqual(WORKFLOW.count("  artifact-consumer:\n"), 1)
        self.assertIn("    needs: linux-x86_64\n", consumer)
        self.assertNotIn("if: always()", consumer)
        self.assertIn("artifact-manifest.py extract", consumer)
        self.assertIn("artifact-manifest.py verify", consumer)
        self.assertIn('[[ -x "$artifact_root/modex" ]]', consumer)
        self.assertIn("modex 0.1.0-dev", consumer)
        self.assertNotIn("run-unittest.py", consumer)
        self.assertNotIn("matrix:", consumer)


if __name__ == "__main__":
    unittest.main()
