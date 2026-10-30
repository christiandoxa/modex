"""Real-process characterization of Super tool-history session isolation."""

import hashlib
import json
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns
from test_deepseek_web_search_mode_01651_04392 import ORACLE_01651, ORACLE_01651_SHA256


SYNTHETIC_KEY = "synthetic-single-provider-key"
SESSION_A = '{"session_id":"synthetic-session-a"}'
SESSION_B = '{"session_id":"synthetic-session-b"}'


class DeepSeekSessionHistoryIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary, digest in ((ORACLE_01651, ORACLE_01651_SHA256), (ORACLE, ORACLE_SHA256)):
            if hashlib.sha256(binary.read_bytes()).hexdigest() != digest:
                raise AssertionError("The Prodex oracle does not match its pinned release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")

    def test_super_tool_output_reuses_history_from_a_different_session(self):
        """Historical releases import another session's prompt; Modex scopes it."""
        call_id = "synthetic-cross-session-tool-call"
        turns = [
            {
                "model": "deepseek-chat",
                "input": "synthetic private prompt from session A",
                "_headers": {"x-codex-turn-metadata": SESSION_A},
            },
            {
                "model": "deepseek-chat",
                "input": [{
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": "synthetic tool result from session B",
                }],
                "safety_identifier": "synthetic-session-history-lookup",
                "_headers": {"x-codex-turn-metadata": SESSION_B},
            },
        ]
        self.assertNotEqual(SESSION_A, SESSION_B)
        tool_call = {
            "id": call_id,
            "type": "function",
            "function": {"name": "lookup", "arguments": '{"owner":"session-a"}'},
        }
        replies = [
            {
                "status": 200,
                "content_type": "application/json",
                "body": json.dumps({
                    "id": "synthetic-session-a-response",
                    "created": 42,
                    "model": "deepseek-chat",
                    "choices": [{"index": 0, "message": {
                        "role": "assistant", "content": "", "tool_calls": [tool_call],
                    }, "finish_reason": "tool_calls"}],
                }).encode(),
            },
            buffered_reply(1),
        ]

        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(binary, turns, replies, api_keys=SYNTHETIC_KEY)
                self.assertEqual([response["status"] for response in responses], [200, 200])
                self.assertEqual(
                    [post["headers"]["authorization"] for post in posts],
                    ["Bearer " + SYNTHETIC_KEY] * 2,
                )
                messages = json.loads(posts[1]["body"])["messages"]
                if binary == MODEX:
                    self.assertNotIn("synthetic private prompt from session A", json.dumps(messages))
                else:
                    self.assertIn("synthetic private prompt from session A", json.dumps(messages))
                    self.assertIn(call_id, json.dumps(messages))


if __name__ == "__main__":
    unittest.main()
