"""Compare buffered provider response shapes through all three Super processes."""

import hashlib
import json
import os
from pathlib import Path
import unittest

from test_cli import MODEX
from test_deepseek_continuation import observe_turns
from test_deepseek_web_search_mode_01651_04392 import ORACLE_01651, ORACLE_01651_SHA256


ORACLE_04392 = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_04392_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
BINARIES = (ORACLE_01651, ORACLE_04392, MODEX)
API_KEYS = "synthetic-key-a,synthetic-key-b"
DEEPSEEK_REQUEST = {"model": "deepseek-chat", "input": "synthetic buffered response"}
ANTHROPIC_REQUEST = {
    "model": "deepseek-chat",
    "input": "synthetic buffered response",
    "stream": False,
    "tools": [{"type": "web_search_preview"}],
}
DEEPSEEK_SUCCESS = (
    b'{"id":"chatcmpl_synthetic","model":"deepseek-chat","created":42,'
    b'"choices":[{"message":{"role":"assistant","content":"synthetic DeepSeek response"},'
    b'"finish_reason":"stop"}],"usage":{"prompt_tokens":2,"completion_tokens":3,"total_tokens":5}}'
)
ANTHROPIC_SUCCESS = (
    b'{"id":"msg_synthetic","type":"message","role":"assistant",'
    b'"content":[{"type":"text","text":"synthetic Anthropic response"}],'
    b'"model":"claude-test","stop_reason":"end_turn",'
    b'"usage":{"input_tokens":2,"output_tokens":3}}'
)


def _json_response(response):
    value = json.loads(bytes.fromhex(response["body"]))
    value.pop("created_at", None)
    return value


class ProviderBufferedResponseShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary, digest in (
            (ORACLE_01651, ORACLE_01651_SHA256),
            (ORACLE_04392, ORACLE_04392_SHA256),
        ):
            if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != digest:
                raise AssertionError(f"Prodex oracle does not match its pinned release: {binary}")
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")

    def test_deepseek_nonobject_json_roots_keep_release_error_without_retry(self):
        for name, body in (("null", b"null"), ("scalar", b"7"), ("array", b"[]")):
            for binary in BINARIES:
                with self.subTest(shape=name, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary,
                        [DEEPSEEK_REQUEST],
                        [{"status": 200, "content_type": "application/json", "body": body}],
                        api_keys=API_KEYS,
                    )
                    self.assertEqual(len(posts), 1, "a successful malformed body must not retry")
                    self.assertEqual(posts[0]["path"], "/v1/chat/completions")
                    self.assertEqual(posts[0]["headers"]["authorization"], "Bearer synthetic-key-a")
                    self.assertEqual([response["status"] for response in responses], [500])
                    self.assertEqual(bytes.fromhex(responses[0]["body"]), b"")

    def test_deepseek_valid_and_malformed_json_keep_release_mapping_without_retry(self):
        replies = (
            ("valid object", DEEPSEEK_SUCCESS, 200, None),
            ("malformed JSON", b"{", 502, b"provider response could not be processed"),
        )
        for name, body, status, error_body in replies:
            observations = []
            for binary in BINARIES:
                with self.subTest(shape=name, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary,
                        [DEEPSEEK_REQUEST],
                        [{"status": 200, "content_type": "application/json", "body": body}],
                        api_keys=API_KEYS,
                    )
                    self.assertEqual(len(posts), 1, "buffered translation failures must not retry")
                    self.assertEqual(posts[0]["path"], "/v1/chat/completions")
                    self.assertEqual([response["status"] for response in responses], [status])
                    payload = bytes.fromhex(responses[0]["body"])
                    if error_body is not None:
                        self.assertEqual(payload, error_body)
                    if status == 200:
                        observations.append(_json_response(responses[0]))
            if observations:
                self.assertEqual(observations[1], observations[0])
                self.assertEqual(observations[2], observations[0])
                self.assertEqual(
                    observations[0]["output"][0]["content"][0]["text"],
                    "synthetic DeepSeek response",
                )

    def test_anthropic_buffered_root_shapes_and_valid_message_match_releases(self):
        cases = (
            ("null", b"null", 502),
            ("scalar", b"7", 502),
            ("array", b"[]", 502),
            ("malformed JSON", b"{", 502),
            ("valid message", ANTHROPIC_SUCCESS, 200),
        )
        for name, body, status in cases:
            observations = []
            for binary in BINARIES:
                with self.subTest(shape=name, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary,
                        [ANTHROPIC_REQUEST],
                        [{"status": 200, "content_type": "application/json", "body": body}],
                        api_keys=API_KEYS,
                    )
                    self.assertEqual(len(posts), 1, "buffered translation failures must not retry")
                    self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(posts[0]["headers"]["x-api-key"], "synthetic-key-a")
                    self.assertEqual([response["status"] for response in responses], [status])
                    if status != 200:
                        self.assertEqual(
                            bytes.fromhex(responses[0]["body"]),
                            b"provider response could not be processed",
                        )
                    else:
                        observations.append(_json_response(responses[0]))
            if observations:
                self.assertEqual(observations[1], observations[0])
                self.assertEqual(observations[2], observations[0])
                self.assertEqual(
                    observations[0]["output"][0]["content"][0]["text"],
                    "synthetic Anthropic response",
                )

    def test_anthropic_tool_use_empty_string_fields_match_releases(self):
        cases = (
            ("empty ID", {"type": "tool_use", "id": "", "name": "lookup", "input": {}}),
            ("empty name", {"type": "tool_use", "id": "call_synthetic", "name": "", "input": {}}),
            ("both empty", {"type": "tool_use", "id": "", "name": "", "input": {}}),
        )
        for name, block in cases:
            observations = []
            reply = {
                "status": 200,
                "content_type": "application/json",
                "body": json.dumps({
                    "id": "msg_synthetic",
                    "type": "message",
                    "role": "assistant",
                    "content": [block],
                    "model": "claude-test",
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 2, "output_tokens": 1},
                }, separators=(",", ":")).encode(),
            }
            for binary in BINARIES:
                with self.subTest(shape=name, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary,
                        [ANTHROPIC_REQUEST],
                        [reply],
                        api_keys=API_KEYS,
                    )
                    self.assertEqual(len(posts), 1)
                    self.assertEqual(posts[0]["path"], "/anthropic/v1/messages")
                    self.assertEqual([response["status"] for response in responses], [200])
                    observations.append(_json_response(responses[0]))
            self.assertEqual(observations[1], observations[0])
            self.assertEqual(observations[2], observations[0])
            self.assertEqual(observations[0]["output"][0]["call_id"], block["id"])
            self.assertEqual(observations[0]["output"][0]["name"], block["name"])

        invalid_cases = (
            ("missing ID", {"type": "tool_use", "name": "lookup", "input": {}}),
            ("non-string ID", {"type": "tool_use", "id": 7, "name": "lookup", "input": {}}),
            ("missing name", {"type": "tool_use", "id": "call_synthetic", "input": {}}),
            ("non-string name", {"type": "tool_use", "id": "call_synthetic", "name": 7, "input": {}}),
        )
        for name, block in invalid_cases:
            response_bodies = []
            reply = {
                "status": 200,
                "content_type": "application/json",
                "body": json.dumps({
                    "id": "msg_synthetic",
                    "type": "message",
                    "role": "assistant",
                    "content": [block],
                    "model": "claude-test",
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 2, "output_tokens": 1},
                }, separators=(",", ":")).encode(),
            }
            for binary in BINARIES:
                with self.subTest(shape=name, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary,
                        [ANTHROPIC_REQUEST],
                        [reply],
                        api_keys=API_KEYS,
                    )
                    self.assertEqual(len(posts), 1)
                    self.assertEqual([response["status"] for response in responses], [502])
                    response_bodies.append(bytes.fromhex(responses[0]["body"]))
            self.assertEqual(response_bodies[1], response_bodies[0])
            self.assertEqual(response_bodies[2], response_bodies[0])

    def test_http_503_retry_rotates_credentials_for_both_buffered_routes(self):
        cases = (
            ("DeepSeek", DEEPSEEK_REQUEST, "/v1/chat/completions", DEEPSEEK_SUCCESS, "authorization"),
            ("Anthropic", ANTHROPIC_REQUEST, "/anthropic/v1/messages", ANTHROPIC_SUCCESS, "x-api-key"),
        )
        error = b'{"error":{"code":"server_is_overloaded"}}'
        for name, request, path, success, auth_header in cases:
            for binary in BINARIES:
                with self.subTest(provider=name, binary=str(binary)):
                    posts, responses = observe_turns(
                        binary,
                        [request],
                        [
                            {"status": 503, "content_type": "application/json", "body": error},
                            {"status": 200, "content_type": "application/json", "body": success},
                        ],
                        api_keys=API_KEYS,
                    )
                    self.assertEqual(len(posts), 2)
                    self.assertEqual([post["path"] for post in posts], [path, path])
                    expected_keys = (
                        ["Bearer synthetic-key-a", "Bearer synthetic-key-b"]
                        if auth_header == "authorization"
                        else ["synthetic-key-a", "synthetic-key-b"]
                    )
                    self.assertEqual(
                        [post["headers"][auth_header] for post in posts],
                        expected_keys,
                    )
                    self.assertEqual([response["status"] for response in responses], [200])


if __name__ == "__main__":
    unittest.main()
