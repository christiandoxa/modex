"""Compare eight-client slow-partial admission through real isolated processes."""

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

    def test_eight_incomplete_headers_reproduce_runtime_mismatch(self):
        harness = test_super_launch.SuperLaunchTests()
        for version, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            for workers in (None, 1):
                with self.subTest(version=version, workers=workers):
                    environment = {} if workers is None else {
                        "PRODEX_RUNTIME_PROXY_WORKER_COUNT": str(workers),
                    }
                    baseline, baseline_records, baseline_upstream, _ = harness.run_launch(
                        binary=oracle, scenario="slow-partial", environment_overrides=environment,
                    )
                    modex, modex_records, modex_upstream, _ = harness.run_launch(
                        binary=MODEX, scenario="slow-partial", environment_overrides=environment,
                    )

                    baseline_probe = next(row for row in baseline_records if row["kind"] == "slow-partial")
                    modex_probe = next(row for row in modex_records if row["kind"] == "slow-partial")
                    for result, upstream in (
                        (baseline, baseline_upstream), (modex, modex_upstream),
                    ):
                        self.assertEqual((result.returncode, result.stdout),
                                         (0, b"synthetic-client-complete\n"), result.stderr)
                        self.assertEqual(len(upstream), 1)
                        self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
                        self.assertEqual(
                            {key.lower(): value for key, value in upstream[0]["headers"].items()}[
                                "authorization"
                            ],
                            "Bearer synthetic-provider-key",
                        )
                    self.assertEqual((baseline_probe["clients"], baseline_probe["hold_ms"]), (8, 1000))
                    self.assertTrue(baseline_probe["responded_before_release"], baseline_probe)
                    self.assertEqual(baseline_probe["before_release_status"], 200)
                    self.assertEqual(modex_probe["clients"], 8)
                    self.assertEqual(modex_probe["hold_ms"], 1000)
                    self.assertEqual(modex_probe["status"], 200)


if __name__ == "__main__":
    unittest.main()
