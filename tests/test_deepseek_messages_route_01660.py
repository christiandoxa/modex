"""Compare the native DeepSeek Anthropic Messages route with Prodex 0.166.0."""

import hashlib
import json
import unittest
from unittest.mock import patch

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_continuation import observe_turns
from test_local_rewrite import SYNTHETIC_API_KEY, UpstreamHandler


def _anthropic_reply(identifier, text="synthetic reply"):
    return {
        "id": identifier, "type": "message", "role": "assistant",
        "model": "deepseek-chat", "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn", "usage": {"input_tokens": 2, "output_tokens": 1},
    }


def _body(response):
    return bytes.fromhex(response["body"])


def _headers(row):
    return {name.lower(): value for name, value in row.items()}


class DeepSeekMessagesRoute01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def test_root_and_v1_routes_forward_methods_bodies_and_responses(self):
        requests = [
            {"_path": "/messages?probe=root", "_method": "POST",
             "_raw_body": '{"model": "deepseek-chat", "messages": [], "max_tokens": 3}'},
            {"_path": "/v1/messages?probe=v1", "_method": "GET", "_raw_body": ""},
            {"_path": "/messages?probe=head", "_method": "HEAD", "_raw_body": ""},
            {"_path": "/v1/messages?probe=put", "_method": "PUT",
             "_raw_body": '{"model":"deepseek-chat","messages":[{"role":"user","content":"synthetic"}]}'},
        ]
        replies = [
            {"status": 201, "content_type": "application/json", "body": json.dumps(
                _anthropic_reply("msg_post"), separators=(",", ":"),
            ).encode()},
            {"status": 202, "content_type": "application/json", "body": json.dumps(
                _anthropic_reply("msg_get"), separators=(",", ":"),
            ).encode()},
            {"status": 203, "content_type": "application/json", "body": json.dumps(
                _anthropic_reply("msg_head"), separators=(",", ":"),
            ).encode()},
            {"status": 422, "content_type": "application/json", "body": b'{"error":"synthetic put error"}'},
        ]
        expected_methods = ["POST", "GET", "HEAD", "PUT"]
        expected_bodies = [request["_raw_body"].encode() for request in requests]
        observations = []
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                with (
                    patch.object(UpstreamHandler, "do_HEAD", UpstreamHandler.do_POST, create=True),
                    patch.object(UpstreamHandler, "do_PUT", UpstreamHandler.do_POST, create=True),
                ):
                    upstream, responses = observe_turns(
                        binary, requests, replies, latest_version="0.166.0",
                    )
                self.assertEqual([row["method"] for row in upstream], expected_methods)
                self.assertEqual([row["path"] for row in upstream], ["/anthropic/v1/messages"] * 4)
                self.assertEqual([row["body"] for row in upstream], expected_bodies)
                for row in upstream:
                    headers = _headers(row["headers"])
                    self.assertEqual(headers["x-api-key"], SYNTHETIC_API_KEY)
                    self.assertEqual(headers["anthropic-version"], "2023-06-01")
                    self.assertNotIn("authorization", headers)
                self.assertNotIn("content-length", _headers(upstream[1]["headers"]))
                self.assertNotIn("content-length", _headers(upstream[2]["headers"]))
                self.assertEqual(_headers(upstream[0]["headers"])["content-length"], str(len(expected_bodies[0])))
                self.assertEqual(_headers(upstream[3]["headers"])["content-length"], str(len(expected_bodies[3])))
                self.assertEqual([row["status"] for row in responses], [201, 202, 203, 422])
                self.assertEqual([_body(row) for row in responses], [
                    json.dumps(_anthropic_reply("msg_post"), separators=(",", ":")).encode(),
                    json.dumps(_anthropic_reply("msg_get"), separators=(",", ":")).encode(),
                    b"",
                    b'{"error":"synthetic put error"}',
                ])
                observations.append((upstream, responses))

        self.assertEqual(
            [(row["method"], row["path"], row["body"]) for row in observations[0][0]],
            [(row["method"], row["path"], row["body"]) for row in observations[1][0]],
        )
        self.assertEqual(
            [(row["status"], _body(row)) for row in observations[0][1]],
            [(row["status"], _body(row)) for row in observations[1][1]],
        )

    def test_malformed_body_error_and_sse_response_are_transparent(self):
        raw_body = "not-json\x00"
        event_body = (
            b'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_stream"}}\n\n'
            b'event: message_stop\ndata: {"type":"message_stop"}\n\n'
        )
        requests = [
            {"_path": "/messages?probe=error", "_raw_body": raw_body},
            {"_path": "/v1/messages?probe=stream", "_raw_body": '{"model":"deepseek-chat","messages":[],"stream":true}'},
            {"_path": "/v1/responses", "model": "deepseek-chat", "input": "synthetic followup",
             "previous_response_id": "msg_stream"},
        ]
        replies = [
            {"status": 422, "content_type": "application/json", "body": b'{"error":"synthetic error"}',
             "response_headers": [("Content-Type", "application/json"), ("X-Synthetic-Provider", "preserved")]},
            {"status": 200, "content_type": "text/event-stream; charset=utf-8", "body": event_body,
             "chunked": True, "chunk_size": 7},
        ]
        observations = []
        for binary in (ORACLE, MODEX):
            upstream, responses = observe_turns(binary, requests, replies, latest_version="0.166.0")
            self.assertEqual([row["body"] for row in upstream], [raw_body.encode(), requests[1]["_raw_body"].encode()])
            self.assertEqual([row["path"] for row in upstream], ["/anthropic/v1/messages"] * 2)
            self.assertEqual([row["status"] for row in responses], [422, 200, 503])
            self.assertEqual([_body(row) for row in responses[:2]], [b'{"error":"synthetic error"}', event_body])
            self.assertIn(b"bound_continuation_unavailable", _body(responses[2]))
            self.assertEqual(_headers(responses[0]["headers"])["x-synthetic-provider"], "preserved")
            observations.append(responses)
        self.assertEqual(
            [(row["status"], _body(row)) for row in observations[0]],
            [(row["status"], _body(row)) for row in observations[1]],
        )

    def test_credentials_are_replaced_and_cookies_are_not_forwarded(self):
        request = {
            "_path": "/messages", "_raw_body": '{"model":"deepseek-chat","messages":[]}',
            "_headers": {
                "Cookie": "synthetic-cookie-secret",
                "X-Api-Key": "client-key-sentinel",
                "Anthropic-Version": "client-version-sentinel",
                "X-Synthetic-Trace": "synthetic-trace",
            },
        }
        upstream, responses = observe_turns(
            MODEX, [request], [{"status": 200, "content_type": "application/json",
                                "body": json.dumps(_anthropic_reply("msg_auth"), separators=(",", ":")).encode()}],
            latest_version="0.166.0",
        )
        self.assertEqual(len(upstream), 1)
        headers = _headers(upstream[0]["headers"])
        self.assertEqual(headers["x-api-key"], SYNTHETIC_API_KEY)
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(headers["x-synthetic-trace"], "synthetic-trace")
        self.assertNotIn("cookie", headers)
        self.assertNotIn("authorization", headers)
        self.assertEqual(responses[0]["status"], 200)

    def test_invalid_local_token_does_not_dispatch_provider_request(self):
        upstream, responses = observe_turns(
            MODEX,
            [{"_path": "/v1/messages", "_raw_body": "{}",
              "_headers": {"Authorization": "Bearer invalid-synthetic-token"}}],
            [], latest_version="0.166.0",
        )
        self.assertEqual(upstream, [])
        self.assertEqual([row["status"] for row in responses], [401])

    def test_messages_ids_keep_existing_continuation_binding_guard(self):
        turns = [
            {"_path": "/messages", "_raw_body": '{"model":"deepseek-chat","messages":[]}'},
            {"_path": "/v1/responses", "model": "deepseek-chat", "input": "synthetic followup",
             "previous_response_id": "msg_unbound"},
        ]
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, turns, [{"status": 200, "content_type": "application/json",
                                     "body": json.dumps(_anthropic_reply("msg_unbound"), separators=(",", ":")).encode()}],
                    latest_version="0.166.0",
                )
                self.assertEqual([row["path"] for row in upstream], ["/anthropic/v1/messages"])
                self.assertEqual([row["status"] for row in responses], [200, 503])
                self.assertIn(b"bound_continuation_unavailable", _body(responses[1]))

    def test_route_aliases_stay_exact(self):
        turns = [
            {"_path": path, "model": "deepseek-chat", "messages": []}
            for path in ("/messages/", "/v1/messages/", "/tenant/messages")
        ]
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(binary, turns, [], latest_version="0.166.0")
                self.assertEqual(upstream, [])
                self.assertEqual([row["status"] for row in responses], [404, 404, 404])

    def test_concurrent_alias_requests_use_only_configured_provider_keys(self):
        turns = [
            {"_path": "/messages?concurrent=1", "model": "deepseek-chat", "messages": [{"role": "user", "content": "synthetic 1"}]},
            {"_path": "/v1/messages?concurrent=2", "model": "deepseek-chat", "messages": [{"role": "user", "content": "synthetic 2"}]},
            {"_path": "/messages?concurrent=3", "model": "deepseek-chat", "messages": [{"role": "user", "content": "synthetic 3"}]},
            {"_path": "/v1/messages?concurrent=4", "model": "deepseek-chat", "messages": [{"role": "user", "content": "synthetic 4"}]},
        ]
        replies = [
            {"status": 200, "content_type": "application/json",
             "body": json.dumps(_anthropic_reply(f"msg_concurrent_{index}"), separators=(",", ":")).encode()}
            for index in range(4)
        ]
        upstream, responses = observe_turns(
            MODEX, turns, replies, api_keys="synthetic-provider-key-a,synthetic-provider-key-b",
            concurrent=True, latest_version="0.166.0",
        )
        self.assertEqual(len(upstream), 4)
        self.assertEqual([row["path"] for row in upstream], ["/anthropic/v1/messages"] * 4)
        self.assertEqual({row["body"] for row in upstream}, {
            json.dumps({key: value for key, value in turn.items() if not key.startswith("_")}, separators=(",", ":")).encode()
            for turn in turns
        })
        keys = [_headers(row["headers"])["x-api-key"] for row in upstream]
        self.assertEqual(set(keys), {"synthetic-provider-key-a", "synthetic-provider-key-b"})
        self.assertNotIn("authorization", _headers(upstream[0]["headers"]))
        self.assertEqual([row["status"] for row in responses], [200] * 4)

    def test_retryable_auth_error_rotates_without_exposing_error_or_losing_binding(self):
        raw_body = '{"model": "deepseek-chat", "messages": []}'
        message_body = json.dumps(_anthropic_reply("msg_rotated"), separators=(",", ":")).encode()
        turns = [
            {"_path": "/messages", "_raw_body": raw_body},
            {"_path": "/v1/responses", "model": "deepseek-chat", "input": "synthetic followup",
             "previous_response_id": "msg_rotated"},
        ]
        replies = [
            {"status": 401, "content_type": "application/json",
             "body": b'{"error":{"type":"authentication_error","message":"synthetic invalid key"}}'},
            {"status": 200, "content_type": "application/json", "body": message_body},
        ]
        for binary in (ORACLE, MODEX):
            with self.subTest(binary=str(binary)):
                upstream, responses = observe_turns(
                    binary, turns, replies,
                    api_keys="synthetic-invalid-key,synthetic-valid-key",
                    latest_version="0.166.0",
                )
                self.assertEqual([row["path"] for row in upstream], ["/anthropic/v1/messages"] * 2)
                self.assertEqual([row["body"] for row in upstream], [raw_body.encode()] * 2)
                self.assertEqual([_headers(row["headers"])["x-api-key"] for row in upstream], [
                    "synthetic-invalid-key", "synthetic-valid-key",
                ])
                self.assertEqual([row["status"] for row in responses], [200, 503])
                self.assertEqual(_body(responses[0]), message_body)
                self.assertIn(b"bound_continuation_unavailable", _body(responses[1]))


if __name__ == "__main__":
    unittest.main()
