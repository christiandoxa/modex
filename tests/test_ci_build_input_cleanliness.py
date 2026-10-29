"""Check source-tree gate behavior without touching the shared checkout."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / "scripts/ci/check-build-inputs.py"
SPEC = importlib.util.spec_from_file_location("modex_check_build_inputs", CHECK_PATH)
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)
WORKFLOW = (ROOT / ".github/workflows/ci-fast.yml").read_text(encoding="utf-8")
RUN_FAST = (ROOT / "scripts/ci/run-fast.sh").read_text(encoding="utf-8")


class BuildInputCleanlinessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="modex-build-input-gate-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repository = self.base / "repo"
        self.repository.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        self.environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        self.git("init", "--quiet")
        self.git("config", "user.name", "Synthetic CI Test")
        self.git("config", "user.email", "ci-test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        (self.repository / ".gitignore").write_text(
            "/build/\n/test-results/\n__pycache__/\n*.pyc\n", encoding="utf-8"
        )
        source = self.repository / "src"
        source.mkdir()
        (source / "main.mojo").write_text("fn main():\n    pass\n", encoding="utf-8")
        (self.repository / "Makefile").write_text("build:\n\ttrue\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "synthetic baseline")

    def git(self, *arguments):
        return subprocess.run(
            ["git", *arguments],
            cwd=self.repository,
            env=self.environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            check=True,
        )

    def check(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            result = CHECK.main(self.repository, self.environment)
        return result, errors.getvalue()

    def test_modified_tracked_source_is_rejected(self):
        (self.repository / "src/main.mojo").write_text(
            "fn main():\n    print(\"changed\")\n", encoding="utf-8"
        )

        result, errors = self.check()

        self.assertEqual(result, 1)
        self.assertIn("src/main.mojo", errors)

    def test_untracked_nonignored_source_is_rejected(self):
        extra = self.repository / "src/extra.mojo"
        extra.write_text("fn extra():\n    pass\n", encoding="utf-8")

        result, errors = self.check()

        self.assertEqual(result, 1)
        self.assertIn("src/extra.mojo", errors)

    def test_ignored_build_outputs_are_preserved(self):
        binary = self.repository / "build/modex"
        results = self.repository / "test-results/summary.json"
        binary.parent.mkdir()
        results.parent.mkdir()
        binary.write_bytes(b"synthetic build output")
        results.write_text("synthetic test output", encoding="utf-8")

        result, errors = self.check()

        self.assertEqual((result, errors), (0, ""))
        self.assertEqual(binary.read_bytes(), b"synthetic build output")
        self.assertEqual(results.read_text(encoding="utf-8"), "synthetic test output")

    def test_cleanliness_gate_runs_before_fast_build_and_packaging(self):
        gate = 'scripts/ci/check-build-inputs.py'
        opt_in = 'if [[ "${MODEX_CI_ARTIFACT_PRODUCER:-0}" == 1 ]]; then'
        opt_in_start = RUN_FAST.index(opt_in)
        opt_in_end = RUN_FAST.index("\nfi", opt_in_start)
        producer_gate = RUN_FAST[opt_in_start:opt_in_end]
        self.assertIn(f'run_logged build-input-check "$PYTHON" {gate}', producer_gate)
        self.assertEqual(RUN_FAST.count("MODEX_CI_ARTIFACT_PRODUCER"), 1)
        build = RUN_FAST.index("run_logged focused-build make build unit")
        self.assertLess(opt_in_start, build)
        workflow_lines = WORKFLOW.splitlines()
        producer_start = workflow_lines.index("      - name: Run fast CI")
        producer_end = next(
            index for index in range(producer_start + 1, len(workflow_lines))
            if workflow_lines[index].startswith("      - name:")
        )
        producer_step = "\n".join(workflow_lines[producer_start:producer_end])
        self.assertIn("MODEX_CI_ARTIFACT_PRODUCER: '1'", producer_step)
        self.assertEqual(WORKFLOW.count("MODEX_CI_ARTIFACT_PRODUCER"), 1)
        python_tests_start = RUN_FAST.index(
            'run_logged focused-python-active "$PYTHON"'
        )
        python_tests_end = RUN_FAST.index("\n", python_tests_start)
        python_tests = RUN_FAST[python_tests_start:python_tests_end]
        self.assertIn("test_ci_build_input_cleanliness.py", python_tests)

        package_start = WORKFLOW.index("- name: Package the verified Modex executable")
        package_end = WORKFLOW.index("- name: Upload the Modex build handoff", package_start)
        package = WORKFLOW[package_start:package_end]
        self.assertLess(package.index(f'"$PYTHON" {gate}'), package.index('source_sha="$(git rev-parse HEAD)"'))


if __name__ == "__main__":
    unittest.main()
