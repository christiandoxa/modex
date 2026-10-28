"""Active 0.165.1 reference checks for the production Codex probes."""

import hashlib
import re
import unittest

import test_cli_01651 as active_cli
import test_super_launch as launch_support


PROBE_ENVIRONMENT = (
    "CODEX_HOME",
    "TEST_CODEX_LOG",
    "TEST_CODEX_LOG_APPEND",
    "TEST_CODEX_ARGS_LOG",
    "TEST_CODEX_ARGS_LOG_APPEND",
    "TEST_CODEX_STDIN_LOG",
)
SENTINEL_ENVIRONMENT = {
    name: f"synthetic-probe-sentinel-{name.lower()}" for name in PROBE_ENVIRONMENT
}


class ActiveSuperLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not active_cli.ORACLE.is_file() or hashlib.sha256(active_cli.ORACLE.read_bytes()).hexdigest() != active_cli.ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 Linux release")
        if not launch_support.MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def test_probe_failure_and_environment_match_01651(self):
        observations = []
        for binary in (active_cli.ORACLE, launch_support.MODEX):
            with self.subTest(binary=binary.name):
                result, records, upstream, state = launch_support.SuperLaunchTests().run_launch(
                    binary,
                    scenario="app-server-help-failure",
                    environment_overrides=SENTINEL_ENVIRONMENT,
                )
                self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
                self.assertEqual([record["kind"] for record in records], ["probe", "probe"])
                probes = [record for record in records if record["kind"] == "probe"]
                self.assertEqual([record["args"] for record in probes], [
                    ["--version"], ["app-server", "--help"],
                ])
                self.assertEqual(
                    [record["environment"] for record in probes],
                    [{name: None for name in PROBE_ENVIRONMENT}] * 2,
                )
                self.assertEqual((upstream, state["leftovers"]), ([], []))
                observations.append(
                    re.sub(rb"/tmp/modex-super-launch-[^/]+/codex", b"<CODEX>", result.stderr)
                    .splitlines()[-1]
                )

        expected = (
            b"Error: Codex app-server capability probe failed for <CODEX> with status 7. "
            b"Install or update the official Codex CLI with `npm install -g @openai/codex@latest` "
            b"(https://developers.openai.com/codex/cli), verify `codex --version`, or set "
            b"PRODEX_CODEX_BIN to its executable path. Prodex accepts compatible Codex releases "
            b"at or above its minimum capability baseline; the latest stable release is recommended."
        )
        self.assertEqual(observations, [expected, expected])

    def test_minimum_codex_version_matches_01651(self):
        cases = (
            ({"MODEX_TEST_CODEX_VERSION": "codex-cli 0.153.1"}, False),
            ({
                "MODEX_TEST_CODEX_VERSION": "Codex CLI 0.153.2!",
                "MODEX_TEST_CODEX_VERSION_STDERR": "1",
            }, True),
        )
        for environment, accepted in cases:
            with self.subTest(environment=environment):
                diagnostics = []
                for binary in (active_cli.ORACLE, launch_support.MODEX):
                    result, records, upstream, state = launch_support.SuperLaunchTests().run_launch(
                        binary,
                        scenario="exit-seven",
                        environment_overrides=environment,
                    )
                    probes = [record["args"] for record in records if record["kind"] == "probe"]
                    self.assertEqual((upstream, state["leftovers"]), ([], []))
                    if accepted:
                        self.assertEqual((result.returncode, result.stdout), (7, b""), result.stderr)
                        self.assertEqual(probes, [["--version"], ["app-server", "--help"]])
                        self.assertTrue(any(record["kind"] == "launch" for record in records))
                    else:
                        self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
                        self.assertEqual(probes, [["--version"]])
                        self.assertEqual([record["kind"] for record in records], ["probe"])
                        self.assertIn(b"requires 0.153.2 or newer", result.stderr)
                        diagnostics.append(
                            re.sub(rb"/tmp/modex-super-launch-[^/]+/codex", b"<CODEX>", result.stderr)
                            .splitlines()[-1]
                        )
                if not accepted:
                    self.assertEqual(diagnostics[0], diagnostics[1])

    def test_oversized_probe_capture_matches_01651(self):
        cases = (
            ({"MODEX_TEST_CODEX_VERSION_OVERSIZE": "1"}, [["--version"]], "Codex version probe"),
            ({"MODEX_TEST_CODEX_HELP_OVERSIZE": "1"},
             [["--version"], ["app-server", "--help"]], "Codex app-server capability probe"),
        )
        for environment, expected_probes, label in cases:
            with self.subTest(environment=environment):
                diagnostics = []
                for binary in (active_cli.ORACLE, launch_support.MODEX):
                    result, records, upstream, state = launch_support.SuperLaunchTests().run_launch(
                        binary,
                        scenario="exit-seven",
                        environment_overrides=environment,
                    )
                    self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
                    self.assertEqual(
                        [record["args"] for record in records if record["kind"] == "probe"],
                        expected_probes,
                    )
                    self.assertEqual((upstream, state["leftovers"]), ([], []))
                    diagnostics.append(
                        re.sub(rb"/tmp/modex-super-launch-[^/]+/codex", b"<CODEX>", result.stderr)
                        .splitlines()[-1]
                    )
                expected = (
                    b"Error: failed to probe Codex CLI at <CODEX>: "
                    + label.encode()
                    + b" output exceeded the limit"
                )
                self.assertEqual(diagnostics, [expected, expected])
