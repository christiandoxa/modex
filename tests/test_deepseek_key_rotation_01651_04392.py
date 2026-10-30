"""Real-process characterization of DeepSeek credential rotation and binding."""

import hashlib
import json
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import buffered_reply, observe_turns
from test_deepseek_web_search_mode_01651_04392 import ORACLE_01651, ORACLE_01651_SHA256
import test_super_launch


KEYS = "synthetic-key-a,synthetic-key-b"
KEY_A = "Bearer synthetic-key-a"
KEY_B = "Bearer synthetic-key-b"
KEY_C = "Bearer synthetic-key-c"


class DeepSeekKeyRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary, digest in ((ORACLE_01651, ORACLE_01651_SHA256), (ORACLE, ORACLE_SHA256)):
            if hashlib.sha256(binary.read_bytes()).hexdigest() != digest:
                raise AssertionError("The Prodex oracle does not match its pinned release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")

    def test_published_cross_key_tool_history_gap_is_present(self):
        """Gap characterization, not parity: key-A history reaches key B on every binary."""
        call_id = "synthetic-cross-key-tool-call"
        turns = [
            {"model": "deepseek-chat", "input": "synthetic key A history"},
            {"model": "deepseek-chat", "input": [{"type": "function_call_output",
             "call_id": call_id, "output": "synthetic tool output"}],
             "safety_identifier": "synthetic-history-lookup"},
        ]
        call = {"id": call_id, "type": "function", "function": {
            "name": "lookup", "arguments": '{"source":"key-a"}',
        }}
        replies = [
            {"status": 200, "content_type": "application/json", "body": json.dumps({
                "id": "synthetic-key-a-response", "created": 42, "model": "deepseek-chat",
                "choices": [{"index": 0, "message": {
                    "role": "assistant", "content": "", "tool_calls": [call],
                }, "finish_reason": "tool_calls"}],
            }).encode()},
            buffered_reply(1),
        ]
        expected_history = [
            {"content": "synthetic key A history", "role": "user"},
            {"role": "assistant", "content": "", "tool_calls": [{
                "id": call_id, "type": "function", "function": {
                    "name": "lookup", "arguments": '{"source":"key-a"}',
                },
            }]},
            {"content": "synthetic tool output", "role": "tool", "tool_call_id": call_id},
        ]

        # This records an exposed behavior; it is not a parity assertion.
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(binary, turns, replies, api_keys=KEYS)
                self.assertEqual([response["status"] for response in responses], [200, 200])
                self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A, KEY_B])
                self.assertEqual(json.loads(posts[1]["body"])["messages"], expected_history)

    def test_releases_rotate_unbound_requests_and_constrain_continuations(self):
        turns = [{"model": "deepseek-chat", "input": "synthetic first"},
                 {"model": "deepseek-chat", "input": "synthetic second"}]
        for binary in (ORACLE_01651, ORACLE):
            with self.subTest(binary=str(binary), scenario="unbound"):
                posts, responses = observe_turns(binary, turns, [buffered_reply(), buffered_reply(1)], api_keys=KEYS)
                self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A, KEY_B])
                self.assertEqual([response["status"] for response in responses], [200, 200])
            with self.subTest(binary=str(binary), scenario="previous_response"):
                bound_turns = [turns[0], {**turns[1], "use_previous": True}]
                posts, responses = observe_turns(binary, bound_turns, [buffered_reply(), buffered_reply(1)], api_keys=KEYS)
                self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A])
                self.assertEqual([response["status"] for response in responses], [200, 503])
                self.assertIn(b"bound_continuation_unavailable", bytes.fromhex(responses[1]["body"]))
            for identity_name, identity in (
                ("session", {"session_id": "synthetic-bound-session"}),
                ("turn", {"_headers": {"x-codex-turn-state": "synthetic-bound-turn"}}),
            ):
                with self.subTest(binary=str(binary), scenario=identity_name):
                    bound_turns = [
                        {"model": "deepseek-chat", "input": "synthetic first", **identity},
                        {"model": "deepseek-chat", "input": "synthetic second", **identity},
                    ]
                    posts, responses = observe_turns(
                        binary, bound_turns, [buffered_reply(), buffered_reply(1)], api_keys=KEYS,
                    )
                    self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A])
                    self.assertEqual([response["status"] for response in responses], [200, 503])
                    self.assertIn(b"bound_continuation_unavailable", bytes.fromhex(responses[1]["body"]))

        with self.subTest(binary=str(MODEX), scenario="unbound"):
            posts, responses = observe_turns(MODEX, turns, [buffered_reply(), buffered_reply(1)], api_keys=KEYS)
            self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A, KEY_B])
            self.assertEqual([response["status"] for response in responses], [200, 200])
        with self.subTest(binary=str(MODEX), scenario="previous_response"):
            bound_turns = [turns[0], {**turns[1], "use_previous": True}]
            posts, responses = observe_turns(MODEX, bound_turns, [buffered_reply(), buffered_reply(1)], api_keys=KEYS)
            self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A])
            self.assertEqual([response["status"] for response in responses], [200, 503])
            self.assertIn(b"bound_continuation_unavailable", bytes.fromhex(responses[1]["body"]))
        for identity_name, identity in (
            ("session", {"session_id": "synthetic-bound-session"}),
            ("turn", {"_headers": {"x-codex-turn-state": "synthetic-bound-turn"}}),
        ):
            with self.subTest(binary=str(MODEX), scenario=identity_name):
                bound_turns = [
                    {"model": "deepseek-chat", "input": "synthetic first", **identity},
                    {"model": "deepseek-chat", "input": "synthetic second", **identity},
                ]
                posts, responses = observe_turns(
                    MODEX, bound_turns, [buffered_reply(), buffered_reply(1)], api_keys=KEYS,
                )
                self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A])
                self.assertEqual([response["status"] for response in responses], [200, 503])
                self.assertIn(b"bound_continuation_unavailable", bytes.fromhex(responses[1]["body"]))

        result, records, upstream, state = test_super_launch.SuperLaunchTests().run_launch(
            binary=MODEX, api_key=None, scenario="buffered", environment_overrides={"DEEPSEEK_API_KEYS": KEYS},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((len(upstream), state["leftovers"]), (1, []))
        self.assertNotIn(KEYS.encode(), result.stdout + result.stderr)

    def test_structured_retry_classification_matches_both_releases(self):
        requests = (
            ("responses", [{"model": "deepseek-chat", "input": "synthetic retry"}]),
            ("chat_completions", [{
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "synthetic retry"}],
                "_path": "/v1/chat/completions",
            }]),
        )
        cases = (
            ("auth", 401, b'{"error":{"code":"invalid_api_key"}}', True),
            ("rate_limit", 429, b'{"error":{"code":"rate_limit_exceeded"}}', True),
            ("transient", 503, b'{"error":{"type":"server_is_overloaded"}}', True),
            ("unknown_503", 503, b'{"error":{"type":"synthetic_error","message":"synthetic failure"}}', True),
            ("malformed_503", 503, b'{"error":', True),
            ("unknown_401", 401, b'{"error":{"type":"synthetic_error"}}', True),
            ("unknown_429", 429, b'{"error":{"type":"synthetic_error"}}', False),
            ("not_found", 404, b'{"error":{"code":"model_not_supported"}}', False),
            ("case_sensitive_code_key", 429, b'{"error":{"CODE":"rate_limit_error"}}', False),
            ("duplicate_code_last_unknown", 429,
             b'{"error":{"code":"invalid_api_key","code":"invalid_request"}}', False),
            ("duplicate_code_last_retryable", 429,
             b'{"error":{"code":"invalid_request","code":"invalid_api_key"}}', True),
        )
        for name, status, body, retry in cases:
            for route_name, request in requests:
                for binary in (ORACLE_01651, ORACLE, MODEX):
                    with self.subTest(case=name, route=route_name, binary=str(binary)):
                        posts, responses = observe_turns(
                            binary, request,
                            [{"status": status, "content_type": "application/json", "body": body}, buffered_reply(1)],
                            api_keys=KEYS,
                        )
                        self.assertEqual([post["headers"]["authorization"] for post in posts],
                                         [KEY_A, KEY_B] if retry else [KEY_A])
                        self.assertEqual([response["status"] for response in responses], [200] if retry else [status])
                        if not retry:
                            self.assertEqual(bytes.fromhex(responses[0]["body"]), body)

    def test_unknown_identity_candidates_still_rotate(self):
        identities = (
            ("previous response", {"previous_response_id": "synthetic-unbound-response"}),
            ("turn state", {"_headers": {"x-codex-turn-state": "synthetic-unbound-turn"}}),
            ("session", {"session_id": "synthetic-unbound-session"}),
        )
        error = {"status": 401, "content_type": "application/json",
                 "body": b'{"error":{"code":"invalid_api_key"}}'}
        for binary in (ORACLE_01651, ORACLE, MODEX):
            for identity_name, identity in identities:
                with self.subTest(binary=str(binary), identity=identity_name):
                    posts, responses = observe_turns(
                        binary,
                        [{"model": "deepseek-chat", "input": "synthetic unknown identity", **identity}],
                        [error, buffered_reply(1)],
                        api_keys=KEYS,
                    )
                    self.assertEqual(
                        [post["headers"]["authorization"] for post in posts], [KEY_A, KEY_B],
                    )
                    self.assertEqual([response["status"] for response in responses], [200])

    def test_native_anthropic_precommit_error_rotates_once(self):
        request = [{
            "model": "deepseek-chat",
            "input": "synthetic search",
            "tools": [{"type": "web_search_preview"}],
        }]
        error = b'data: {"type":"error","error":{"type":"rate_limit_exceeded_error"}}\n\n'
        success = b"".join((
            b'data: {"type":"message_start","message":{"id":"msg-ok","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}\n\n',
            b'data: {"type":"message_stop"}\n\n',
        ))
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary,
                    request,
                    [
                        {"status": 200, "content_type": "text/event-stream", "body": error},
                        {"status": 200, "content_type": "text/event-stream", "body": success},
                    ],
                    api_keys=KEYS,
                )
                self.assertEqual(
                    [post["headers"].get("x-api-key") for post in posts],
                    ["synthetic-key-a", "synthetic-key-b"],
                )
                self.assertEqual([response["status"] for response in responses], [200])

    def test_native_anthropic_error_event_type_gate_is_case_sensitive(self):
        request = [{
            "model": "deepseek-chat",
            "input": "synthetic search",
            "tools": [{"type": "web_search_preview"}],
        }]
        success = b"".join((
            b'data: {"type":"message_start","message":{"id":"msg-ok","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}\n\n',
            b'data: {"type":"message_stop"}\n\n',
        ))
        cases = (
            ("uppercase type with top-level code", b'data: {"type":"ERROR","code":"rate_limit_error"}\n\n', ["synthetic-key-a"]),
            ("exact type with top-level code", b'data: {"type":"error","code":"rate_limit_error"}\n\n', ["synthetic-key-a", "synthetic-key-b"]),
            ("uppercase type with error member", b'data: {"type":"ERROR","error":{"type":"rate_limit_error"}}\n\n', ["synthetic-key-a", "synthetic-key-b"]),
            ("whitespace type", b'data: {"type":" error ","code":"rate_limit_error"}\n\n', ["synthetic-key-a"]),
        )
        for binary in (ORACLE_01651, ORACLE, MODEX):
            for name, first_event, expected_keys in cases:
                with self.subTest(binary=str(binary), case=name):
                    posts, responses = observe_turns(
                        binary,
                        request,
                        [
                            {"status": 200, "content_type": "text/event-stream", "body": first_event + success},
                            {"status": 200, "content_type": "text/event-stream", "body": success},
                        ],
                        api_keys=KEYS,
                    )
                    self.assertEqual(
                        [post["headers"].get("x-api-key") for post in posts],
                        expected_keys,
                    )
                    self.assertEqual([response["status"] for response in responses], [200])

    def test_exhausted_native_anthropic_error_event_matches_releases(self):
        request = [{
            "model": "deepseek-chat",
            "input": "synthetic search",
            "tools": [{"type": "web_search_preview"}],
        }]
        error = b'data: {"type":"error","error":{"type":"rate_limit_error","message":"synthetic rate limit"}}\n\n'
        success = b"".join((
            b'data: {"type":"message_start","message":{"id":"msg-ok","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}\n\n',
            b'data: {"type":"message_stop"}\n\n',
        ))
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary), scenario="single key"):
                posts, responses = observe_turns(
                    binary, request,
                    [{"status": 200, "content_type": "text/event-stream", "body": error}],
                    api_keys="synthetic-key-a",
                )
                events = [json.loads(line[6:]) for line in bytes.fromhex(responses[0]["body"]).splitlines()
                          if line.startswith(b"data: ")]
                self.assertEqual([post["headers"].get("x-api-key") for post in posts], ["synthetic-key-a"])
                self.assertEqual(responses[0]["status"], 200)
                self.assertEqual([event["type"] for event in events], ["response.failed"])
                self.assertEqual(events[0]["response"]["error"], {
                    "code": "provider_stream_error", "message": "unexpected end of stream",
                })

            with self.subTest(binary=str(binary), scenario="exhausted rotation"):
                posts, responses = observe_turns(
                    binary, request,
                    [
                        {"status": 200, "content_type": "text/event-stream", "body": error},
                        {"status": 200, "content_type": "text/event-stream", "body": error},
                    ],
                    api_keys=KEYS,
                )
                events = [json.loads(line[6:]) for line in bytes.fromhex(responses[0]["body"]).splitlines()
                          if line.startswith(b"data: ")]
                self.assertEqual(
                    [post["headers"].get("x-api-key") for post in posts],
                    ["synthetic-key-a", "synthetic-key-b"],
                )
                self.assertEqual(responses[0]["status"], 200)
                self.assertEqual([event["type"] for event in events], ["response.failed"])
                self.assertEqual(events[0]["response"]["error"], {
                    "code": "provider_stream_error", "message": "unexpected end of stream",
                })

            with self.subTest(binary=str(binary), scenario="event followed by valid stream"):
                posts, responses = observe_turns(
                    binary, request,
                    [{"status": 200, "content_type": "text/event-stream", "body": error + success}],
                    api_keys="synthetic-key-a",
                )
                events = [json.loads(line[6:]) for line in bytes.fromhex(responses[0]["body"]).splitlines()
                          if line.startswith(b"data: ")]
                self.assertEqual(len(posts), 1)
                self.assertEqual([event["type"] for event in events], ["response.created", "response.completed"])

    def test_native_anthropic_precommit_transport_failure_rotates(self):
        request = [{
            "model": "deepseek-chat",
            "input": "synthetic search",
            "tools": [{"type": "web_search_preview"}],
        }]
        partial = b'data: {"type":"error","error":{"type":"rate_limit_error"}}'
        success = b"".join((
            b'data: {"type":"message_start","message":{"id":"msg-ok","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}\n\n',
            b'data: {"type":"message_stop"}\n\n',
        ))
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary,
                    request,
                    [
                        {
                            "status": 200,
                            "content_type": "text/event-stream",
                            "body": partial,
                            "declared_length": len(partial) + 20,
                            "reset_after_body": True,
                        },
                        {"status": 200, "content_type": "text/event-stream", "body": success},
                    ],
                    api_keys=KEYS,
                )
                self.assertEqual(
                    [post["headers"].get("x-api-key") for post in posts],
                    ["synthetic-key-a", "synthetic-key-b"],
                )
                self.assertEqual([response["status"] for response in responses], [200])

    def test_single_key_non_2xx_sse_error_stays_raw(self):
        body = b'data: {"type":"error","error":{"type":"rate_limit_error"}}\n\n'
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary,
                    [{"model": "deepseek-chat", "input": "synthetic non-2xx stream"}],
                    [{"status": 503, "content_type": "text/event-stream", "body": body}],
                    api_keys="synthetic-key-a",
                )
                self.assertEqual(len(posts), 1)
                self.assertEqual(responses[0]["status"], 503)
                self.assertEqual(bytes.fromhex(responses[0]["body"]), body)

    def test_concurrent_owner_conflict_matches_both_releases(self):
        identity = {
            "session_id": "synthetic-conflicting-session",
            "_headers": {"x-codex-turn-state": "synthetic-conflicting-turn"},
        }
        turns = [
            {"model": "deepseek-chat", "input": f"synthetic conflict {index}", **identity}
            for index in range(4)
        ]
        followup = [{"model": "deepseek-chat", "input": "synthetic conflict follow-up", **identity}]
        replies = []
        for index in range(4):
            reply = buffered_reply(index)
            reply["release_after_requests"] = 4
            replies.append(reply)
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary, turns, replies, api_keys=KEYS, concurrent=True,
                    followup_turns=followup,
                )
                self.assertEqual(len(posts), 4)
                self.assertEqual({post["headers"]["authorization"] for post in posts}, {KEY_A, KEY_B})
                self.assertEqual([response["status"] for response in responses], [200, 200, 200, 200, 503])
                self.assertIn(b"bound_continuation_unavailable", bytes.fromhex(responses[-1]["body"]))

    def test_retry_classifier_matches_the_pinned_code_set(self):
        retry_codes = (
            "unauthenticated", "invalid_api_key", "authentication_error",
            "insufficient_quota", "credit_balance_exhausted",
            "organization_spend_limit_exceeded", "project_spend_limit_exceeded",
            "quota_exhausted", "quota_exceeded", "resource_exhausted",
            "rate_limit_error", "rate_limit_exceeded", "rate_limit_exceeded_error", "slow_down",
            "overloaded_error", "server_is_overloaded",
        )
        no_retry_codes = (
            "not_found_error", "model_not_supported", "unauthorized", "unauthorized_error",
            "permission_denied", "permission_error", "invalid_credential", "rate_limit",
            "too_many_requests", "service_unavailable", "temporarily_unavailable",
            "internal_error", "internal_server_error", "backend_error", "server_error",
            "unavailable", "model_not_found", "not_found",
        )
        binaries = (ORACLE_01651, ORACLE, MODEX)
        for binary in binaries:
            with self.subTest(binary=str(binary), scenario="pinned retry codes"):
                turns = [{"model": "deepseek-chat", "input": f"synthetic code {i}"}
                         for i in range(len(retry_codes))]
                replies = []
                expected_auth = []
                for index, code in enumerate(retry_codes):
                    body = b'{"error":{"code":"' + code.encode() + b'"}}'
                    replies.extend([
                        {"status": 429, "content_type": "application/json", "body": body},
                        buffered_reply(index),
                    ])
                    first = KEY_A if index % 2 == 0 else KEY_B
                    expected_auth.extend([first, KEY_B if first == KEY_A else KEY_A])
                posts, responses = observe_turns(binary, turns, replies, api_keys=KEYS)
                self.assertEqual([post["headers"]["authorization"] for post in posts], expected_auth)
                self.assertEqual([response["status"] for response in responses], [200] * len(retry_codes))
            with self.subTest(binary=str(binary), scenario="unverified aliases"):
                turns = [{"model": "deepseek-chat", "input": f"synthetic alias {i}"}
                         for i in range(len(no_retry_codes))]
                replies = [
                    {"status": 429, "content_type": "application/json",
                     "body": b'{"error":{"code":"' + code.encode() + b'"}}'}
                    for code in no_retry_codes
                ]
                posts, responses = observe_turns(binary, turns, replies, api_keys=KEYS)
                self.assertEqual(
                    [post["headers"]["authorization"] for post in posts],
                    [KEY_A if index % 2 == 0 else KEY_B for index in range(len(no_retry_codes))],
                )
                self.assertEqual([response["status"] for response in responses], [429] * len(no_retry_codes))

    def test_modex_chat_retry_returns_only_the_final_upstream_body(self):
        request = [{
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "synthetic retry"}],
            "_path": "/v1/chat/completions",
        }]
        final = buffered_reply(1)
        posts, responses = observe_turns(
            MODEX, request,
            [{"status": 401, "content_type": "application/json",
              "body": b'{"error":{"code":"invalid_api_key"}}'}, final],
            api_keys=KEYS,
        )
        self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A, KEY_B])
        self.assertEqual(responses[0]["status"], 200)
        self.assertEqual(bytes.fromhex(responses[0]["body"]), final["body"])

    def test_modex_unknown_identity_chat_error_rotates_to_final_body(self):
        error_body = b'{"error":{"code":"server_is_overloaded","message":"synthetic failure"}}'
        request = [{
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "synthetic scoped error"}],
            "session_id": "synthetic-session",
            "_path": "/v1/chat/completions",
        }]
        final = buffered_reply(1)
        posts, responses = observe_turns(
            MODEX, request,
            [{"status": 503, "content_type": "application/json", "body": error_body}, final],
            api_keys=KEYS,
        )
        self.assertEqual([post["headers"]["authorization"] for post in posts], [KEY_A, KEY_B])
        self.assertEqual(responses[0]["status"], 200)
        self.assertEqual(bytes.fromhex(responses[0]["body"]), final["body"])

    def test_modex_unbound_round_robin_is_atomic_under_concurrency(self):
        turns = [{"model": "deepseek-chat", "input": f"synthetic turn {index}"} for index in range(4)]
        posts, responses = observe_turns(
            MODEX, turns, [buffered_reply(index) for index in range(4)], api_keys=KEYS, concurrent=True,
        )
        self.assertEqual(len(posts), 4)
        self.assertEqual(sorted(post["headers"]["authorization"] for post in posts), sorted([KEY_A, KEY_A, KEY_B, KEY_B]))
        self.assertEqual(sorted(response["status"] for response in responses), [200, 200, 200, 200])

    def test_status_fallback_retry_matches_releases_before_commit(self):
        request = [{"model": "deepseek-chat", "input": "synthetic retry"}]
        body = b'{"error":{"message":"synthetic failure","type":"synthetic"}}'
        for status in (400, 401, 403, 404, 408, 409, 422, 429, 500, 502, 503):
            retry = status in (401, 403, 500, 502, 503)
            for binary in (ORACLE_01651, ORACLE, MODEX):
                with self.subTest(status=status, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary, request,
                        [{"status": status, "content_type": "application/json", "body": body}, buffered_reply(1)],
                        api_keys=KEYS,
                    )
                    self.assertEqual([post["headers"]["authorization"] for post in posts],
                                     [KEY_A, KEY_B] if retry else [KEY_A])
                    self.assertEqual(responses[0]["status"], 200 if retry else status)
        for name, status, text_body, retry in (
            ("overloaded text", 400, b'{"error":{"message":"backend overloaded"}}', True),
            ("unsupported text", 400, b'{"error":{"message":"model is not supported"}}', False),
            ("generic 429 text", 429, b'{"error":{"message":"too many requests"}}', False),
        ):
            for binary in (ORACLE_01651, ORACLE, MODEX):
                with self.subTest(case=name, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary, request,
                        [{"status": status, "content_type": "application/json", "body": text_body},
                         buffered_reply(1)],
                        api_keys=KEYS,
                    )
                    self.assertEqual(
                        [post["headers"]["authorization"] for post in posts],
                        [KEY_A, KEY_B] if retry else [KEY_A],
                    )
                    self.assertEqual(responses[0]["status"], 200 if retry else status)

    def test_three_key_retry_exhaustion_keeps_one_cursor_advance(self):
        keys = "synthetic-key-a,synthetic-key-b,synthetic-key-c"
        error_body = b'{"error":{"code":"rate_limit_error","message":"synthetic exhausted"}}'
        retryable_error = {"status": 429, "content_type": "application/json", "body": error_body}
        routes = (
            ("responses", [
                {"model": "deepseek-chat", "input": "synthetic exhaust all three keys"},
                {"model": "deepseek-chat", "input": "synthetic request after exhaustion"},
            ]),
            ("chat_completions", [
                {"model": "deepseek-chat", "messages": [{"role": "user", "content": "synthetic exhaust all three keys"}],
                 "_path": "/v1/chat/completions"},
                {"model": "deepseek-chat", "messages": [{"role": "user", "content": "synthetic request after exhaustion"}],
                 "_path": "/v1/chat/completions"},
            ]),
        )
        for route_name, turns in routes:
            for binary in (ORACLE_01651, ORACLE, MODEX):
                with self.subTest(route=route_name, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary, turns,
                        [retryable_error, retryable_error, retryable_error, buffered_reply(1)],
                        api_keys=keys,
                    )
                    self.assertEqual(
                        [post["headers"]["authorization"] for post in posts],
                        [KEY_A, KEY_B, KEY_C, KEY_B],
                    )
                    self.assertEqual([response["status"] for response in responses], [429, 200])
                    self.assertEqual(bytes.fromhex(responses[0]["body"]), error_body)

    def test_combo_model_fallback_precedes_credential_rotation(self):
        turns = [{"model": "combo:flash,pro", "input": "synthetic model fallback"}]
        replies = [
            {"status": 404, "content_type": "application/json",
             "body": b'{"error":{"code":"model_not_supported","message":"synthetic unsupported model"}}'},
            {"status": 401, "content_type": "application/json",
             "body": b'{"error":{"code":"invalid_api_key","message":"synthetic rejected key"}}'},
            buffered_reply(),
        ]
        expected_models = {
            ORACLE_01651: ["deepseek-flash", "deepseek-v4-pro", "deepseek-flash"],
            ORACLE: ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-v4-flash"],
            MODEX: ["deepseek-flash", "deepseek-v4-pro", "deepseek-flash"],
        }
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary, turns, replies, api_keys=KEYS,
                )
                self.assertEqual(
                    [post["headers"]["authorization"] for post in posts],
                    [KEY_A, KEY_A, KEY_B],
                )
                self.assertEqual(
                    [json.loads(post["body"])["model"] for post in posts],
                    expected_models[binary],
                )
                self.assertEqual(
                    [json.loads(post["body"])["messages"] for post in posts],
                    [[{"content": "synthetic model fallback", "role": "user"}]] * 3,
                )
                self.assertEqual([response["status"] for response in responses], [200])

    def test_combo_model_retry_budget_caps_and_resets_per_credential(self):
        models = [f"synthetic-budget-model-{index}" for index in range(257)]
        request = [{
            "model": "combo:" + ",".join(models),
            "input": "synthetic model retry budget",
        }]
        rate_limit = {
            "status": 429, "content_type": "application/json",
            "body": b'{"error":{"code":"rate_limit_error"}}',
        }
        request_with_search = [{
            **request[0],
            "tools": [{"type": "web_search_preview"}],
        }]
        first_event_error = (
            b'data: {"type":"error","error":{"type":"rate_limit_error"}}\n\n'
        )
        success = b"".join((
            b'data: {"type":"message_start","message":{"id":"msg-ok","role":"assistant","model":"synthetic-budget-model-0","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}\n\n',
            b'data: {"type":"message_stop"}\n\n',
        ))
        not_found = {
            "status": 404, "content_type": "application/json",
            "body": b'{"error":{"code":"model_not_supported"}}',
        }
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary), scenario="HTTP cap and credential reset"):
                posts, responses = observe_turns(
                    binary, request,
                    [rate_limit] * 257 + [buffered_reply(1)],
                    api_keys=KEYS,
                )
                self.assertEqual(len(posts), 258)
                self.assertEqual(
                    [post["headers"]["authorization"] for post in posts],
                    [KEY_A] * 256 + [KEY_B, KEY_B],
                )
                self.assertEqual(
                    [json.loads(post["body"])["model"] for post in posts],
                    models[:256] + models[:2],
                )
                self.assertEqual([response["status"] for response in responses], [200])

            with self.subTest(binary=str(binary), scenario="native first event at model budget edge"):
                posts, responses = observe_turns(
                    binary, request_with_search,
                    [not_found] * 255 + [
                        {"status": 200, "content_type": "text/event-stream", "body": first_event_error},
                        {"status": 200, "content_type": "text/event-stream", "body": success},
                    ],
                    api_keys=KEYS,
                )
                self.assertEqual(len(posts), 257)
                self.assertEqual(
                    [post["headers"].get("x-api-key") for post in posts],
                    ["synthetic-key-a"] * 256 + ["synthetic-key-b"],
                )
                self.assertEqual(
                    [json.loads(post["body"])["model"] for post in posts],
                    models[:256] + [models[0]],
                )
                self.assertEqual([response["status"] for response in responses], [200])

    def test_combo_model_candidates_accept_large_chains_without_quadratic_scan(self):
        candidate_sets = (
            ("2,049 candidates", [f"synthetic-model-{index}" for index in range(2049)]),
            ("2,048 long candidates", [
                f"synthetic-{index:04d}-" + "x" * (256 - len(f"synthetic-{index:04d}-"))
                for index in range(2048)
            ]),
        )
        for binary in (ORACLE_01651, ORACLE, MODEX):
            for scenario, models in candidate_sets:
                with self.subTest(binary=str(binary), scenario=scenario):
                    posts, responses = observe_turns(
                        binary,
                        [{"model": "combo:" + ",".join(models), "input": "synthetic large model chain"}],
                        [buffered_reply()],
                        api_keys="synthetic-key-a",
                    )
                    self.assertEqual(len(posts), 1)
                    self.assertEqual(json.loads(posts[0]["body"])["model"], models[0])
                    self.assertEqual([response["status"] for response in responses], [200])

    def test_combo_model_exhaustion_preserves_final_error_and_advances_cursor_once(self):
        turns = [
            {"model": "combo:flash,pro", "input": "synthetic exhaust model chain"},
            {"model": "deepseek-chat", "input": "synthetic after model exhaustion"},
        ]
        final_error = b'{"error":{"code":"model_not_supported","message":"synthetic final model error"}}'
        unsupported = {"status": 404, "content_type": "application/json", "body": final_error}
        expected_first_model = {
            ORACLE_01651: "deepseek-flash",
            ORACLE: "deepseek-v4-flash",
            MODEX: "deepseek-flash",
        }
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary, turns, [unsupported, unsupported, buffered_reply(2)], api_keys=KEYS,
                )
                self.assertEqual(
                    [post["headers"]["authorization"] for post in posts],
                    [KEY_A, KEY_A, KEY_B],
                )
                self.assertEqual(
                    [json.loads(post["body"])["model"] for post in posts],
                    [expected_first_model[binary], "deepseek-v4-pro", "deepseek-chat"],
                )
                self.assertEqual([response["status"] for response in responses], [404, 200])
                self.assertEqual(bytes.fromhex(responses[0]["body"]), final_error)

    def test_combo_custom_models_retry_with_one_key_and_empty_combo_stays_literal(self):
        unsupported = {
            "status": 404, "content_type": "application/json",
            "body": b'{"error":{"code":"model_not_supported"}}',
        }
        custom_turn = [{
            "model": "combo:synthetic-model-one,synthetic-model-two",
            "input": "synthetic custom model fallback",
        }]
        unknown_404 = {
            "status": 404, "content_type": "application/json",
            "body": b'{"error":{"code":"synthetic_unknown_error","message":"synthetic unavailable"}}',
        }
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary), case="custom candidates with one credential"):
                posts, responses = observe_turns(
                    binary,
                    custom_turn,
                    [unknown_404, buffered_reply()],
                    api_keys="synthetic-key-a",
                )
                self.assertEqual(
                    [post["headers"]["authorization"] for post in posts], [KEY_A, KEY_A],
                )
                self.assertEqual(
                    [json.loads(post["body"])["model"] for post in posts],
                    ["synthetic-model-one", "synthetic-model-two"],
                )
                self.assertEqual([response["status"] for response in responses], [200])

            with self.subTest(binary=str(binary), case="empty candidate list"):
                posts, responses = observe_turns(
                    binary,
                    [{"model": "combo:,,,", "input": "synthetic empty combo"}],
                    [unsupported],
                    api_keys=KEYS,
                )
                self.assertEqual(len(posts), 1)
                self.assertEqual(json.loads(posts[0]["body"])["model"], "combo:,,,")
                self.assertEqual([response["status"] for response in responses], [404])

    def test_combo_model_fallback_success_binds_the_session_to_its_credential(self):
        session = {"session_id": "synthetic-combo-bound-session"}
        turns = [
            {"model": "combo:flash,pro", "input": "synthetic bound fallback", **session},
            {"model": "deepseek-chat", "input": "synthetic bound continuation", **session},
        ]
        unsupported = {
            "status": 404, "content_type": "application/json",
            "body": b'{"error":{"code":"model_not_supported"}}',
        }
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary, turns, [unsupported, buffered_reply(1)], api_keys=KEYS,
                )
                self.assertEqual(
                    [post["headers"]["authorization"] for post in posts], [KEY_A, KEY_A],
                )
                self.assertEqual([response["status"] for response in responses], [200, 503])
                self.assertIn(b"bound_continuation_unavailable", bytes.fromhex(responses[1]["body"]))

    def test_native_anthropic_not_found_first_event_falls_back_before_rotation(self):
        request = [{
            "model": "combo:flash,pro",
            "input": "synthetic native model fallback",
            "tools": [{"type": "web_search_preview"}],
        }]
        error = b'data: {"type":"error","error":{"type":"not_found_error"}}\n\n'
        success = b"".join((
            b'data: {"type":"message_start","message":{"id":"msg-ok","role":"assistant","model":"deepseek-v4-pro","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}\n\n',
            b'data: {"type":"message_stop"}\n\n',
        ))
        expected_models = {
            ORACLE_01651: ["deepseek-flash", "deepseek-v4-pro"],
            ORACLE: ["deepseek-v4-flash", "deepseek-v4-pro"],
            MODEX: ["deepseek-flash", "deepseek-v4-pro"],
        }
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary,
                    request,
                    [
                        {"status": 200, "content_type": "text/event-stream", "body": error},
                        {"status": 200, "content_type": "text/event-stream", "body": success},
                    ],
                    api_keys=KEYS,
                )
                self.assertEqual(
                    [post["headers"].get("x-api-key") for post in posts],
                    ["synthetic-key-a", "synthetic-key-a"],
                )
                self.assertEqual(
                    [json.loads(post["body"])["model"] for post in posts],
                    expected_models[binary],
                )
                self.assertEqual([response["status"] for response in responses], [200])

    def test_native_anthropic_not_found_exhaustion_matches_single_key_releases(self):
        error = b'data: {"type":"error","error":{"type":"not_found_error","message":"synthetic unavailable"}}\n\n'
        cases = (
            ("single model", "deepseek-chat", ["deepseek-chat"]),
            ("combo exhausted", "combo:flash,pro", None),
        )
        for binary in (ORACLE_01651, ORACLE, MODEX):
            for name, model, expected_models in cases:
                with self.subTest(binary=str(binary), scenario=name):
                    replies = [{"status": 200, "content_type": "text/event-stream", "body": error}]
                    if model.startswith("combo:"):
                        replies.append({"status": 200, "content_type": "text/event-stream", "body": error})
                    posts, responses = observe_turns(
                        binary,
                        [{
                            "model": model,
                            "input": "synthetic single-key native fallback exhaustion",
                            "tools": [{"type": "web_search_preview"}],
                        }],
                        replies,
                        api_keys="synthetic-key-a",
                    )
                    posted_models = [json.loads(post["body"])["model"] for post in posts]
                    if expected_models is None:
                        expected_models = {
                            ORACLE_01651: ["deepseek-flash", "deepseek-v4-pro"],
                            ORACLE: ["deepseek-v4-flash", "deepseek-v4-pro"],
                            MODEX: ["deepseek-flash", "deepseek-v4-pro"],
                        }[binary]
                    self.assertEqual(posted_models, expected_models)
                    self.assertTrue(all(post["headers"].get("x-api-key") == "synthetic-key-a" for post in posts))
                    events = [
                        json.loads(line[6:])
                        for line in bytes.fromhex(responses[0]["body"]).splitlines()
                        if line.startswith(b"data: ")
                    ]
                    self.assertEqual([response["status"] for response in responses], [200])
                    self.assertEqual([event["type"] for event in events], ["response.failed"])
                    self.assertEqual(events[0]["response"]["error"], {
                        "code": "provider_stream_error", "message": "unexpected end of stream",
                    })

    def test_native_anthropic_first_event_retry_budget_spans_model_chain(self):
        error = b'data: {"type":"error","error":{"type":"not_found_error","message":"synthetic unavailable"}}\n\n'
        turns = [{
            "model": "combo:flash,pro,synthetic-third",
            "input": "synthetic global first-event retry budget",
            "tools": [{"type": "web_search_preview"}],
        }]
        expected_models = {
            ORACLE_01651: ["deepseek-flash", "deepseek-v4-pro"],
            ORACLE: ["deepseek-v4-flash", "deepseek-v4-pro"],
            MODEX: ["deepseek-flash", "deepseek-v4-pro"],
        }
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary,
                    turns,
                    [{"status": 200, "content_type": "text/event-stream", "body": error}] * 3,
                    api_keys="synthetic-key-a",
                )
                self.assertEqual(
                    [json.loads(post["body"])["model"] for post in posts],
                    expected_models[binary],
                )
                self.assertEqual([response["status"] for response in responses], [200])
                events = [
                    json.loads(line[6:])
                    for line in bytes.fromhex(responses[0]["body"]).splitlines()
                    if line.startswith(b"data: ")
                ]
                self.assertEqual([event["type"] for event in events], ["response.failed"])
                self.assertEqual(events[0]["response"]["error"], {
                    "code": "provider_stream_error", "message": "unexpected end of stream",
                })

    def test_native_anthropic_auth_first_event_rotates_before_next_model(self):
        auth = b'data: {"type":"error","error":{"type":"invalid_api_key","message":"synthetic auth"}}\n\n'
        success = b"".join((
            b'data: {"type":"message_start","message":{"id":"msg-auth-ok","role":"assistant","model":"deepseek-flash","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
            b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":5}}\n\n',
            b'data: {"type":"message_stop"}\n\n',
        ))
        turns = [{
            "model": "combo:flash,pro",
            "input": "synthetic native auth retry precedence",
            "tools": [{"type": "web_search_preview"}],
        }]
        expected_models = {
            ORACLE_01651: ["deepseek-flash", "deepseek-flash"],
            ORACLE: ["deepseek-v4-flash", "deepseek-v4-flash"],
            MODEX: ["deepseek-flash", "deepseek-flash"],
        }
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary,
                    turns,
                    [
                        {"status": 200, "content_type": "text/event-stream", "body": auth},
                        {"status": 200, "content_type": "text/event-stream", "body": success},
                    ],
                    api_keys=KEYS,
                )
                self.assertEqual(
                    [post["headers"].get("x-api-key") for post in posts],
                    ["synthetic-key-a", "synthetic-key-b"],
                )
                self.assertEqual(
                    [json.loads(post["body"])["model"] for post in posts],
                    expected_models[binary],
                )
                self.assertEqual([response["status"] for response in responses], [200])

    def test_native_anthropic_does_not_replay_after_first_event_commit(self):
        request = [{
            "model": "combo:flash,pro",
            "input": "synthetic committed native stream",
            "tools": [{"type": "web_search_preview"}],
        }]
        committed = b"".join((
            b'data: {"type":"message_start","message":{"id":"msg-committed","role":"assistant","model":"deepseek-flash","usage":{"input_tokens":3,"output_tokens":0}}}\n\n',
            b'data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"kept before error"}}\n\n',
            b'data: {"type":"error","error":{"type":"not_found_error"}}\n\n',
        ))
        for binary in (ORACLE_01651, ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                posts, responses = observe_turns(
                    binary,
                    request,
                    [{"status": 200, "content_type": "text/event-stream", "body": committed}],
                    api_keys=KEYS,
                )
                self.assertEqual(len(posts), 1)
                self.assertEqual(json.loads(posts[0]["body"])["model"], "deepseek-flash" if binary in (ORACLE_01651, MODEX) else "deepseek-v4-flash")
                self.assertEqual([response["status"] for response in responses], [200])
                events = [
                    json.loads(line[6:])
                    for line in bytes.fromhex(responses[0]["body"]).splitlines()
                    if line.startswith(b"data: ")
                ]
                self.assertEqual(
                    [event["type"] for event in events],
                    ["response.created", "response.output_item.added", "response.output_text.delta", "response.failed"],
                )
                self.assertEqual(events[2]["delta"], "kept before error")
                self.assertEqual(events[3]["response"]["error"], {
                    "code": "not_found_error", "message": "Anthropic stream failed",
                })
