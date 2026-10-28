"""Keep fast CI helper tests owned by exactly one producer or consumer shard."""

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
CONSUMER_MODULES = (
    "test_ci_artifact_manifest.py",
    "test_ci_shard_runner.py",
    "test_ci_test_census.py",
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


class FastWorkflowShardOwnershipTests(unittest.TestCase):
    def test_helper_modules_are_owned_once_by_the_two_consumer_shards(self):
        producer_line = next(
            line for line in RUN_FAST.splitlines()
            if line.startswith("run_logged focused-python ")
        )
        producer_modules = re.findall(r"test_[A-Za-z0-9_]+\.py", RUN_FAST)
        producer_focused_modules = re.findall(r"test_[A-Za-z0-9_]+\.py", producer_line)
        helper_line = next(
            line for line in RUN_FAST.splitlines()
            if line.startswith("    run_logged focused-helper-python ")
        )
        producer_helper_modules = re.findall(r"test_[A-Za-z0-9_]+\.py", helper_line)
        helper_gate_start = RUN_FAST.index(
            'if [[ "${MODEX_CI_FAST_HELPER_TESTS_IN_CONSUMERS:-0}" == 1 ]]; then'
        )
        helper_gate_end = RUN_FAST.index("\nfi", helper_gate_start)
        helper_gate = RUN_FAST[helper_gate_start:helper_gate_end]
        workflow_lines = WORKFLOW.splitlines()
        producer_start = next(
            index for index, line in enumerate(workflow_lines)
            if line == "      - name: Run fast CI"
        )
        producer_end = next(
            index for index in range(producer_start + 1, len(workflow_lines))
            if workflow_lines[index].startswith("      - name:")
        )
        producer_step = "\n".join(workflow_lines[producer_start:producer_end])
        consumer_start = next(
            index for index, line in enumerate(workflow_lines)
            if "- name: Verify the handoff and execute deterministic shard tests" in line
        )
        consumer_command = shell_command_after(
            workflow_lines, consumer_start, '"$PYTHON" scripts/ci/run-unittest.py'
        )
        consumer_modules = re.findall(r"test_[A-Za-z0-9_]+\.py", consumer_command)

        self.assertEqual(consumer_modules, list(CONSUMER_MODULES))
        self.assertIn("test_ci_workflow_shards.py", producer_focused_modules)
        self.assertEqual(producer_helper_modules, list(CONSUMER_MODULES))
        self.assertIn("else", helper_gate)
        self.assertLess(
            helper_gate.index("else"), helper_gate.index("run_logged focused-helper-python")
        )
        self.assertIn("focused-helper-python: SHARDED", helper_gate)
        self.assertIn("MODEX_CI_FAST_HELPER_TESTS_IN_CONSUMERS: '1'", producer_step)
        self.assertEqual(WORKFLOW.count("MODEX_CI_FAST_HELPER_TESTS_IN_CONSUMERS"), 1)
        for module in CONSUMER_MODULES:
            with self.subTest(module=module):
                self.assertEqual(producer_modules.count(module), 1)
                self.assertEqual(producer_focused_modules.count(module), 0)
                self.assertEqual(producer_helper_modules.count(module), 1)
                self.assertEqual(consumer_modules.count(module), 1)
        self.assertIn('--shard-index "$SHARD_INDEX" --shard-count 2', consumer_command)
        self.assertEqual(
            {RUNNER.shard_for_module(module.removesuffix(".py"), 2) for module in CONSUMER_MODULES},
            {0, 1},
        )


if __name__ == "__main__":
    unittest.main()
