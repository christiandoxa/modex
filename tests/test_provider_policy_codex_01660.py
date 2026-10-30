"""Pass an upstream policy-capacity 503 through the active Super process."""

import hashlib
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256


POLICY_BODY = b'{"error":{"code":"policy_capacity_unavailable","message":"synthetic policy capacity"}}'


class ProviderPolicyCodex01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 Linux release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")

    def test_policy_capacity_503_reaches_synthetic_codex_unchanged(self):
        from test_super_launch import SuperLaunchTests

        observations = []
        for binary in (ORACLE, MODEX):
            with self.subTest(binary="Prodex" if binary == ORACLE else "Modex"):
                result, records, upstream, state = SuperLaunchTests().run_launch(
                    binary=binary,
                    scenario="policy-capacity-503",
                )
                response = next(record for record in records if record.get("kind") == "response")
                initialize = [
                    record["params"]["clientInfo"]
                    for record in records
                    if record.get("kind") == "request" and record.get("method") == "initialize"
                ]

                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(len(upstream), 1, "the synthetic client request must not be replayed")
                self.assertEqual(response["status"], 503)
                self.assertEqual(response["headers"]["content-type"], "application/json")
                self.assertEqual(bytes.fromhex(response["body"]), POLICY_BODY)
                self.assertEqual(initialize, [{"name": "prodex-hook-trust", "version": "0.166.0"}])
                self.assertEqual(state["leftovers"], [])
                self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                observations.append((
                    response["status"], response["headers"]["content-type"], response["body"],
                ))

        self.assertEqual(observations[0], observations[1])


if __name__ == "__main__":
    unittest.main()
