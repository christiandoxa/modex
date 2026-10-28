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
            client_info(baseline_records),
            {"name": "prodex-hook-trust", "version": "0.165.1"},
        )
        self.assertEqual(client_info(modex_records), client_info(baseline_records))


if __name__ == "__main__":
    unittest.main()
