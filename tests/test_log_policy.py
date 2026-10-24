"""Runtime policy path selection through the pinned CLI oracle."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
import test_cli
from test_cli import MODEX, ORACLE


def token_event(value):
    return {"timestamp": "2026-10-24T01:02:04Z", "event": "token_usage", "fields": {
        "input_tokens": value, "output_tokens": "4"}}


class LogPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def invoke(self, binary, policy, locations, environment=None):
        with tempfile.TemporaryDirectory(prefix="modex-log-policy-") as directory:
            root = Path(directory)
            (root / "home").mkdir(mode=0o700)
            (root / "workspace").mkdir()
            prodex = root / "prodex"
            prodex.mkdir(mode=0o700)
            (root / "tmp").mkdir()
            if policy is not None:
                (prodex / "policy.toml").write_text(policy.replace("@ROOT@", str(root)))
            for name, value in locations.items():
                path = root / name
                path.mkdir(parents=True, exist_ok=True)
                (path / "prodex-runtime-fixture.log").write_text(json.dumps(token_event(value)) + "\n")
            env = {"TZ": "UTC", "PRODEX_HOME": str(prodex), "TMPDIR": str(root / "tmp")}
            if environment:
                env.update({key: value.replace("@ROOT@", str(root))
                            for key, value in environment.items()})
            result = subprocess.run(
                sandbox_command(binary, root, ["log", "last", "--json"],
                                argv0="prodex" if binary == ORACLE else "modex",
                                environment=env),
                capture_output=True, timeout=10, check=False)
            return result.returncode, result.stdout, result.stderr

    def assert_selected(self, policy, locations, expected, environment=None):
        baseline = self.invoke(ORACLE, policy, locations, environment)
        actual = self.invoke(MODEX, policy, locations, environment)
        self.assertEqual(actual, baseline)
        self.assertEqual(actual[0], 0, actual[2])
        self.assertIn(('"input_tokens":' + str(expected)).encode(), actual[1])

    def test_relative_and_absolute_policy_log_dirs(self):
        self.assert_selected(
            'version=1\nextra=1\n[runtime]\nlog_dir="chosen"\nextra=2\n'
            '[runtime_proxy]\npreset="Many_Terminals"\n'
            '[secrets]\nextra=3\n[runtime.future]\n'
            'local_date=2026-10-24\nlocal_time=07:32:00\n'
            'local_datetime=2026-10-24T07:32:00\nnumber=1.25\n',
            {"prodex/chosen": 11, "tmp": 12}, 11)
        self.assert_selected(
            'version=1\n[runtime]\nlog_dir="chosen"\n[runtime.future]\n'
            'value = """before\\\n  after"""\n',
            {"prodex/chosen": 17, "tmp": 18}, 17)
        self.assert_selected(
            'version=1\n[runtime]\nlog_dir="@ROOT@/abslogs"\n',
            {"abslogs": 13, "tmp": 14}, 13)
        self.assert_selected(
            'version=1\n[runtime]\nlog_dir="  chosen  "\n'
            '[runtime.future]\nanswer=1\n[secrets.future]\nanswer=2\n',
            {"prodex/  chosen  ": 15, "tmp": 16}, 15)

    def test_environment_override_and_empty_value(self):
        self.assert_selected(
            'version=1\n[runtime]\nlog_dir="chosen"\n',
            {"workspace/override": 21, "prodex/chosen": 22, "tmp": 23}, 21,
            {"PRODEX_RUNTIME_LOG_DIR": "override"})
        self.assert_selected(
            'version=1\n[runtime]\nlog_dir="chosen"\n',
            {"absolute-override": 26, "prodex/chosen": 27, "tmp": 28}, 26,
            {"PRODEX_RUNTIME_LOG_DIR": "@ROOT@/absolute-override"})
        self.assert_selected(
            'version=1\n[runtime]\nlog_dir="chosen"\n',
            {"prodex/chosen": 24, "tmp": 25}, 24,
            {"PRODEX_RUNTIME_LOG_DIR": ""})

    def test_invalid_policy_falls_back_to_tmpdir(self):
        policies = [
            'version="1"\n',
            'version=1\n[runtime]\nlog_dir="  "\n',
            'version=1\n[runtime_proxy]\nunknown=3\n',
            'version=1\n[secrets]\nkeyring_service="service"\n',
            'version=1\n[runtime_proxy]\nworker_count=-1\n',
            'version=1\n[runtime]\nlog_format="JSON"\n',
            'version=1\n[runtime]\nlog_dir="chosen"\n[runtime.future]\n'
            'value = """before\\ \r\n\r after"""\n',
            'version=1\n[runtime]\nlog_dir="chosen"\n[runtime.future]\n'
            'truncated=2000-01-01T00\n',
        ]
        for policy in policies:
            with self.subTest(policy=policy):
                self.assert_selected(policy, {"prodex/chosen": 31, "tmp": 32}, 32)

    def test_policy_scalar_type_and_range_boundaries(self):
        cases = [
            ('[runtime_proxy]\nworker_count=9223372036854775807\n', True),
            ('[runtime_proxy]\nworker_count=9223372036854775808\n', True),
            ('[runtime_proxy]\nworker_count=18446744073709551615\n', True),
            ('[runtime_proxy]\nworker_count=18446744073709551616\n', False),
            ('[runtime_proxy]\nworker_count=-0\n', True),
            ('[runtime_proxy]\nhttp_connect_timeout_ms=9223372036854775808\n', True),
            ('[runtime_proxy]\nhttp_connect_timeout_ms=18446744073709551615\n', True),
            ('[runtime_proxy]\nhttp_connect_timeout_ms=18446744073709551616\n', False),
            ('[runtime_proxy]\nstream_idle_timeout_ms=-0\n', True),
            ('[runtime_proxy]\nresponses_critical_floor_percent=-9223372036854775808\n', True),
            ('[runtime_proxy]\nresponses_critical_floor_percent=9223372036854775807\n', True),
            ('[runtime_proxy]\nresponses_critical_floor_percent=-9223372036854775809\n', False),
            ('[runtime_proxy]\nresponses_critical_floor_percent=-0\n', True),
            ('[runtime_proxy]\npreset="MANY-TERMINALS"\n', True),
            ('[runtime_proxy]\npreset="many_terminals"\n', True),
            ('[runtime_proxy]\npreset=" many-terminals "\n', False),
            ('[runtime_proxy]\npreset=1\n', False),
            ('[secrets]\nbackend="FiLe"\n', True),
            ('[secrets]\nbackend=" file "\n', False),
            ('[secrets]\nbackend="KEYRING"\nkeyring_service="service"\n', True),
            ('[secrets]\nbackend="keyring"\nkeyring_service="service name"\n', False),
        ]
        for body, valid in cases:
            with self.subTest(body=body):
                expected = 41 if valid else 42
                self.assert_selected(
                    'version=1\n[runtime]\nlog_dir="chosen"\n' + body,
                    {"prodex/chosen": 41, "tmp": 42}, expected)


if __name__ == "__main__":
    unittest.main()
