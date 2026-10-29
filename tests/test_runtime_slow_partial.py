"""Compare slow-request admission through isolated real Super processes."""

import hashlib
import os
from pathlib import Path
import unittest

from test_cli import MODEX
import test_super_launch


REFERENCE_CACHE = Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651", REFERENCE_CACHE / "oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
ORACLE_04392 = Path(os.environ.get(
    "PRODEX_ORACLE_04392", os.environ.get(
        "PRODEX_ORACLE", REFERENCE_CACHE / "oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
    ),
))
ORACLE_04392_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"


class RuntimeSlowPartialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Modex binary has not been built: {MODEX}")
        for label, path, expected in (
            ("Prodex 0.165.1", ORACLE_01651, ORACLE_01651_SHA256),
            ("Prodex 0.439.2", ORACLE_04392, ORACLE_04392_SHA256),
        ):
            if not path.is_file():
                raise AssertionError(f"Pinned {label} oracle is missing: {path}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                raise AssertionError(f"{label} oracle SHA-256 mismatch: {actual}")

    def _run(self, harness, scenario, binary, environment=None):
        result, records, upstream, _ = harness.run_launch(
            binary=binary, scenario=scenario, environment_overrides=environment,
        )
        self.assertEqual((result.returncode, result.stdout),
                         (0, b"synthetic-client-complete\n"), result.stderr)
        probe = next(row for row in records if row["kind"] == scenario)
        expected_upstreams = 4 if scenario == "slow-partial-overflow-completes" else 1
        if scenario in (
            "slow-partial-body-limit", "truncated-header-eof",
            "truncated-body-eof", "truncated-small-body-eof", "empty-request-body",
        ):
            self.assertEqual(upstream, [])
        else:
            self.assertEqual(len(upstream), expected_upstreams)
            for row in upstream:
                self.assertEqual(row["path"], "/v1/chat/completions")
                self.assertEqual(
                    {key.lower(): value for key, value in row["headers"].items()}[
                        "authorization"
                    ],
                    "Bearer synthetic-provider-key",
                )
        return probe

    @staticmethod
    def _signature(scenario, probe):
        if scenario == "slow-partial":
            return (
                probe["responded_before_release"],
                probe["before_release_status"],
                probe["status"],
            )
        if scenario == "slow-partial-body":
            return (
                probe["responded_before_release"],
                probe["before_release_status"],
                probe["cancelled_status"],
                probe["status"],
            )
        if scenario == "slow-partial-fragmented-header":
            return probe["fragments"], probe["status"]
        if scenario == "slow-partial-flood":
            return (
                probe["partial_clients"],
                probe["before_release_status"],
                probe["status"],
            )
        if scenario == "slow-partial-overflow-completes":
            return (
                probe["freed_parked_status"],
                probe["completed_overflow_status"],
                probe["reused_overflow_status"],
                probe["healthy_status"],
            )
        if scenario in ("truncated-header-eof", "empty-request-body"):
            return probe["status"]
        if scenario in ("truncated-body-eof", "truncated-small-body-eof"):
            return probe["status"], probe["body"]
        return probe["declared_bytes"], probe["status"]

    def _compare(self, scenario, environment=None):
        harness = test_super_launch.SuperLaunchTests()
        references = {
            "0.165.1": self._run(harness, scenario, ORACLE_01651, environment),
            "0.439.2": self._run(harness, scenario, ORACLE_04392, environment),
        }
        expected = self._signature(scenario, references["0.165.1"])
        self.assertEqual(self._signature(scenario, references["0.439.2"]), expected)
        modex = self._run(harness, scenario, MODEX, environment)
        return expected, modex

    def test_incomplete_headers_do_not_block_ready_requests(self):
        for workers in (None, 1):
            with self.subTest(workers=workers):
                environment = {} if workers is None else {
                    "PRODEX_RUNTIME_PROXY_WORKER_COUNT": str(workers),
                }
                signature, modex = self._compare("slow-partial", environment)
                self.assertEqual(signature, (True, 200, 200))
                self.assertEqual(self._signature("slow-partial", modex), signature)

    def test_partial_header_overflow_queue_keeps_later_clients_moving(self):
        for count in (127, 128, 129):
            with self.subTest(partial_clients=count):
                environment = {"MODEX_SLOW_PARTIAL_HEADER_COUNT": str(count)}
                signature, modex = self._compare("slow-partial-flood", environment)
                self.assertEqual(signature, (count, 200, 200))
                self.assertEqual(self._signature("slow-partial-flood", modex), signature)

    def test_incomplete_overflow_heads_remain_open_and_complete_fairly(self):
        environment = {"MODEX_SLOW_PARTIAL_HEADER_COUNT": "130"}
        signature, modex = self._compare("slow-partial-overflow-completes", environment)
        self.assertEqual(signature, (200, 200, 200, 200))
        self.assertEqual(self._signature("slow-partial-overflow-completes", modex), signature)

    def test_bounded_overflow_flood_preserves_eventual_success(self):
        environment = {"MODEX_SLOW_PARTIAL_HEADER_COUNT": "136"}
        signature, modex = self._compare("slow-partial-flood", environment)
        self.assertEqual(signature[0], 136)
        self.assertEqual(signature[1:], (200, 200))
        modex_signature = self._signature("slow-partial-flood", modex)
        self.assertEqual(modex_signature[0], 136)
        self.assertEqual(modex_signature[2], 200)

    def test_incomplete_bodies_hold_workers_until_client_cancellation(self):
        signature, modex = self._compare("slow-partial-body")
        self.assertEqual(signature, (False, None, 502, 200))
        self.assertEqual(self._signature("slow-partial-body", modex), signature)

    def test_configured_worker_count_controls_incomplete_body_admission(self):
        for workers in (1, 2):
            with self.subTest(workers=workers):
                environment = {
                    "PRODEX_RUNTIME_PROXY_WORKER_COUNT": str(workers),
                    "MODEX_SLOW_PARTIAL_BODY_COUNT": str(workers),
                }
                signature, modex = self._compare("slow-partial-body", environment)
                self.assertEqual(signature, (False, None, 502, 200))
                self.assertEqual(self._signature("slow-partial-body", modex), signature)

    def test_truncated_headers_still_close_without_a_response(self):
        signature, modex = self._compare("truncated-header-eof")
        self.assertIsNone(signature)
        self.assertIsNone(modex["status"])

    def test_truncated_deferred_body_matches_release_error(self):
        signature, modex = self._compare("truncated-body-eof")
        self.assertEqual(signature, (502, b"upstream request failed".hex()))
        self.assertEqual(self._signature("truncated-body-eof", modex), signature)

    def test_truncated_body_at_defer_threshold_still_closes_silently(self):
        signature, modex = self._compare("truncated-small-body-eof")
        self.assertEqual(signature, (None, ""))
        self.assertEqual(self._signature("truncated-small-body-eof", modex), signature)

    def test_empty_body_is_not_classified_as_truncated(self):
        signature, modex = self._compare("empty-request-body")
        self.assertIsNotNone(signature)
        self.assertEqual(modex["status"], signature)

    def test_fragmented_header_completes_and_dispatches(self):
        signature, modex = self._compare("slow-partial-fragmented-header")
        self.assertEqual(signature, (5, 200))
        self.assertEqual(modex["status"], 200)

    def test_oversized_declared_body_is_rejected_before_body_read(self):
        signature, modex = self._compare("slow-partial-body-limit")
        self.assertEqual(signature, (64 * 1024 * 1024 + 1, 413))
        self.assertEqual(modex["status"], 413)

    def _run_request_head(self, scenario, binary):
        harness = test_super_launch.SuperLaunchTests()
        result, records, upstream, _ = harness.run_launch(binary=binary, scenario=scenario)
        self.assertEqual((result.returncode, result.stdout),
                         (0, b"synthetic-client-complete\n"), result.stderr)
        probe = next(row for row in records if row["kind"] == scenario)
        return probe, upstream

    def _assert_provider_upstreams(self, upstream, count, label):
        self.assertEqual(len(upstream), count, label)
        for row in upstream:
            self.assertEqual(row["path"], "/v1/chat/completions", label)
            self.assertEqual(
                {key.lower(): value for key, value in row["headers"].items()}["authorization"],
                "Bearer synthetic-provider-key",
                label,
            )

    def test_80k_complete_header_is_captured_without_per_chunk_admission_delay(self):
        observations = []
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            with self.subTest(binary=label):
                probe, upstream = self._run_request_head("request-head-80k", binary)
                self.assertEqual((probe["head_bytes"], probe["status"], probe["fragments"]),
                                 (80 * 1024, 200, 1), label)
                self.assertLess(probe["elapsed_ms"], 1000, (label, probe))
                self._assert_provider_upstreams(upstream, 1, label)
                observations.append(probe)
        self.assertEqual(
            [(row["head_bytes"], row["status"]) for row in observations],
            [(80 * 1024, 200)] * 3,
        )

    def test_fragmented_two_mib_header_yields_to_healthy_request(self):
        observations = []
        for label, binary in (
            ("0.165.1", ORACLE_01651),
            ("0.439.2", ORACLE_04392),
            ("Modex", MODEX),
        ):
            with self.subTest(binary=label):
                probe, upstream = self._run_request_head(
                    "request-head-near-limit-fragmented", binary,
                )
                self.assertEqual((probe["head_bytes"], probe["fragment_bytes"], probe["fragments"]),
                                 (2 * 1024 * 1024, 512, 4097), label)
                self.assertEqual((probe["status"], probe["healthy_status"]), (200, 200), label)
                self.assertTrue(probe["healthy_before_large_complete"], (label, probe))
                self.assertLess(probe["healthy_elapsed_ms"], 750, (label, probe))
                self.assertLess(probe["large_header_complete_ms"], 5000, (label, probe))
                self._assert_provider_upstreams(upstream, 2, label)
                observations.append(probe)
        self.assertEqual(
            [(row["head_bytes"], row["status"], row["healthy_status"]) for row in observations],
            [(2 * 1024 * 1024, 200, 200)] * 3,
        )

    def test_header_limit_boundary_matches_releases_and_records_over_limit_gap(self):
        releases = []
        for label, binary in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            with self.subTest(binary=label):
                probe, upstream = self._run_request_head("request-head-over-limit", binary)
                self.assertEqual((probe["head_bytes"], probe["status"]),
                                 (2 * 1024 * 1024 + 1, 200), label)
                self._assert_provider_upstreams(upstream, 1, label)
                releases.append(probe)
        self.assertEqual([row["status"] for row in releases], [200, 200])

        modex, upstream = self._run_request_head("request-head-over-limit", MODEX)
        self.assertEqual(modex["head_bytes"], 2 * 1024 * 1024 + 1)
        self.assertIn(modex["status"], (200, 502))
        self._assert_provider_upstreams(upstream, 1 if modex["status"] == 200 else 0, "Modex")


if __name__ == "__main__":
    unittest.main()
