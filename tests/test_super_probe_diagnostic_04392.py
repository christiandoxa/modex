"""Codex probe diagnostics against the pinned 0.439.2 release."""

import hashlib
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
            result, records, upstream, state = launch_support.run_private_launch(
                binary,
                scenario="exit-seven",
                environment_overrides={"MODEX_TEST_CODEX_VERSION_OVERSIZE": "1"},
            )
            diagnostic = launch_support.normalized_codex_path(result.stderr).splitlines()[-1:]
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

    def test_oversized_app_server_help_probe_matches_reference_context(self):
        observations = []
        for binary in (test_cli.ORACLE, launch_support.MODEX):
            result, records, upstream, state = launch_support.run_private_launch(
                binary,
                scenario="exit-seven",
                environment_overrides={"MODEX_TEST_CODEX_HELP_OVERSIZE": "1"},
            )
            diagnostic = launch_support.normalized_codex_path(result.stderr).splitlines()[-1:]
            self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
            self.assertEqual(
                [record["args"] for record in records if record["kind"] == "probe"],
                [["--version"], ["app-server", "--help"]],
            )
            self.assertEqual((upstream, state["leftovers"]), ([], []))
            observations.append(diagnostic)

        expected = [
            b"Error: failed to probe Codex CLI at <CODEX>: "
            b"Codex app-server capability probe output exceeded the limit"
        ]
        self.assertEqual(observations, [expected, expected])

    def test_minimum_codex_version_remains_04392_compatible(self):
        cases = (
            ({"MODEX_TEST_CODEX_VERSION": "codex-cli 0.153.1"}, False),
            ({"MODEX_TEST_CODEX_VERSION": "codex 0.+153.2"}, True),
            ({"MODEX_TEST_CODEX_VERSION": "codex 0.153.+2"}, True),
            ({
                "MODEX_TEST_CODEX_VERSION": "Codex CLI 0.153.2!",
                "MODEX_TEST_CODEX_VERSION_STDERR": "1",
            }, True),
        )
        for environment, accepted in cases:
            with self.subTest(environment=environment):
                diagnostics = []
                for binary in (test_cli.ORACLE, launch_support.MODEX):
                    result, records, upstream, state = launch_support.run_private_launch(
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
                            launch_support.normalized_codex_path(result.stderr)
                            .splitlines()[-1]
                        )
                if not accepted:
                    self.assertEqual(diagnostics[0], diagnostics[1])

    def test_nonzero_version_probe_matches_04392(self):
        diagnostics = []
        for binary in (test_cli.ORACLE, launch_support.MODEX):
            result, records, upstream, state = launch_support.run_private_launch(
                binary,
                scenario="exit-seven",
                environment_overrides={"MODEX_TEST_CODEX_VERSION_EXIT": "7"},
            )
            self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
            self.assertEqual([record["kind"] for record in records], ["probe"])
            self.assertEqual(records[0]["args"], ["--version"])
            self.assertEqual((upstream, state["leftovers"]), ([], []))
            diagnostics.append(
                launch_support.normalized_codex_path(result.stderr)
                .splitlines()[-1]
            )
        self.assertEqual(diagnostics[0], diagnostics[1])
        self.assertIn(b"Codex version probe failed for <CODEX> with status 7.", diagnostics[0])
