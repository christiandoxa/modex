"""Compare combo-model production requests with the checksum-pinned Prodex release."""

import hashlib
import json
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns


class ProviderRequestPrepareTests(unittest.TestCase):
    def test_combo_model_matches_release_on_synthetic_loopback(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        cases = [("flash", "deepseek-v4-flash"),
                 ("deepseek-flash", "deepseek-flash"),
                 ("deepseek-v4-flash", "deepseek-v4-flash"),
                 ("combo:flash,auto", "deepseek-v4-flash"),
                 ("combo:pro;flash", "deepseek-v4-pro"),
                 ("combo: ;AUTO|flash", "deepseek-v4-pro"),
                 (" combo:\u2003; Flash>pro ", "deepseek-v4-flash"),
                 ("combo:; custom-model|flash", "custom-model"),
                 ("COMBO:flash,pro", "COMBO:flash,pro"),
                 ("combo:,,,", "combo:,,,"), ("combo:", "combo:")]
        turns = [{"model": model, "input": "synthetic model selector"} for model, _ in cases]
        replies = [buffered_reply(index, created=42) for index in range(len(turns))]
        observed = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(binary, turns, replies)
            self.assertEqual(len(upstream), len(turns))
            self.assertEqual([response["status"] for response in responses], [200] * len(turns))
            bodies = [json.loads(record["body"]) for record in upstream]
            self.assertEqual([body["model"] for body in bodies], [expected for _, expected in cases])
            for record in upstream:
                self.assertEqual(record["path"], "/v1/chat/completions")
                self.assertEqual(record["headers"]["authorization"], "Bearer synthetic-provider-key")
            observed.append(bodies)
        self.assertEqual(*observed)


if __name__ == "__main__":
    unittest.main()
