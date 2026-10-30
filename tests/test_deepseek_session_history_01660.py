"""Compare session-scoped tool history with the active 0.166.0 release."""

import hashlib
import json
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns


class DeepSeekSessionHistory01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match 0.166.0")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")

    def test_tool_history_does_not_cross_explicit_sessions(self):
        call_id = "synthetic-session-tool"
        call = {"id": call_id, "type": "function",
                "function": {"name": "lookup", "arguments": "{}"}}
        reply = {"status": 200, "content_type": "application/json", "body": json.dumps({
            "id": "synthetic-first-response", "created": 42, "model": "deepseek-chat",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "",
                                                   "tool_calls": [call]},
                         "finish_reason": "tool_calls"}],
        }).encode()}
        for session_case in ("same", "different", "absent", "a_to_absent", "absent_to_b"):
            turns = [
                {"model": "deepseek-chat", "input": "synthetic session A prompt",
                 "_headers": {"x-codex-turn-metadata": '{"session_id":"synthetic-a"}'}},
                {"model": "deepseek-chat", "input": [{"type": "function_call_output",
                  "call_id": call_id, "output": "synthetic result"}],
                 "safety_identifier": "synthetic-history-lookup",
                 "_headers": {"x-codex-turn-metadata": '{"session_id":"synthetic-a"}'}},
            ]
            if session_case == "absent":
                turns[0].pop("_headers")
                turns[1].pop("_headers")
            elif session_case == "a_to_absent":
                turns[1].pop("_headers")
            elif session_case == "absent_to_b":
                turns[0].pop("_headers")
                turns[1]["_headers"]["x-codex-turn-metadata"] = '{"session_id":"synthetic-b"}'
            elif session_case == "different":
                turns[1]["_headers"]["x-codex-turn-metadata"] = '{"session_id":"synthetic-b"}'
            for label, binary in (("reference", ORACLE), ("Modex", MODEX)):
                with self.subTest(session_case=session_case, product=label):
                    posts, responses = observe_turns(
                        binary, turns, [reply, buffered_reply(1)],
                        api_keys="synthetic-provider-key", latest_version="0.166.0",
                    )
                    if session_case == "same":
                        self.assertEqual([response["status"] for response in responses], [200, 503])
                        self.assertEqual(len(posts), 1)
                        continue
                    self.assertEqual([response["status"] for response in responses], [200, 200])
                    self.assertEqual(len(posts), 2)
                    messages = json.dumps(json.loads(posts[1]["body"])["messages"])
                    if session_case == "absent" or label == "reference":
                        self.assertIn("synthetic session A prompt", messages)
                    else:
                        self.assertNotIn("synthetic session A prompt", messages)


if __name__ == "__main__":
    unittest.main()
