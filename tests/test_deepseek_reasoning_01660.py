"""Compare DeepSeek reasoning request mapping with Prodex 0.166.0."""

import hashlib
import json
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns
from test_local_rewrite import json_bytes


CASES = [
    ("low_flat", {"reasoning_effort": "low"}, "low", "enabled"),
    ("low_nested_unicode", {"reasoning": {"effort": " \u2003LoW\u2003 "}}, "low", "enabled"),
    ("low_nested_precedence", {
        "reasoning_effort": "high", "reasoning": {"effort": " \u2003LoW\u2003 "},
    }, "low", "enabled"),
    ("medium", {"reasoning_effort": "medium"}, "high", "enabled"),
    ("high", {"reasoning_effort": "high"}, "high", "enabled"),
    ("max", {"reasoning_effort": "max"}, "max", "enabled"),
    ("xhigh", {"reasoning_effort": "xhigh"}, "max", "enabled"),
    ("minimal", {"reasoning_effort": "minimal"}, None, "disabled"),
    ("none", {"reasoning_effort": "none"}, None, "disabled"),
]


class DeepSeekReasoning01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def test_reasoning_effort_request_and_metadata_match_active_release(self):
        turns = [{"model": "deepseek-chat", "input": "synthetic reasoning", **fields}
                 for _, fields, _, _ in CASES]
        replies = [buffered_reply(index) for index in range(len(turns))]
        observations = []
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, turns, replies, latest_version="0.166.0",
                )
                self.assertEqual([row["status"] for row in responses], [200] * len(turns))
                self.assertEqual(len(upstream), len(turns))
                bodies = [json.loads(row["body"]) for row in upstream]
                self.assertEqual([body["reasoning_effort"] if "reasoning_effort" in body else None
                                  for body in bodies], [effort for _, _, effort, _ in CASES])
                self.assertEqual([body["thinking"]["type"] for body in bodies],
                                 [thinking for _, _, _, thinking in CASES])
                observations.append(bodies)
        self.assertEqual(observations[0], observations[1])

    def test_native_and_fallback_tool_choice_match_active_release(self):
        native_choice = {"type": "function", "name": "lookup"}
        fallback_choice = "required"
        turns = [
            {
                "model": "deepseek-chat", "input": "synthetic native reasoning",
                "reasoning_effort": "low",
                "tools": [{"type": "function", "name": "lookup", "parameters": {"type": "object"}}],
                "tool_choice": native_choice,
            },
            {
                "model": "deepseek-chat", "input": "synthetic fallback reasoning",
                "reasoning": {"effort": " \u2003LoW\u2003 "},
                "tools": [{"type": "custom", "name": "lookup", "format": {"type": "text"}}],
                "tool_choice": fallback_choice,
            },
        ]
        observations = []
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, turns, [buffered_reply(0), buffered_reply(1)],
                    latest_version="0.166.0",
                )
                self.assertEqual([row["status"] for row in responses], [200, 200])
                self.assertEqual([row["path"] for row in upstream],
                                 ["/v1/chat/completions", "/v1/chat/completions"])
                bodies = [json.loads(row["body"]) for row in upstream]
                self.assertEqual([body["reasoning_effort"] for body in bodies], ["low", "low"])
                self.assertEqual([body["thinking"] for body in bodies],
                                 [{"type": "enabled"}, {"type": "enabled"}])
                for body in bodies:
                    self.assertNotIn("tool_choice", body)
                    self.assertEqual(len(body["tools"]), 1)
                metadata = [json.loads(bytes.fromhex(row["body"]))["metadata"]["deepseek"]
                            for row in responses]
                self.assertEqual(metadata[0]["omitted_tool_choice"]["from"], native_choice)
                self.assertEqual(metadata[1]["omitted_tool_choice"]["from"], fallback_choice)
                self.assertTrue(all("thinking mode" in item["omitted_tool_choice"]["reason"]
                                    for item in metadata))
                observations.append(bodies)
        self.assertEqual(observations[0], observations[1])

    def test_low_effort_is_preserved_on_function_call_output_turn(self):
        call = {"id": "call_synthetic_low", "type": "function",
                "function": {"name": "lookup", "arguments": "{}"}}
        first = {"status": 200, "content_type": "application/json", "body": json_bytes({
            "id": "synthetic-chat-low", "model": "deepseek-chat",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": None,
                        "tool_calls": [call]}, "finish_reason": "tool_calls"}],
        })}
        turns = [
            {"model": "deepseek-chat", "input": "synthetic lookup"},
            {"model": "deepseek-chat", "input": [{
                "type": "function_call_output", "call_id": call["id"], "output": "synthetic result",
            }], "reasoning": {"effort": " \u2003LoW\u2003 "}},
        ]
        observations = []
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, turns, [first, buffered_reply(1)], latest_version="0.166.0",
                )
                self.assertEqual([row["status"] for row in responses], [200, 200])
                self.assertEqual(len(upstream), 2)
                followup = json.loads(upstream[1]["body"])
                self.assertEqual(followup["messages"], [{
                    "role": "tool", "tool_call_id": call["id"], "content": "synthetic result",
                }])
                self.assertEqual(followup["reasoning_effort"], "low")
                self.assertEqual(followup["thinking"], {"type": "enabled"})
                observations.append(followup)
        self.assertEqual(observations[0], observations[1])


if __name__ == "__main__":
    unittest.main()
