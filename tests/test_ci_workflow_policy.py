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


class WorkflowPolicyTests(unittest.TestCase):
    def run_policy(self, workflow_text):
        with tempfile.TemporaryDirectory(prefix="modex-workflow-policy-") as temporary:
            workflow = Path(temporary) / "workflow.yml"
            workflow.write_text(workflow_text, encoding="utf-8")
            errors = StringIO()
            with patch.object(POLICY, "WORKFLOWS", Path(temporary)), redirect_stderr(errors):
                result = POLICY.main()
        return result, errors.getvalue()

    def test_unpinned_list_action_fails_policy(self):
        result, output = self.run_policy(
            "permissions:\n"
            "  contents: read\n"
            "jobs:\n"
            "  check:\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
        )

        self.assertEqual(result, 1)
        self.assertIn("actions/checkout@v4", output)
        self.assertIn("action must use a full immutable commit SHA", output)

    def test_unpinned_actions_in_whitespace_and_flow_forms_fail_policy(self):
        steps = (
            "      - uses : actions/checkout@v4\n",
            "      - { uses: actions/checkout@v4 }\n",
            "      - { name: checkout, uses: actions/checkout@v4 }\n",
            "      - name: checkout\n"
            "        uses : actions/checkout@v4\n",
        )

        for step in steps:
            with self.subTest(step=step):
                result, output = self.run_policy(
                    "permissions:\n"
                    "  contents: read\n"
                    "jobs:\n"
                    "  check:\n"
                    "    steps:\n"
                    + step
                )

                self.assertEqual(result, 1)
                self.assertIn("actions/checkout@v4", output)
                self.assertIn("action must use a full immutable commit SHA", output)

    def test_split_flow_action_reference_fails_closed(self):
        steps = (
            "      - { uses:\n"
            "          actions/checkout@v4 }\n",
            "      - { uses: # split value\n"
            "          actions/checkout@v4 }\n",
        )

        for step in steps:
            with self.subTest(step=step):
                result, output = self.run_policy(
                    "permissions:\n"
                    "  contents: read\n"
                    "jobs:\n"
                    "  check:\n"
                    "    steps:\n"
                    + step
                )

                self.assertEqual(result, 1)
                self.assertIn("action uses key has unsupported YAML syntax", output)

    def test_quoted_and_tagged_action_keys_fail_closed(self):
        steps = (
            '      - "uses": actions/checkout@v4\n',
            '      - "u\\u0073es": actions/checkout@v4\n',
            "      - 'uses': actions/checkout@v4\n",
            "      - !!str uses: actions/checkout@v4\n",
            '      - !!str "uses": actions/checkout@v4\n',
            '      - !<tag:yaml.org,2002:str> "u\\u0073es": actions/checkout@v4\n',
        )

        for step in steps:
            with self.subTest(step=step):
                result, output = self.run_policy(
                    "permissions:\n"
                    "  contents: read\n"
                    "jobs:\n"
                    "  check:\n"
                    "    steps:\n"
                    + step
                )

                self.assertEqual(result, 1)
                self.assertIn("workflow policy: FAIL", output)

    def test_job_permission_overrides_cannot_grant_write_access(self):
        workflows = (
            "permissions:\n"
            "  contents: read\n"
            "jobs:\n"
            "  check:\n"
            "    permissions: write-all\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: true\n",
            "permissions:\n"
            "  contents: read\n"
            "jobs:\n"
            "  check:\n"
            "    permissions: { contents: write }\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: true\n",
        )

        for workflow_text in workflows:
            with self.subTest(workflow=workflow_text):
                result, output = self.run_policy(workflow_text)

                self.assertEqual(result, 1)
                self.assertIn("permissions must use the single canonical read-only block", output)

    def test_root_permissions_only_accept_the_single_unquoted_contents_read_key(self):
        workflows = (
            "permissions:\n"
            "  contents: read\n"
            "  issues: \"write\"\n",
            "permissions:\n"
            "  contents: read\n"
            "  issues: read\n",
            "permissions: { contents: read }\n",
            "permissions: &read_only\n"
            "  contents: read\n",
            "permissions:\n"
            "  <<: *read_only\n"
            "  contents: read\n",
        )

        for permission_block in workflows:
            with self.subTest(permission_block=permission_block):
                result, output = self.run_policy(permission_block + "jobs:\n  check:\n    steps:\n      - run: true\n")

                self.assertEqual(result, 1)
                self.assertIn("permissions must use the single canonical read-only block", output)

    def test_alternative_yaml_key_syntax_cannot_create_job_permissions(self):
        job_overrides = (
            "    env:\n"
            "      PERMISSION_KEY: &permission_key permissions\n"
            "    *permission_key: write-all\n",
            "    ? permissions\n"
            "    : write-all\n",
            "    !!str permissions: write-all\n",
            "    !<tag:yaml.org,2002:str> permissions: write-all\n",
            "    \"permiss\\u0069ons\": write-all\n",
        )

        for job_override in job_overrides:
            with self.subTest(job_override=job_override):
                workflow_text = (
                    "permissions:\n"
                    "  contents: read\n"
                    "jobs:\n"
                    "  check:\n"
                    "    runs-on: ubuntu-latest\n"
                    + job_override
                    + "    steps:\n"
                    + "      - run: true\n"
                )
                result, output = self.run_policy(workflow_text)

                self.assertEqual(result, 1)
                self.assertIn("permissions must use the single canonical read-only block", output)

    def test_permissions_like_text_inside_run_blocks_is_not_workflow_config(self):
        result, output = self.run_policy(
            "permissions:\n"
            "  contents: read\n"
            "jobs:\n"
            "  check:\n"
            "    if: ${{ !cancelled() }}\n"
            "    steps:\n"
            "      - run: |\n"
            "          cat <<'EOF'\n"
            "          permissions: write-all\n"
            "          contents: write\n"
            "          *permission_key: write-all\n"
            "          - uses : actions/checkout@v4\n"
            '          - "u\\u0073es": actions/checkout@v4\n'
            "          EOF\n"
            "      - run: 'printf \"%s\" \"{permissions: write-all; uses: actions/checkout@v4}\"'\n"
        )

        self.assertEqual(result, 0, output)


if __name__ == "__main__":
    unittest.main()
