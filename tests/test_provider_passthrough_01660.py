"""Buffered provider metadata passthrough against Prodex 0.166.0."""

import hashlib
import json
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY


class ProviderBufferedMetadata01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 Linux release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")

    def test_buffered_passthrough_metadata_matches_active_release(self):
        values = ["synthetic-ascii", "synthetic\tmetadata", "synthetic-\x80",
                  "synthetic-\xff", "synthetic-\xc3\xa9"]
        payload = b"\x00synthetic metadata body\xff"
        for route, status in (("/v1/chat/completions?synthetic=metadata", 201), ("/v1/responses", 503)):
            turns = [{"model": "deepseek-chat", "_path": route,
                      **({"input": "synthetic"} if route == "/v1/responses" else {"messages": []}),
                      "_headers": {"x-codex-turn-state": f"synthetic-client-turn-{index}",
                          "x-codex-turn-metadata": json.dumps({"session_id": f"synthetic-metadata-{index}"}),
                          "x-prodex-internal-conversation-namespace": f"synthetic-namespace-{index}"}}
                     for index in range(len(values))]
            replies = [{"status": status, "content_type": "application/x-synthetic", "body": payload,
                        "response_headers": [("Content-Type", "application/x-synthetic"),
                            ("x-codex-turn-state", value), ("x-request-id", "synthetic-request"),
                            ("Connection", "X-Synthetic-Hop"), ("X-Synthetic-Hop", "strip-me")]}
                       for value in values]
            for binary in (ORACLE, MODEX):
                with self.subTest(route=route, binary=str(binary)):
                    upstream, responses = observe_turns(
                        binary, turns, replies, latest_version="0.166.0",
                    )
                    self.assertEqual(len(upstream), len(turns), "metadata handling must never replay a POST")
                    self.assertEqual([row["status"] for row in responses], [status] * len(turns))
                    for index, response in enumerate(responses):
                        headers = {name.lower(): value for name, value in response["headers"].items()}
                        self.assertEqual(headers.get("x-codex-turn-state"), values[index] if index < 2 else None)
                        self.assertEqual(headers["x-request-id"], "synthetic-request")
                        self.assertNotIn("x-synthetic-hop", headers)
                        self.assertEqual(bytes.fromhex(response["body"]), payload)
                        sent = upstream[index]["headers"]
                        self.assertEqual(sent["authorization"], "Bearer " + SYNTHETIC_API_KEY)
                        self.assertEqual(sent["x-codex-turn-state"], f"synthetic-client-turn-{index}")
                        self.assertFalse(any(name.startswith("x-prodex-internal-") for name in sent))


if __name__ == "__main__":
    unittest.main()
