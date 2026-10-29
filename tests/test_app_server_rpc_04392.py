"""Compare production hook-trust identity with the 0.439.2 release."""

import hashlib
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
import test_super_launch


class AppServerRpc04392Tests(unittest.TestCase):
    def test_initialize_client_info_matches_release(self):
        if not MODEX.is_file():
            self.fail("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            self.fail("PRODEX_ORACLE must identify the verified 0.439.2 Linux release")
        observed = []
        for binary in (ORACLE, MODEX):
            result, records, upstream, state = test_super_launch.SuperLaunchTests().run_launch(
                binary=binary, scenario="buffered"
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(upstream), 1)
            self.assertEqual(state["leftovers"], [])
            requests = [record["params"]["clientInfo"] for record in records
                        if record.get("kind") == "request" and record.get("method") == "initialize"]
            self.assertEqual(len(requests), 1)
            observed.append(requests[0])
        self.assertEqual(observed, [{"name": "prodex-hook-trust", "version": "0.439.2"}] * 2)


if __name__ == "__main__":
    unittest.main()
