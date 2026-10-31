"""Compare buffered provider metadata with the active 0.166.2 release."""

import hashlib
import json
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns
from test_provider_metadata_01660 import CASES


class ProviderMetadata01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_buffered_metadata_and_local_tags_match(self):
        for name, body, turn, expected_metadata in CASES:
            with self.subTest(case=name):
                observations = []
                for binary in (ORACLE, MODEX):
                    upstream, captured = observe_turns(
                        binary, [turn],
                        [{"status": 200, "content_type": "application/json", "body": body}],
                        latest_version="0.166.2",
                    )
                    self.assertEqual([row["status"] for row in captured], [200])
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
                    self.assertEqual(upstream[0]["headers"]["authorization"], "Bearer synthetic-provider-key")
                    response = json.loads(bytes.fromhex(captured[0]["body"]))
                    self.assertEqual(response.get("metadata"), expected_metadata)
                    response.pop("created_at", None)
                    observations.append((upstream[0]["body"], response))
                self.assertEqual(observations[0], observations[1])


if __name__ == "__main__":
    unittest.main()
