"""Compare combo-model production requests with the checksum-pinned Prodex release."""

import hashlib
import json
import os
from pathlib import Path
import unittest

from test_cli import MODEX
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as ORACLE_01651_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns

ORACLE_04392 = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    Path.home() / ".cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_04392_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"


class ProviderRequestPrepareTests(unittest.TestCase):
    def test_combo_model_matches_release_on_synthetic_loopback(self):
        for oracle, digest in ((ORACLE_01651, ORACLE_01651_SHA256), (ORACLE_04392, ORACLE_04392_SHA256)):
            self.assertEqual(hashlib.sha256(oracle.read_bytes()).hexdigest(), digest)
        cases = [("flash", "deepseek-flash"),
                 ("deepseek-flash", "deepseek-flash"),
                 ("deepseek-v4-flash", "deepseek-v4-flash"),
                 ("combo:flash,auto", "deepseek-flash"),
                 ("combo:pro;flash", "deepseek-v4-pro"),
                 ("combo: ;AUTO|flash", "deepseek-v4-pro"),
                 (" combo:\u2003; Flash>pro ", "deepseek-flash"),
                 ("combo:; custom-model|flash", "custom-model"),
                 ("COMBO:flash,pro", "COMBO:flash,pro"),
                 ("combo:,,,", "combo:,,,"), ("combo:", "combo:")]
        for shape in ("simple", "non-simple"):
            turns = [{"model": model, "input": "synthetic model selector",
                      **({"safety_identifier": "synthetic-user"} if shape == "non-simple" else {})}
                     for model, _ in cases]
            replies = [buffered_reply(index, created=42) for index in range(len(turns))]
            observed = []
            for binary in (ORACLE_01651, ORACLE_04392, MODEX):
                with self.subTest(shape=shape, binary=binary):
                    upstream, responses = observe_turns(binary, turns, replies)
                    self.assertEqual(len(upstream), len(turns))
                    self.assertEqual([response["status"] for response in responses], [200] * len(turns))
                    bodies = [json.loads(record["body"]) for record in upstream]
                    expected = [model for _, model in cases]
                    if binary == ORACLE_04392:
                        for index in (0, 3, 6):
                            expected[index] = "deepseek-v4-flash"
                    self.assertEqual([body["model"] for body in bodies], expected)
                    for record in upstream:
                        self.assertEqual(record["path"], "/v1/chat/completions")
                        self.assertEqual(record["headers"]["authorization"], "Bearer synthetic-provider-key")
                    observed.append(bodies)
            self.assertEqual(observed[0], observed[2])
            for index in (0, 3, 6):
                observed[1][index]["model"] = observed[0][index]["model"]
            self.assertEqual(observed[0], observed[1])


if __name__ == "__main__":
    unittest.main()
