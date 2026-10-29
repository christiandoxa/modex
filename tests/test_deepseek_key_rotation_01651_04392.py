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


class DeepSeekKeyRotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary, digest in ((ORACLE_01651, ORACLE_01651_SHA256), (ORACLE, ORACLE_SHA256)):
            if hashlib.sha256(binary.read_bytes()).hexdigest() != digest:
                raise AssertionError("The Prodex oracle does not match its pinned release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")

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
        request = [{"model": "deepseek-chat", "input": "synthetic retry"}]
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
            for binary in (ORACLE_01651, ORACLE, MODEX):
                with self.subTest(case=name, binary=str(binary)):
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
