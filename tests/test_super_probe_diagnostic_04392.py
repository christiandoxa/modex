"""Oversized Codex probe diagnostics against the pinned 0.439.2 release."""

import hashlib
import re
import unittest

import test_cli
import test_super_launch as launch_support


class SuperProbeDiagnostic04392Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (
            not test_cli.ORACLE.is_file()
            or hashlib.sha256(test_cli.ORACLE.read_bytes()).hexdigest()
            != test_cli.ORACLE_SHA256
        ):
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.439.2 Linux release")
        if not launch_support.MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def test_oversized_version_probe_matches_reference_context(self):
        observations = []
        for binary in (test_cli.ORACLE, launch_support.MODEX):
            result, records, upstream, state = launch_support.SuperLaunchTests().run_launch(
                binary,
                scenario="exit-seven",
                environment_overrides={"MODEX_TEST_CODEX_VERSION_OVERSIZE": "1"},
            )
            diagnostic = re.sub(
                rb"/tmp/modex-super-launch-[^/]+/codex", b"<CODEX>", result.stderr
            ).splitlines()[-1:]
            self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
            self.assertEqual(
                [record["args"] for record in records if record["kind"] == "probe"],
                [["--version"]],
            )
            self.assertEqual((upstream, state["leftovers"]), ([], []))
            observations.append(diagnostic)

        expected = [
            b"Error: failed to probe Codex CLI at <CODEX>: "
            b"Codex version probe output exceeded the limit"
        ]
        self.assertEqual(observations, [expected, expected])
