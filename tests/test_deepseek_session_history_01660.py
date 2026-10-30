"""Compare session-scoped tool history with the active 0.166.0 release."""

import hashlib
import json
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns


KEYS = "synthetic-key-a,synthetic-key-b"
KEY_A = "Bearer synthetic-key-a"
KEY_B = "Bearer synthetic-key-b"


def tool_call_reply(call_id="synthetic-history-call", response_id="synthetic-history-response"):
    return {
        "status": 200,
        "content_type": "application/json",
        "body": json.dumps({
            "id": response_id,
            "created": 42,
            "model": "deepseek-chat",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": call_id,
                        "type": "function",
                        "function": {"name": "lookup", "arguments": '{"source":"synthetic"}'},
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }).encode(),
    }


def streamed_tool_call_reply(call_id="synthetic-streamed-history-call"):
    def frame(delta, finish_reason=None, *, choices=True, usage=None):
        chunk = {
            "id": "synthetic-streamed-history",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "deepseek-chat",
            "choices": ([{"index": 0, "delta": delta, "finish_reason": finish_reason}] if choices else []),
        }
        if usage is not None:
            chunk["usage"] = usage
        return b"data: " + json.dumps(chunk, separators=(",", ":")).encode() + b"\n\n"

    return {
        "status": 200,
        "content_type": "text/event-stream",
        "body": b"".join((
            frame({"role": "assistant"}),
            frame({"tool_calls": [{
                "index": 0,
                "id": call_id,
                "type": "function",
                "function": {"name": "lookup", "arguments": '{"source":"synthetic"}'},
            }]}),
            frame({}, "tool_calls"),
            frame({}, choices=False, usage={"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}),
            b"data: [DONE]\n\n",
        )),
    }


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

    def test_tool_history_does_not_cross_api_credentials(self):
        call_id = "synthetic-credential-tool"
        turns = [
            {"model": "deepseek-chat", "input": "synthetic key A history"},
            {"model": "deepseek-chat", "input": [{
                "type": "function_call_output", "call_id": call_id, "output": "synthetic tool result",
            }], "safety_identifier": "synthetic-credential-history"},
        ]
        replies = [tool_call_reply(call_id, "synthetic-key-a-response"), buffered_reply(1)]
        posts, responses = observe_turns(
            ORACLE, turns, replies, api_keys=KEYS, latest_version="0.166.0",
        )
        self.assertEqual([response["status"] for response in responses], [200, 200])
        self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A, KEY_B])
        self.assertIn("synthetic key A history", json.dumps(json.loads(posts[1]["body"])["messages"]))

        posts, responses = observe_turns(MODEX, turns, replies, api_keys=KEYS, latest_version="0.166.0")
        self.assertEqual([response["status"] for response in responses], [200, 503])
        self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A])

    def test_buffered_and_streamed_tool_history_stays_with_its_key(self):
        for stream, reply, call_id in (
            (False, tool_call_reply(), "synthetic-history-call"),
            (True, streamed_tool_call_reply(), "synthetic-streamed-history-call"),
        ):
            seed = {"model": "deepseek-chat", "input": "synthetic same-key history"}
            if stream:
                seed["stream"] = True
            turns = [seed, {
                "model": "deepseek-chat",
                "input": [{"type": "function_call_output", "call_id": call_id, "output": "synthetic tool result"}],
                "safety_identifier": "synthetic-credential-history",
            }]
            for label, api_keys in (("single", "synthetic-key-a"), ("duplicate", "synthetic-key-a,synthetic-key-a")):
                with self.subTest(stream=stream, key_scope=label):
                    posts, responses = observe_turns(
                        MODEX, turns, [reply, buffered_reply(1)], api_keys=api_keys, latest_version="0.166.0",
                    )
                    self.assertEqual([response["status"] for response in responses], [200, 200])
                    self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A, KEY_A])
                    messages = json.loads(posts[1]["body"])["messages"]
                    self.assertIn("synthetic same-key history", json.dumps(messages))
                    self.assertIn("synthetic tool result", json.dumps(messages))

            with self.subTest(stream=stream, key_scope="different credentials"):
                posts, responses = observe_turns(
                    MODEX, turns, [reply, buffered_reply(1)], api_keys=KEYS, latest_version="0.166.0",
                )
                self.assertEqual([response["status"] for response in responses], [200, 503])
                self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A])

        same_session = [
            {"model": "deepseek-chat", "input": "synthetic session-owned tool history",
             "session_id": "synthetic-tool-session"},
            {"model": "deepseek-chat", "input": [{"type": "function_call_output",
             "call_id": "synthetic-history-call", "output": "synthetic tool result"}],
             "safety_identifier": "synthetic-credential-history",
             "session_id": "synthetic-tool-session"},
        ]
        posts, responses = observe_turns(
            MODEX, same_session, [tool_call_reply(), buffered_reply(1)],
            api_keys=KEYS, latest_version="0.166.0",
        )
        self.assertEqual([response["status"] for response in responses], [200, 503])
        self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A])

    def test_cached_history_suppresses_retry_to_another_credential(self):
        call_id = "synthetic-cached-retry-call"
        turns = [
            {"model": "deepseek-chat", "input": "synthetic key B cached prompt"},
            {"model": "deepseek-chat", "input": [{
                "type": "function_call_output", "call_id": call_id, "output": "synthetic cached output",
            }], "safety_identifier": "synthetic-credential-history"},
        ]
        retryable = {
            "status": 503, "content_type": "application/json",
            "body": b'{"error":{"code":"server_is_overloaded","message":"synthetic retry"}}',
        }
        tool_reply = tool_call_reply(call_id, "synthetic-key-b-cached-response")
        for binary, expected_keys, expected_statuses in (
            (ORACLE, [KEY_A, KEY_B, KEY_B, KEY_A], [200, 200]),
            (MODEX, [KEY_A, KEY_B, KEY_B], [200, 503]),
        ):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary, turns,
                    [retryable, tool_reply, retryable, buffered_reply(2)],
                    api_keys=KEYS, latest_version="0.166.0",
                )
                self.assertEqual([post["headers"]["authorization"] for post in posts], expected_keys)
                self.assertEqual([response["status"] for response in responses], expected_statuses)
                messages = json.loads(posts[2]["body"])["messages"]
                self.assertIn("synthetic key B cached prompt", json.dumps(messages))
                if binary == MODEX:
                    self.assertEqual(bytes.fromhex(responses[1]["body"]), retryable["body"])
                else:
                    self.assertIn("synthetic cached output", json.dumps(json.loads(posts[3]["body"])["messages"]))

    def test_native_anthropic_first_event_still_rotates_without_cached_history(self):
        request = [{
            "model": "deepseek-chat",
            "input": "synthetic native first-event retry",
            "tools": [{"type": "web_search_preview"}],
        }]
        error = {
            "status": 200, "content_type": "text/event-stream",
            "body": b'data: {"type":"error","error":{"type":"rate_limit_exceeded_error"}}\n\n',
        }
        success = {
            "status": 200, "content_type": "text/event-stream",
            "body": b"".join((
                b'data: {"type":"message_start","message":{"id":"synthetic-native-retry","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
                b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":1}}\n\n',
                b'data: {"type":"message_stop"}\n\n',
            )),
        }
        config = '[deepseek]\nweb_search_mode = "anthropic"\n'
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary, request, [error, success], api_keys=KEYS,
                    shared_config=config, latest_version="0.166.0",
                )
                self.assertEqual(
                    [post["headers"].get("x-api-key") for post in posts],
                    ["synthetic-key-a", "synthetic-key-b"],
                )
                self.assertEqual([response["status"] for response in responses], [200])

    def test_cross_key_tool_lookup_is_atomic_under_concurrent_requests(self):
        call_id = "synthetic-concurrent-credential-call"
        followup = {"model": "deepseek-chat", "input": [{
            "type": "function_call_output", "call_id": call_id, "output": "synthetic concurrent output",
        }], "safety_identifier": "synthetic-concurrent-history"}
        posts, responses = observe_turns(
            MODEX,
            [{"model": "deepseek-chat", "input": "synthetic concurrent seed"}],
            [tool_call_reply(call_id, "synthetic-concurrent-credential-response"), buffered_reply(1)],
            api_keys=KEYS,
            concurrent=True,
            followup_turns=[followup, followup],
            followup_concurrent=True,
            latest_version="0.166.0",
        )
        self.assertEqual(sorted(response["status"] for response in responses), [200, 200, 503])
        self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A, KEY_A])
        messages = json.loads(posts[1]["body"])["messages"]
        self.assertIn("synthetic concurrent seed", json.dumps(messages))
        self.assertIn("synthetic concurrent output", json.dumps(messages))


if __name__ == "__main__":
    unittest.main()
