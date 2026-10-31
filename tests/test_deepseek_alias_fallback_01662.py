"""Compare DeepSeek alias retry behavior with Prodex 0.166.2 in loopback-only runs."""

import hashlib
import json
import unittest

from manual_real_codex_01660_route_comparison import require_isolated_environment
from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY, json_bytes


MODEL_NOT_SUPPORTED = {
    "status": 404,
    "content_type": "application/json",
    "body": b'{"error":{"code":"model_not_supported","message":"synthetic unsupported model"}}',
}
GENERIC_NOT_FOUND = {
    "status": 404,
    "content_type": "application/json",
    "body": b'{"error":{"code":"synthetic_not_found","message":"synthetic missing route"}}',
}
GENERIC_BAD_REQUEST = {
    "status": 400,
    "content_type": "application/json",
    "body": b'{"error":{"code":"synthetic_invalid_request","message":"synthetic invalid request"}}',
}
POLICY_CAPACITY_UNAVAILABLE = {
    "status": 503,
    "content_type": "application/json",
    "body": b'{"error":{"code":"policy_capacity_unavailable","message":"synthetic policy"}}',
}


def buffered_reply(index):
    return {
        "status": 200,
        "content_type": "application/json",
        "body": json_bytes({
            "id": f"synthetic-alias-{index}",
            "model": "deepseek-chat",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "synthetic alias reply"},
                "finish_reason": "stop",
            }],
        }),
    }


