"""Compare production Super hook-trust identity with the verified 0.165.1 oracle."""

import hashlib
import unittest

from test_cli import MODEX
from test_cli_01651 import ORACLE, ORACLE_SHA256
import test_super_launch


class AppServerRpc01651Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 Linux release")

    def test_production_initialize_client_info_matches_oracle(self):
        suite = test_super_launch.SuperLaunchTests()
        baseline, baseline_records, baseline_upstream, _ = suite.run_launch(
            binary=ORACLE, scenario="buffered"
        )
        modex, modex_records, modex_upstream, _ = suite.run_launch(
            binary=MODEX, scenario="buffered"
        )

        def client_info(records):
            requests = [
                record["params"]["clientInfo"]
                for record in records
                if record.get("kind") == "request" and record.get("method") == "initialize"
            ]
            if len(requests) != 1:
                raise AssertionError(f"expected one app-server initialize request, got {len(requests)}")
            return requests[0]

        self.assertEqual((baseline.returncode, modex.returncode), (0, 0))
        self.assertEqual((len(baseline_upstream), len(modex_upstream)), (1, 1))
        self.assertEqual(
            test_super_launch.normalized_codex_path(baseline.stderr),
            test_super_launch.normalized_codex_path(modex.stderr),
        )
        self.assertNotIn(b"synthetic-provider-key", baseline.stdout + baseline.stderr + modex.stdout + modex.stderr)
        self.assertEqual(
            client_info(baseline_records),
            {"name": "prodex-hook-trust", "version": "0.165.1"},
        )
        self.assertEqual(client_info(modex_records), client_info(baseline_records))

    def test_closed_app_server_stdin_reports_reference_broken_pipe(self):
        suite = test_super_launch.SuperLaunchTests()
        baseline, baseline_records, baseline_upstream, baseline_state = suite.run_launch(
            binary=ORACLE, scenario="closed-input"
        )
        modex, modex_records, modex_upstream, modex_state = suite.run_launch(
            binary=MODEX, scenario="closed-input"
        )
        expected = "Error: Broken pipe (os error 32)"

        def request_methods(records):
            return [
                record["method"]
                for record in records
                if record.get("kind") == "request"
            ]

        self.assertEqual((baseline.returncode, modex.returncode), (1, 1))
        self.assertEqual((baseline.stdout, modex.stdout), (b"", b""))
        self.assertEqual((baseline_upstream, modex_upstream), ([], []))
        self.assertEqual((baseline_state["leftovers"], modex_state["leftovers"]), ([], []))
        self.assertEqual(
            test_super_launch.normalized_codex_path(baseline.stderr),
            test_super_launch.normalized_codex_path(modex.stderr),
        )
        self.assertEqual((request_methods(baseline_records), request_methods(modex_records)),
                         (["initialize"], ["initialize"]))
        self.assertEqual(baseline.stderr.decode().splitlines()[-1], expected)
        self.assertEqual(modex.stderr.decode().splitlines()[-1], expected)

    def test_closed_app_server_stdout_reports_reference_channel_error(self):
        suite = test_super_launch.SuperLaunchTests()
        baseline, baseline_records, baseline_upstream, baseline_state = suite.run_launch(
            binary=ORACLE, scenario="closed-output"
        )
        modex, modex_records, modex_upstream, modex_state = suite.run_launch(
            binary=MODEX, scenario="closed-output"
        )
        expected = (
            "Error: Codex hook-trust preflight initialize failed: "
            "channel is empty and sending half is closed"
        )

        def request_methods(records):
            return [record["method"] for record in records if record.get("kind") == "request"]

        self.assertEqual((baseline.returncode, modex.returncode), (1, 1))
        self.assertEqual((baseline.stdout, modex.stdout), (b"", b""))
        self.assertEqual((baseline_upstream, modex_upstream), ([], []))
        self.assertEqual((baseline_state["leftovers"], modex_state["leftovers"]), ([], []))
        self.assertEqual(
            test_super_launch.normalized_codex_path(baseline.stderr),
            test_super_launch.normalized_codex_path(modex.stderr),
        )
        self.assertEqual((request_methods(baseline_records), request_methods(modex_records)),
                         (["initialize"], ["initialize"]))
        self.assertEqual(baseline.stderr.decode().splitlines()[-1], expected)
        self.assertEqual(modex.stderr.decode().splitlines()[-1], expected)

    def test_invalid_app_server_stdout_utf8_reports_reference_stream_error(self):
        suite = test_super_launch.SuperLaunchTests()
        expected = "Error: Codex hook-trust preflight stdout failed: stream did not contain valid UTF-8"
        for scenario, expected_methods in (
            ("invalid-utf8", ["initialize"]),
            ("invalid-utf8-later", ["initialize", "hooks/list"]),
        ):
            with self.subTest(scenario=scenario):
                baseline, baseline_records, baseline_upstream, baseline_state = suite.run_launch(
                    binary=ORACLE, scenario=scenario
                )
                modex, modex_records, modex_upstream, modex_state = suite.run_launch(
                    binary=MODEX, scenario=scenario
                )

                def request_methods(records):
                    return [record["method"] for record in records if record.get("kind") == "request"]

                self.assertEqual((baseline.returncode, modex.returncode), (1, 1))
                self.assertEqual((baseline.stdout, modex.stdout), (b"", b""))
                self.assertEqual((baseline_upstream, modex_upstream), ([], []))
                self.assertEqual((baseline_state["leftovers"], modex_state["leftovers"]), ([], []))
                self.assertEqual(
                    test_super_launch.normalized_codex_path(baseline.stderr),
                    test_super_launch.normalized_codex_path(modex.stderr),
                )
                self.assertEqual((request_methods(baseline_records), request_methods(modex_records)),
                                 (expected_methods, expected_methods))
                self.assertEqual(baseline.stderr.decode().splitlines()[-1], expected)
                self.assertEqual(modex.stderr.decode().splitlines()[-1], expected)

    def test_split_utf8_frame_ignores_malformed_and_unmatched_noise(self):
        suite = test_super_launch.SuperLaunchTests()
        responses = []
        methods = []
        stderr_outputs = []
        for binary in (ORACLE, MODEX):
            result, records, upstream, state = suite.run_launch(
                binary=binary, scenario="split-utf8-noise"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, b"synthetic-client-complete\n")
            self.assertEqual(len(upstream), 1)
            self.assertEqual(state["leftovers"], [])
            responses.append(result.stdout)
            methods.append([record["method"] for record in records if record.get("kind") == "request"])
            stderr_outputs.append(test_super_launch.normalized_codex_path(result.stderr))
        self.assertEqual(responses[0], responses[1])
        self.assertEqual(methods, [["initialize", "hooks/list", "hooks/list"]] * 2)
        self.assertEqual(stderr_outputs[0], stderr_outputs[1])


if __name__ == "__main__":
    unittest.main()
