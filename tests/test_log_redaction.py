"""Exact release comparisons for detached log secret redaction."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from log_mismatches import UNAPPROVED_SAFE_DIFFERENCE
import test_cli
from test_cli import MODEX, ORACLE


def run_message(binary, message):
    with tempfile.TemporaryDirectory(prefix="modex-log-redaction-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        session = root / "home/.codex/sessions/2026/10/24/rollout-fixture.jsonl"
        session.parent.mkdir(parents=True)
        session.write_text(json.dumps({
            "timestamp": "2026-10-24T01:02:04Z",
            "type": "event_msg",
            "payload": {"type": "user_message", "message": message},
        }) + "\n")
        result = subprocess.run(
            sandbox_command(
                binary, root, ["log", "last", "--json"],
                argv0="modex" if binary == MODEX else "prodex",
                environment={"TZ": "UTC"},
            ),
            capture_output=True, timeout=10, check=False,
        )
        return result.returncode, result.stdout, result.stderr


class LogRedactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file():
            raise AssertionError("The pinned Prodex 0.439.2 oracle is required")
        test_cli.CliTests.setUpClass()

    def assert_matches_oracle(self, message):
        baseline = run_message(ORACLE, message)
        modex = run_message(MODEX, message)
        self.assertEqual(modex, baseline, message)

    def test_nested_json_and_quoted_sensitive_assignments(self):
        for message in (
            '{"api_key":"synthetic-secret-value"}',
            'prefix {"nested":{"access_token":"synthetic-secret-value"}} suffix',
            '{"password": "synthetic secret, with punctuation: !"}',
            'api_key="synthetic-secret-value"',
            "password='synthetic-secret-value'",
            "password='synthetic-secret-value",
            'api_key="synthetic\\\"quoted-value"',
            'api_key = "synthetic-secret-value"',
            '"api_key" : "synthetic-secret-value"',
            "'api_key' = 'synthetic-secret-value'",
            '"api_key"\t :\t"synthetic-secret-value"',
            'url=https://example.test?api_key=sk-live-synthetic-value',
            '東京 🙂 stays exact; api_key="秘密-synthetic-value" 🦊',
            'prefix🙂suffix and café remain unchanged',
            'Cookie: first=synthetic-one; second=synthetic-two\nvisible=ok',
            'x-api-key=synthetic-value proxy_authorization=synthetic-value refresh-token=synthetic-value customCredentialValue=synthetic-value',
        ):
            with self.subTest(message=message):
                self.assert_matches_oracle(message)

    def test_unicode_whitespace_credentials_are_safely_redacted(self):
        for mismatch in UNAPPROVED_SAFE_DIFFERENCE:
            with self.subTest(message=mismatch["input"]):
                baseline = run_message(ORACLE, mismatch["input"])
                modex = run_message(MODEX, mismatch["input"])
                self.assertEqual(baseline, (0, mismatch["baseline_stdout"], b""))
                self.assertEqual(modex, (0, mismatch["modex_stdout"], b""))
                self.assertNotIn(mismatch["secret"].encode(), modex[1])
                self.assertEqual(
                    mismatch["secret"].encode() in baseline[1],
                    mismatch["baseline_leaks_secret"],
                )

    def test_ambiguous_sensitive_values_never_expose_synthetic_secrets(self):
        cases = (
            ("password= \t \u2003 synthetic-first synthetic-second", ("synthetic-first", "synthetic-second")),
            ('password= \t\u2003  "synthetic-quoted-value"', ("synthetic-quoted-value",)),
            (
                'password=\u0085"synthetic-c1-control-value"',
                ("synthetic-c1-control-value",),
            ),
            ('password=\x1b[31m"synthetic-control-value"', ("synthetic-control-value",)),
            (
                'password=prefix \t\u2003"synthetic-after-whitespace-value"',
                ("synthetic-after-whitespace-value",),
            ),
            (
                'password=prefix \t\x1b[31m"synthetic-after-control-value"',
                ("synthetic-after-control-value",),
            ),
            ('password=\u2028“synthetic-curly-quoted value”', ("synthetic-curly-quoted", "value")),
            ('password=\u200b"synthetic-zero-width value"', ("synthetic-zero-width", "value")),
        )
        for message, sentinels in cases:
            with self.subTest(message=message):
                result = run_message(MODEX, message)
                self.assertEqual(result[0], 0)
                self.assertEqual(result[2], b"")
                for sentinel in sentinels:
                    self.assertNotIn(sentinel.encode(), result[1])

    def test_many_sensitive_assignments_remain_bounded(self):
        count = 3000
        message = " ".join(
            f"password=synthetic-redaction-{index}" for index in range(count)
        )
        result = run_message(MODEX, message)
        self.assertEqual(result[0], 0)
        self.assertEqual(result[2], b"")
        self.assertEqual(result[1].count(b"<redacted>"), count)
        self.assertNotIn(b"synthetic-redaction-", result[1])

    def test_bearer_schemes_and_api_key_prefix_boundaries(self):
        for message in (
            'Authorization: Bearer synthetic-token',
            'authorization: BASIC synthetic-token',
            'Token synthetic-token',
            'Bearer synthetic-token',
            'sk-proj-synthetic-credential-12345678',
            'SK-12345678',
            'sk_test_synthetic-credential-12345678',
            'sk_live_synthetic-credential-12345678',
            'sk-ant-synthetic-credential-12345678',
            'sk-1234567',
        ):
            with self.subTest(message=message):
                self.assert_matches_oracle(message)


if __name__ == "__main__":
    unittest.main()