def chat_stream_reply(index):
    initial = {
        "id": f"chatcmpl_synthetic_alias_{index}",
        "created": 42,
        "model": "deepseek-chat",
        "choices": [{"index": 0, "delta": {"content": "synthetic stream"}, "finish_reason": None}],
    }
    terminal = {
        "id": f"chatcmpl_synthetic_alias_{index}",
        "created": 42,
        "model": "deepseek-chat",
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    return {
        "status": 200,
        "content_type": "text/event-stream",
        "body": b"".join(
            b"data: " + json_bytes(chunk) + b"\n\n"
            for chunk in (initial, terminal)
        ) + b"data: [DONE]\n\n",
    }


def native_error_reply():
    return {
        "status": 200,
        "content_type": "text/event-stream",
        "body": b'event: error\ndata: {"type":"error","error":{"type":"not_found_error","message":"synthetic unsupported model"}}\n\n',
    }


def native_overloaded_reply():
    return {
        "status": 200,
        "content_type": "text/event-stream",
        "body": b'event: error\ndata: {"type":"error","error":{"type":"overloaded_error","message":"synthetic overloaded backend"}}\n\n',
    }


def native_success_reply():
    events = [
        {"type": "message_start", "message": {"id": "msg_synthetic_alias", "model": "deepseek-flash", "usage": {"input_tokens": 1, "output_tokens": 0}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "synthetic native reply"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 2}},
        {"type": "message_stop"},
    ]
    return {
        "status": 200,
        "content_type": "text/event-stream",
        "body": b"".join(b"data: " + json_bytes(event) + b"\n\n" for event in events),
    }


def upstream_models(posts):
    return [json.loads(post["body"])["model"] for post in posts]


class DeepSeekAliasFallback01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_isolated_environment()
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def compare(self, turns, replies, **options):
        results = {}
        for label, binary in (("oracle", ORACLE), ("modex", MODEX)):
            posts, responses = observe_turns(
                binary, turns, replies, latest_version="0.166.2", **options,
            )
            results[label] = (posts, responses)
        return results

    def test_alias_orders_retryable_404_and_fixed_model_control(self):
        cases = (
            ("flash", ["deepseek-flash", "deepseek-v4-pro"]),
            ("auto", ["deepseek-v4-pro", "deepseek-flash"]),
            ("pro", ["deepseek-v4-pro", "deepseek-flash"]),
        )
        for index, (alias, chain) in enumerate(cases):
            results = self.compare(
                [{"model": alias, "input": f"synthetic alias {index}"}],
                [MODEL_NOT_SUPPORTED, buffered_reply(index)],
            )
            for label, (posts, responses) in results.items():
                with self.subTest(binary=label, alias=alias):
                    self.assertEqual(upstream_models(posts), chain)
                    self.assertEqual([post["path"] for post in posts],
                                     ["/v1/chat/completions"] * len(chain))
                    self.assertEqual([post["headers"]["authorization"] for post in posts],
                                     ["Bearer " + SYNTHETIC_API_KEY] * len(chain))
                    self.assertEqual([response["status"] for response in responses], [200])

        for alias, expected_model in (("default", "default"), ("", "deepseek-v4-pro")):
            results = self.compare(
                [{"model": alias, "input": f"synthetic fixed alias {alias}"}],
                [MODEL_NOT_SUPPORTED],
            )
            for label, (posts, responses) in results.items():
                with self.subTest(binary=label, alias=alias):
                    self.assertEqual(upstream_models(posts), [expected_model])
                    self.assertEqual([response["status"] for response in responses], [404])

        # A concrete model ID remains a single candidate and does not rotate on NotFound.
        results = self.compare(
            [{"model": "deepseek-v4-pro", "input": "synthetic fixed model"}],
            [MODEL_NOT_SUPPORTED],
            api_keys="synthetic-key-a,synthetic-key-b",
        )
        for label, (posts, responses) in results.items():
            with self.subTest(binary=label, model="deepseek-v4-pro"):
                self.assertEqual(upstream_models(posts), ["deepseek-v4-pro"])
                self.assertEqual([post["headers"]["authorization"] for post in posts],
                                 ["Bearer synthetic-key-a"])
                self.assertEqual([response["status"] for response in responses], [404])

    def test_generic_404_uses_status_class_but_other_4xx_does_not_retry(self):
        cases = (
            (MODEL_NOT_SUPPORTED, ["deepseek-flash", "deepseek-v4-pro"], 200),
            (GENERIC_NOT_FOUND, ["deepseek-flash", "deepseek-v4-pro"], 200),
            (GENERIC_BAD_REQUEST, ["deepseek-flash"], 400),
        )
        for index, (error, expected_models, expected_status) in enumerate(cases):
            replies = [error] + ([buffered_reply(index)] if expected_status == 200 else [])
            results = self.compare(
                [{"model": "flash", "input": f"synthetic error class {index}"}],
                replies,
            )
            for label, (posts, responses) in results.items():
                with self.subTest(binary=label, status=error["status"]):
                    self.assertEqual(upstream_models(posts), expected_models)
                    self.assertEqual([response["status"] for response in responses], [expected_status])

    def test_503_retries_models_before_rotating_credentials(self):
        transient = {
            "status": 503,
            "content_type": "application/json",
            "body": b'{"error":{"code":"synthetic_backend_error","message":"synthetic unavailable"}}',
        }
        results = self.compare(
            [{"model": "flash", "input": "synthetic transient fallback"}],
            [transient, transient, buffered_reply(3)],
            api_keys="synthetic-key-a,synthetic-key-b",
        )
        expected_models = ["deepseek-flash", "deepseek-v4-pro", "deepseek-flash"]
        expected_auth = ["Bearer synthetic-key-a", "Bearer synthetic-key-a", "Bearer synthetic-key-b"]
        for label, (posts, responses) in results.items():
            with self.subTest(binary=label):
                self.assertEqual(upstream_models(posts), expected_models)
                self.assertEqual([post["headers"]["authorization"] for post in posts], expected_auth)
                self.assertEqual([response["status"] for response in responses], [200])

    def test_policy_capacity_503_retries_alias_models_before_rotating_credentials(self):
        cases = (
            ("flash", ["deepseek-flash", "deepseek-v4-pro"]),
            ("auto", ["deepseek-v4-pro", "deepseek-flash"]),
        )
        for index, (alias, chain) in enumerate(cases):
            results = self.compare(
                [{"model": alias, "input": f"synthetic policy capacity {index}"}],
                [POLICY_CAPACITY_UNAVAILABLE, POLICY_CAPACITY_UNAVAILABLE, buffered_reply(8)],
                api_keys="synthetic-key-a,synthetic-key-b",
            )
            for label, (posts, responses) in results.items():
                with self.subTest(binary=label, alias=alias):
                    self.assertEqual(upstream_models(posts), [chain[0], chain[1], chain[0]])
                    self.assertEqual([post["headers"]["authorization"] for post in posts], [
                        "Bearer synthetic-key-a",
                        "Bearer synthetic-key-a",
                        "Bearer synthetic-key-b",
                    ])
                    self.assertEqual([response["status"] for response in responses], [200])

    def test_streaming_alias_retries_before_committing_the_response(self):
        cases = (
            ("flash", ["deepseek-flash", "deepseek-v4-pro"]),
            ("auto", ["deepseek-v4-pro", "deepseek-flash"]),
        )
        for index, (alias, chain) in enumerate(cases):
            results = self.compare(
                [{"model": alias, "input": f"synthetic stream {index}", "stream": True}],
                [MODEL_NOT_SUPPORTED, chat_stream_reply(index)],
            )
            for label, (posts, responses) in results.items():
                with self.subTest(binary=label, alias=alias):
                    self.assertEqual(upstream_models(posts), chain)
                    self.assertEqual([response["status"] for response in responses], [200])
                    for response in responses:
                        headers = {name.lower(): value for name, value in response["headers"].items()}
                        self.assertIn("text/event-stream", headers["content-type"])
                        self.assertIn(b"event: response.completed", bytes.fromhex(response["body"]))

    def test_native_first_event_allows_one_alias_retry_only(self):
        turn = {
            "model": "auto",
            "input": "synthetic native first event",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        replies = [native_error_reply(), native_error_reply()]
        results = self.compare(
            [turn], replies,
            shared_config='[deepseek]\nweb_search_mode = "anthropic"\n',
        )
        expected_models = ["deepseek-v4-pro", "deepseek-flash"]
        for label, (posts, responses) in results.items():
            with self.subTest(binary=label):
                self.assertEqual(upstream_models(posts), expected_models)
                self.assertEqual([post["path"] for post in posts],
                                 ["/anthropic/v1/messages", "/anthropic/v1/messages"])
                self.assertEqual([post["headers"]["x-api-key"] for post in posts],
                                 [SYNTHETIC_API_KEY, SYNTHETIC_API_KEY])
                self.assertEqual([response["status"] for response in responses], [200])
                self.assertIn(b"event: response.failed", bytes.fromhex(responses[0]["body"]))

    def test_native_first_event_success_fallback_does_not_replay_after_commit(self):
        turn = {
            "model": "auto",
            "input": "synthetic native fallback success",
            "stream": True,
            "tools": [{"type": "web_search_preview"}],
        }
        results = self.compare(
            [turn], [native_error_reply(), native_success_reply()],
            shared_config='[deepseek]\nweb_search_mode = "anthropic"\n',
        )
        for label, (posts, responses) in results.items():
            with self.subTest(binary=label):
                self.assertEqual(upstream_models(posts), ["deepseek-v4-pro", "deepseek-flash"])
                self.assertEqual([response["status"] for response in responses], [200])
                self.assertEqual(len(posts), 2)
                self.assertIn(b"event: response.completed", bytes.fromhex(responses[0]["body"]))

    def test_native_overloaded_first_event_uses_one_model_retry_before_key_rotation(self):
        cases = (
            ("flash", ["deepseek-flash", "deepseek-v4-pro"]),
            ("auto", ["deepseek-v4-pro", "deepseek-flash"]),
        )
        for alias, expected_models in cases:
            results = self.compare(
                [{
                    "model": alias,
                    "input": f"synthetic native overload {alias}",
                    "stream": True,
                    "tools": [{"type": "web_search_preview"}],
                }],
                [native_overloaded_reply(), native_overloaded_reply()],
                api_keys="synthetic-key-a,synthetic-key-b",
                shared_config='[deepseek]\nweb_search_mode = "anthropic"\n',
            )
            for label, (posts, responses) in results.items():
                with self.subTest(binary=label, alias=alias):
                    self.assertEqual(upstream_models(posts), expected_models)
                    self.assertEqual([post["headers"]["x-api-key"] for post in posts],
                                     ["synthetic-key-a", "synthetic-key-a"])
                    self.assertEqual([post["path"] for post in posts],
                                     ["/anthropic/v1/messages"] * len(expected_models))
                    self.assertEqual([response["status"] for response in responses], [200])
                    self.assertEqual(len(posts), 2)


if __name__ == "__main__":
    unittest.main()
