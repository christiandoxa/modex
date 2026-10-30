"""Characterize the unimplemented DeepSeek local compact route against 0.166.0."""

import hashlib
import json
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns


class LocalCompactGap01660Tests(unittest.TestCase):
    def test_compact_fallback_is_not_implemented(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        cases = (
            ([], "Original input items: 0", "No parseable recent message or tool content"),
            ([{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": "synthetic compact message"}]}],
             "Original input items: 1", "user message: synthetic compact message"),
        )
        for items, count, content in cases:
            for binary in (ORACLE, MODEX):
                with self.subTest(input_count=len(items), reference=binary == ORACLE):
                    upstream, responses = observe_turns(
                        binary,
                        [{"model": "deepseek-chat", "input": items, "_path": "/v1/responses/compact"}],
                        [], latest_version="0.166.0", concurrent=True,
                    )
                    self.assertEqual(upstream, [])
                    self.assertEqual(len(responses), 1)
                    response = responses[0]
                    payload = json.loads(bytes.fromhex(response["body"]))
                    if binary == ORACLE:
                        self.assertEqual(response["status"], 200)
                        headers = {name.lower(): value for name, value in response["headers"].items()}
                        self.assertEqual(headers["x-prodex-compact-mode"], "local-fallback")
                        self.assertEqual(headers["x-prodex-compact-provider"], "deepseek")
                        self.assertEqual(headers["x-prodex-compact-degraded"], "true")
                        self.assertEqual(headers["x-prodex-compact-reason"], "local-policy")
                        summary = payload["output"][0]["content"][0]["text"]
                        self.assertIn(count, summary)
                        self.assertIn(content, summary)
                    else:
                        self.assertEqual(response["status"], 404)
                        self.assertEqual(payload["error"]["code"], "unsupported_provider_route")


if __name__ == "__main__":
    unittest.main()
