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
