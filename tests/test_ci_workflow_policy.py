"""Regression coverage for immutable action references in workflow steps."""

from contextlib import redirect_stderr
import importlib.util
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "scripts/ci/check-workflow-policy.py"
SPEC = importlib.util.spec_from_file_location("modex_workflow_policy", POLICY_PATH)
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


class WorkflowActionPinTests(unittest.TestCase):
    def test_unpinned_list_action_fails_policy(self):
        with tempfile.TemporaryDirectory(prefix="modex-workflow-policy-") as temporary:
            workflow = Path(temporary) / "workflow.yml"
            workflow.write_text(
                "permissions:\n"
                "  contents: read\n"
                "jobs:\n"
                "  check:\n"
                "    steps:\n"
                "      - uses: actions/checkout@v4\n",
                encoding="utf-8",
            )
            errors = StringIO()
            with patch.object(POLICY, "WORKFLOWS", Path(temporary)), redirect_stderr(errors):
                result = POLICY.main()

        self.assertEqual(result, 1)
        self.assertIn("actions/checkout@v4", errors.getvalue())
        self.assertIn("action must use a full immutable commit SHA", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
