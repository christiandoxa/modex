"""Verify production Super help, selected baseline errors, and safe startup gaps."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from session_oracle import sandbox_command
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as ORACLE_01651_SHA256
from test_super_launch import normalized_app_server_args, run_private_launch
from test_cli import HISTORICAL_04391_ORACLE_SHA256, MODEX, ORACLE, ORACLE_SHA256, ROOT


SUPER_ARGV_CAPTURE = ROOT / "tests/fixtures/super-argv/cases.json"


def isolated_super(binary, arguments):
    with tempfile.TemporaryDirectory(prefix="modex-super-cli-") as directory:
        root = Path(directory)
        for name in ("home", "workspace", "prodex"):
            (root / name).mkdir(mode=0o700)
        cache = root / "prodex/update-check.json"
        cache.write_text(json.dumps({"source": "GitHub", "latest_version": "0.439.0", "checked_at": int(time.time())}))
        cache.chmod(0o600)
        before = {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
                  for path in root.rglob("*")}
        command = sandbox_command(binary, root, arguments, argv0="modex" if binary == MODEX else "prodex",
                                  environment={"PRODEX_HOME": str(root / "prodex")})
        result = subprocess.run(command, capture_output=True, timeout=10, check=False)
        after = {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
                 for path in root.rglob("*")}
        return result, after != before


class SuperCliTests(unittest.TestCase):
    def test_help_matches_baseline_without_creating_application_state(self):
        for arguments in (["super", "--help"], ["super", "-h"], ["s", "--help"], ["help", "super"], ["help", "s"]):
            with self.subTest(arguments=arguments):
                baseline, _ = isolated_super(ORACLE, arguments)
                native, mutated = isolated_super(MODEX, arguments)
                expected = baseline.stdout.decode()
                self.assertEqual((native.returncode, native.stdout.decode(), native.stderr),
                                 (baseline.returncode, expected, baseline.stderr))
                self.assertFalse(mutated)

    def test_positional_tail_validation_matches_baseline(self):
        cases = (
            ["exec", "--sub-agent-model", "fixture-model"],
            ["exec", "--sub-agent", "--no-sub-agent"],
            ["exec", "--api-key", "synthetic-key"],
            ["exec", "--context-window", "16384"],
            ["exec", "--presidio", "--no-presidio"],
            ["exec", "--no-presidio", "--require-tool", "presidio"],
            ["exec", "--provider", "deepseek", "--url", "http://127.0.0.1:8131"],
            ["exec", "--base-url", "http://127.0.0.1:8131", "--url", "http://127.0.0.1:8131"],
            ["exec", "--sub-agent", "--sub-agent-provider", "local"],
            ["exec", "--sub-agent", "--sub-agent-url", "http://127.0.0.1:8131"],
            ["gui", "--sub-agent"],
        )
        for tail in cases:
            with self.subTest(tail=tail):
                baseline, _ = isolated_super(ORACLE, ["super", *tail])
                native, mutated = isolated_super(MODEX, ["super", *tail])
                self.assertEqual((native.returncode, native.stdout, native.stderr),
                                 (baseline.returncode, baseline.stdout, baseline.stderr))
                self.assertFalse(mutated)

    def test_credential_free_url_validation_matches_frozen_capture(self):
        capture = json.loads(SUPER_ARGV_CAPTURE.read_text())
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        self.assertEqual(capture["oracle_sha256"], HISTORICAL_04391_ORACLE_SHA256)
        self.assertTrue(capture["network_isolated"])
        for case in capture["cases"]:
            with self.subTest(name=case["name"]):
                baseline, _ = isolated_super(ORACLE, case["argv"])
                expected = (case["returncode"], case["stdout"].encode(), case["stderr"].encode())
                self.assertEqual((baseline.returncode, baseline.stdout, baseline.stderr), expected)
                native, mutated = isolated_super(MODEX, case["argv"])
                self.assertEqual((native.returncode, native.stdout, native.stderr), expected)
                self.assertFalse(mutated)
                self.assertNotIn("synthetic-secret".encode(), native.stderr)

    def test_invalid_percent_encoded_url_hosts_fail_before_launch(self):
        secret = "synthetic-url-api-key"
        for url in (
            "https://%zz.example.test/path",
            "https://%2z.example.test/path",
            "https://foo%2Fbar.example.test/path",
            "https://%25.example.test/path",
            "https://%20.example.test/path",
            "https://a%40b.example.test/path",
            "https://a|b.example.test/path",
            "https://a^b.example.test/path",
            "https://a%EF%BC%8Fb.example.test/path",
            "https://a%FFb.example.test/path",
            "https://a%C2%A0b.example.test/path",
        ):
            observed = []
            for binary in (ORACLE_01651, ORACLE, MODEX):
                result, _ = isolated_super(
                    binary,
                    ["super", "exec", "--provider", "deepseek", "--api-key", secret,
                     "--url", url, "synthetic prompt"],
                )
                self.assertEqual((result.returncode, result.stdout), (1, b""))
                self.assertIn(b"invalid --url", result.stderr)
                self.assertNotIn(secret.encode(), result.stdout + result.stderr)
                observed.append((result.returncode, result.stdout, result.stderr))
            with self.subTest(url=url):
                self.assertEqual(observed[1:], observed[:1] * 2)

    def test_rollout_weight_float_diagnostics_match_both_releases(self):
        self.assertEqual(hashlib.sha256(ORACLE_01651.read_bytes()).hexdigest(), ORACLE_01651_SHA256)
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        valid = ("NaN", "-NaN", "+inf", "-infinity", "1e9999", "1e999999999999999999999999999999", "1e-9999", "9" * 1200, "+0", "-0", "1.e1", ".1e2")
        invalid = ("", ".", "in", "infinite", "1e", "1e+", " 1 ", "\t1", "1\n", "1 2", "1_0", "1f", "0x1p0", "1.0tail", "١", "１２", "−0", "\u00a01\u00a0")
        binaries = (ORACLE_01651, ORACLE, MODEX)
        for option in ("--rollout-budget-sampling-weight", "--rollout-budget-prefill-weight"):
            for value, expected_exit in [(item, 0) for item in valid] + [(item, 2) for item in invalid]:
                outputs = []
                for binary in binaries:
                    with self.subTest(option=option, value=value, binary=binary.name):
                        result, mutated = isolated_super(binary, ["super", option, value, "--help"])
                        self.assertFalse(mutated)
                        stdout = result.stdout
                        if binary != MODEX:
                            for command in ("super", "run", "doctor", "login"):
                                stdout = stdout.replace(b"prodex " + command.encode(), b"modex " + command.encode())
                        outputs.append((result.returncode, stdout, result.stderr))
                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(outputs[1], outputs[2])
                self.assertEqual(outputs[0][0], expected_exit)

    def test_rollout_budget_reminders_identify_the_invalid_element(self):
        self.assertEqual(hashlib.sha256(ORACLE_01651.read_bytes()).hexdigest(), ORACLE_01651_SHA256)
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        cases = (("1,,2", ""), (",1", ""), ("1,", ""), ("1,invalid,2", "invalid"))
        for value, invalid_element in cases:
            outputs = []
            for binary in (ORACLE_01651, ORACLE, MODEX):
                with self.subTest(value=value, binary=binary.name):
                    result, mutated = isolated_super(binary, [
                        "super", "--rollout-budget-tokens", "100",
                        "--rollout-budget-reminders", value, "--help",
                    ])
                    self.assertFalse(mutated)
                    self.assertEqual((result.returncode, result.stdout), (2, b""))
                    self.assertIn(
                        b"invalid value '" + invalid_element.encode() + b"' for '--rollout-budget-reminders <TOKENS>'",
                        result.stderr,
                    )
                    outputs.append((result.returncode, result.stdout, result.stderr))
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(outputs[1], outputs[2])

    def test_positional_rollout_weight_errors_match_releases_before_child_start(self):
        self.assertEqual(hashlib.sha256(ORACLE_01651.read_bytes()).hexdigest(), ORACLE_01651_SHA256)
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        binaries = (ORACLE_01651, ORACLE, MODEX)
        for option in ("--rollout-budget-sampling-weight", "--rollout-budget-prefill-weight"):
            for value in ("", "in", "infinite", "1e", " 1 ", "1f", "0x1p0", "1.0tail", "١", "\u00a01\u00a0"):
                outputs = []
                for binary in binaries:
                    with self.subTest(option=option, value=value, binary=binary.name):
                        result, records, upstream, state = run_private_launch(
                            binary, scenario="exit-seven", codex_arguments=("exec", option, value),
                        )
                        self.assertEqual(result.returncode, 1, result.stderr)
                        self.assertEqual((result.stdout, records, upstream, state["leftovers"]), (b"", [], [], []))
                        self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                        outputs.append((result.returncode, result.stdout, result.stderr))
                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(outputs[1], outputs[2])

    def test_positional_rollout_budget_reminder_error_preserves_state_effects(self):
        self.assertEqual(hashlib.sha256(ORACLE_01651.read_bytes()).hexdigest(), ORACLE_01651_SHA256)
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        binaries = (ORACLE_01651, ORACLE, MODEX)
        expected_managed = {
            ORACLE_01651.resolve(): (
                {"state/profile-lifecycle.json.lock", "state/runtime-housekeeping.lock",
                 "state/update-check-codex-aligned-v1.json", "state/update-check.json"},
                {"state/runtime-housekeeping.last-run"},
            ),
            ORACLE.resolve(): (
                {"state/profile-lifecycle.json.lock", "state/runtime-housekeeping.lock",
                 "state/update-check.json"},
                {"state/runtime-housekeeping.last-run"},
            ),
            MODEX.resolve(): ({"state/update-check.json"}, set()),
        }
        for value in ("", "1,,2", "1,invalid,2"):
            with self.subTest(value=value):
                outputs = []
                for binary in binaries:
                    result, records, upstream, state = run_private_launch(
                        binary, scenario="exit-seven",
                        codex_arguments=(
                            "exec", "--rollout-budget-tokens", "100",
                            "--rollout-budget-reminders", value,
                        ),
                    )
                    self.assertEqual((result.returncode, result.stdout), (1, b""))
                    self.assertEqual(result.stderr, b"Error: expected comma-separated unsigned integers\n")
                    self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                    self.assertEqual((records, upstream, state["leftovers"]), ([], [], []))
                    required, optional = expected_managed[Path(binary).resolve()]
                    observed = set(state["managed"])
                    self.assertTrue(required <= observed, (str(binary), required, observed))
                    self.assertLessEqual(observed - required, optional, (str(binary), observed))
                    outputs.append((result.returncode, result.stdout, result.stderr))
                self.assertEqual(outputs[0], outputs[1])
                self.assertEqual(outputs[1], outputs[2])

        cases = (
            ("limit zero", (),
             ("exec", "--rollout-budget-tokens", "0", "--rollout-budget-reminders", "1,2", "synthetic prompt"), []),
            ("limit one", (),
             ("exec", "--rollout-budget-tokens", "1", "--rollout-budget-reminders", "1", "synthetic prompt"), []),
            ("limit two", (),
             ("exec", "--rollout-budget-tokens", "2", "--rollout-budget-reminders", "0,1,2", "synthetic prompt"),
             ["features.rollout_budget.enabled=true", "features.rollout_budget.limit_tokens=2",
              "features.rollout_budget.reminder_at_remaining_tokens=[1]"]),
            ("u64 max default", (),
             ("exec", "--rollout-budget-tokens", "18446744073709551615", "synthetic prompt"),
             ["features.rollout_budget.enabled=true", "features.rollout_budget.limit_tokens=18446744073709551615",
              "features.rollout_budget.reminder_at_remaining_tokens=[184467440737095516]"]),
            ("u64 near max default", (),
             ("exec", "--rollout-budget-tokens", "18446744073709551614", "synthetic prompt"),
             ["features.rollout_budget.enabled=true", "features.rollout_budget.limit_tokens=18446744073709551614",
              "features.rollout_budget.reminder_at_remaining_tokens=[184467440737095516]"]),
            ("all filtered", (),
             ("exec", "--rollout-budget-tokens", "100", "--rollout-budget-reminders", "0,100", "synthetic prompt"),
             ["features.rollout_budget.enabled=true", "features.rollout_budget.limit_tokens=100",
              "features.rollout_budget.reminder_at_remaining_tokens=[75,50,25]"]),
            ("repeated reminders", (),
             ("exec", "--rollout-budget-tokens", "10", "--rollout-budget-reminders", "1,2",
              "--rollout-budget-reminders", "2,4", "synthetic prompt"),
             ["features.rollout_budget.enabled=true", "features.rollout_budget.limit_tokens=10",
              "features.rollout_budget.reminder_at_remaining_tokens=[4,2,1]"]),
            ("repeated token limit", (),
             ("exec", "--rollout-budget-tokens", "10", "--rollout-budget-tokens", "20", "synthetic prompt"),
             ["features.rollout_budget.enabled=true", "features.rollout_budget.limit_tokens=20",
              "features.rollout_budget.reminder_at_remaining_tokens=[15,10,5]"]),
            ("pre-exec options", ("--rollout-budget-tokens", "100", "--rollout-budget-reminders", "1,2"),
             ("exec", "--", "synthetic prompt"),
             ["features.rollout_budget.enabled=true", "features.rollout_budget.limit_tokens=100",
              "features.rollout_budget.reminder_at_remaining_tokens=[2,1]"]),
            ("post-exec options", (),
             ("exec", "--rollout-budget-tokens", "100", "--rollout-budget-reminders", "1,2", "synthetic prompt"),
             ["features.rollout_budget.enabled=true", "features.rollout_budget.limit_tokens=100",
              "features.rollout_budget.reminder_at_remaining_tokens=[2,1]"]),
            ("user config order", (),
             ("exec", "-c", "features.rollout_budget.enabled=false", "--rollout-budget-tokens", "100",
              "--rollout-budget-reminders", "1,2", "-c", "features.rollout_budget.limit_tokens=9",
              "--", "literal prompt", "--rollout-budget-tokens=4"),
             ["features.rollout_budget.enabled=true", "features.rollout_budget.limit_tokens=100",
              "features.rollout_budget.reminder_at_remaining_tokens=[2,1]",
              "features.rollout_budget.enabled=false", "features.rollout_budget.limit_tokens=9"]),
            ("reminders without limit", (),
             ("exec", "--rollout-budget-reminders", "1,2", "synthetic prompt"), []),
        )
        for case, super_arguments, codex_arguments, expected_config in cases:
            normalized_launches = []
            for binary in binaries:
                with self.subTest(case=case, binary=binary.name):
                    result, records, upstream, state = run_private_launch(
                        binary, scenario="exit-seven", super_arguments=super_arguments,
                        codex_arguments=codex_arguments,
                    )
                    if case == "user config order" and binary == MODEX:
                        self.assertEqual((result.returncode, result.stdout), (1, b""))
                        self.assertIn(b"Super startup is not implemented", result.stderr)
                        self.assertNotIn(b"expected comma-separated unsigned integers", result.stderr)
                        self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                        self.assertEqual((records, upstream, state["leftovers"]), ([], [], []))
                        self.assertEqual(state["managed"], ["state/update-check.json"])
                        continue
                    launch = next(record for record in records if record["kind"] == "launch")
                    actual_config = [arg for arg in launch["args"] if arg.startswith("features.rollout_budget.")]
                    normalized_args = normalized_app_server_args(launch["args"])
                    self.assertEqual((result.returncode, result.stdout), (7, b""))
                    self.assertEqual(actual_config, expected_config)
                    self.assertNotIn("--rollout-budget-tokens", launch["args"])
                    self.assertNotIn("--rollout-budget-reminders", launch["args"])
                    self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                    self.assertEqual((upstream, state["leftovers"]), ([], []))
                    if case == "user config order":
                        self.assertEqual(normalized_args[-7:], [
                            "-c", "features.rollout_budget.enabled=false", "-c",
                            "features.rollout_budget.limit_tokens=9", "--", "literal prompt",
                            "--rollout-budget-tokens=4",
                        ])
                    normalized_launches.append(normalized_args)
            self.assertEqual(normalized_launches[0], normalized_launches[1])
            if case == "user config order":
                self.assertEqual(len(normalized_launches), 2)
            else:
                self.assertEqual(normalized_launches[1], normalized_launches[2])

    def test_unavailable_startup_fails_before_side_effects_and_keeps_keys_private(self):
        sentinel = "synthetic-key-never-print-this"
        for arguments in (
            ["super"],
            ["s", "--provider", "deepseek", "--api-key", sentinel, "exec", "fixture prompt"],
            ["super", "--dry-run", "--url", "http://127.0.0.1:8131"],
        ):
            with self.subTest(arguments=arguments):
                result, mutated = isolated_super(MODEX, arguments)
                self.assertEqual((result.returncode, result.stdout), (1, b""))
                self.assertIn(b"Super startup is not implemented", result.stderr)
                self.assertNotIn(sentinel.encode(), result.stderr)
                self.assertFalse(mutated)


if __name__ == "__main__":
    unittest.main()
