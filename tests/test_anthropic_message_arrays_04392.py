"""Compare the safe Anthropic message-array subset with frozen Prodex 0.439.2."""

import hashlib
import json
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_provider_tools_04392_characterization import _run


INVALID_REQUEST_BODY = b'{"error":{"code":"invalid_request","message":"request is incompatible with DeepSeek native Anthropic web-search translation","type":"invalid_request_error"}}'


class AnthropicMessageArrayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.439.2")
        if not MODEX.is_file():
            raise AssertionError(f"Modex binary has not been built: {MODEX}")

    def test_simple_message_arrays_match_release_request_and_response(self):
        cases = {
            "single user": [
                {"type": "message", "role": "user", "content": "synthetic query"},
            ],
            "default user role": [
                {"content": "synthetic query"},
            ],
            "adjacent same-role messages": [
                {"type": "message", "role": "user", "content": "prior query"},
                {"role": "user", "content": "current query"},
                {"role": "user", "content": "follow-up query"},
            ],
            "alternating roles": [
                {"role": "user", "content": "first query"},
                {"type": "message", "role": "assistant", "content": "prior answer"},
                {"type": "message", "role": "assistant", "content": "continued answer"},
                {"type": "message", "role": "user", "content": "next query"},
            ],
            "system and developer messages": [
                {"type": "message", "role": "system", "content": "first system note"},
                {"type": "message", "role": "user", "content": "first query"},
                {"role": "developer", "content": "second system note"},
                {"type": "message", "role": "user", "content": "second query"},
                {"type": "message", "role": "assistant", "content": "prior answer"},
            ],
            "Unicode content": [
                {"type": "message", "role": "user", "content": "こんにちは 🦀 café\nquoted \"text\""},
            ],
            "zero-width content": [
                {"type": "message", "role": "user", "content": "\u200b"},
            ],
            "Unicode whitespace with zero-width text": [
                {"type": "message", "role": "user", "content": "\u00a0\u200b\u3000"},
            ],
        }
        for name, input_messages in cases.items():
            with self.subTest(case=name):
                request = {
                    "model": "deepseek-chat",
                    "input": input_messages,
                    "stream": False,
                    "tools": [{"type": "web_search_preview"}],
                }
                reference = _run(ORACLE, request, scenario="anthropic-buffered")
                actual = _run(MODEX, request, scenario="anthropic-buffered")
                self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                self.assertEqual((actual["exit_code"], actual["status"]), (0, 200))
                self.assertEqual(len(reference["upstream"]), 1)
                self.assertEqual(len(actual["upstream"]), 1)
                self.assertEqual(actual["upstream"][0]["path"], reference["upstream"][0]["path"])
                self.assertEqual(bytes.fromhex(actual["upstream"][0]["body"]), bytes.fromhex(reference["upstream"][0]["body"]))

                expected_response = json.loads(reference["response_body"])
                actual_response = json.loads(actual["response_body"])
                expected_response.pop("created_at")
                actual_response.pop("created_at")
                self.assertEqual(actual_response, expected_response)
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(actual["state"]["leftovers"], [])

    def test_empty_and_whitespace_arrays_match_release(self):
        cases = {
            "empty array": [],
            "empty content": [{"type": "message", "role": "user", "content": ""}],
            "ASCII whitespace": [{"type": "message", "role": "user", "content": " \t\n "}],
            "Unicode whitespace": [{"type": "message", "role": "user", "content": "\u00a0\u3000"}],
            "blank adjacent content": [
                {"type": "message", "role": "user", "content": "   "},
                {"type": "message", "role": "user", "content": "preserved query"},
            ],
            "system only": [{"type": "message", "role": "system", "content": "system note"}],
            "developer and blank user": [
                {"role": "developer", "content": "system note"},
                {"role": "user", "content": "\t"},
            ],
            "blank between roles": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "\u3000"},
                {"role": "user", "content": "second"},
            ],
            "blank system with user": [
                {"role": "system", "content": ""},
                {"role": "developer", "content": " \t"},
                {"role": "user", "content": "query"},
            ],
        }
        for name, input_messages in cases.items():
            with self.subTest(case=name):
                request = {
                    "model": "deepseek-chat",
                    "input": input_messages,
                    "stream": False,
                    "tools": [{"type": "web_search_preview"}],
                }
                actual = _run(MODEX, request, scenario="anthropic-buffered")
                self.assertEqual(actual["state"]["leftovers"], [])
                reference = _run(ORACLE, request, scenario="anthropic-buffered")
                expected_status = 200 if name in ("blank adjacent content", "blank between roles", "blank system with user") else 400
                self.assertEqual(reference["status"], expected_status)
                self.assertEqual((actual["exit_code"], actual["status"]), (reference["exit_code"], reference["status"]))
                self.assertEqual(len(actual["upstream"]), len(reference["upstream"]))
                if reference["status"] == 200:
                    self.assertEqual(actual["upstream_body"], reference["upstream_body"])
                else:
                    self.assertEqual(reference["response_body"], INVALID_REQUEST_BODY)
                    self.assertEqual(actual["response_body"], reference["response_body"])
                self.assertEqual(reference["state"]["leftovers"], [])

    def test_unknown_roles_and_message_metadata_match_release(self):
        cases = {
            "typed unknown role": [{"type": "message", "role": "critic", "content": "synthetic text"}],
            "untyped unknown role": [{"role": "critic", "content": "synthetic text"}],
            "untyped null role": [{"role": None, "content": "synthetic text"}],
            "untyped numeric role": [{"role": 7, "content": "synthetic text"}],
            "message id": [{"type": "message", "role": "user", "content": "synthetic text", "id": "keep this ID"}],
            "message status": [{"type": "message", "role": "user", "content": "synthetic text", "status": "incomplete"}],
            "additional metadata": [{"type": "message", "role": "user", "content": "synthetic text", "extra": {"marker": "synthetic"}}],
            "prefix remains rejected": [{"type": "message", "role": "user", "content": "synthetic text", "prefix": False}],
        }
        for name, input_messages in cases.items():
            with self.subTest(case=name):
                request = {
                    "model": "deepseek-chat",
                    "input": input_messages,
                    "stream": False,
                    "tools": [{"type": "web_search_preview"}],
                }
                reference = _run(ORACLE, request, scenario="anthropic-buffered")
                actual = _run(MODEX, request, scenario="anthropic-buffered")
                self.assertEqual(actual["state"]["leftovers"], [])
                if name in ("typed unknown role", "prefix remains rejected"):
                    self.assertEqual((reference["exit_code"], reference["status"]), (1, 502))
                    self.assertEqual(reference["upstream"], [])
                    self.assertEqual((actual["exit_code"], actual["status"]), (1, 502))
                    self.assertEqual(actual["upstream"], [])
                    self.assertEqual(reference["response_body"], actual["response_body"])
                else:
                    self.assertEqual((reference["exit_code"], reference["status"]), (0, 200))
                    self.assertEqual(len(reference["upstream"]), 1)
                    self.assertEqual((actual["exit_code"], actual["status"]), (0, 200))
                    self.assertEqual(len(actual["upstream"]), 1)
                    self.assertEqual(actual["upstream_body"], reference["upstream_body"])
                    if name.startswith("untyped "):
                        self.assertEqual(reference["upstream_body"]["messages"][0]["role"], "user")
                self.assertEqual(reference["state"]["leftovers"], [])

    def test_mixed_rich_content_fails_closed(self):
        request = {
            "model": "deepseek-chat",
            "input": [{
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "synthetic text"},
                    {"type": "input_image", "image_url": "https://example.test/image.png"},
                ],
            }],
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
        }
        reference = _run(ORACLE, request, scenario="anthropic-buffered")
        actual = _run(MODEX, request, scenario="anthropic-buffered")
        self.assertEqual((reference["exit_code"], reference["status"]), (1, 502))
        self.assertEqual((actual["exit_code"], actual["status"]), (1, 502))
        self.assertEqual(reference["upstream"], [])
        self.assertEqual(actual["upstream"], [])
        self.assertEqual(actual["response_body"], reference["response_body"])
        self.assertEqual(reference["state"]["leftovers"], [])
        self.assertEqual(actual["state"]["leftovers"], [])

    def test_message_text_content_shapes_match_release(self):
        cases = {
            "annotated": ([{"type": "input_text", "text": "synthetic text", "annotations": {"marker": "synthetic"}}], 200),
            "multiple parts": ([{"type": "input_text", "text": "alpha"}, {"type": "output_text", "text": "beta"}], 200),
            "mixed scalar parts": (["alpha", 123, None, {"text": "beta"}], 200),
            "preserved spacing": ([{"type": "input_text", "text": " "}, {"type": "input_text", "text": "beta"}], 200),
            "object": ({"type": "input_text", "text": "alpha"}, 200),
            "empty array": ([], 400),
            "blank array": ([{"type": "input_text", "text": " \t"}], 400),
            "missing text": ([{"type": "input_text"}], 502),
            "image": ([{"type": "input_image", "image_url": "https://example.test/a"}], 502),
        }
        for name, (content, status) in cases.items():
            with self.subTest(case=name):
                request = {"model": "deepseek-chat", "input": [{"type": "message", "role": "user", "content": content}],
                           "stream": False, "tools": [{"type": "web_search_preview"}]}
                reference = _run(ORACLE, request, scenario="anthropic-buffered")
                actual = _run(MODEX, request, scenario="anthropic-buffered")
                self.assertEqual(reference["status"], status)
                self.assertEqual((actual["exit_code"], actual["status"]), (reference["exit_code"], status))
                self.assertEqual(len(actual["upstream"]), len(reference["upstream"]))
                if status == 200:
                    self.assertEqual(actual["upstream_body"], reference["upstream_body"])
                    expected = json.loads(reference["response_body"])
                    observed = json.loads(actual["response_body"])
                    expected.pop("created_at")
                    observed.pop("created_at")
                    self.assertEqual(observed, expected)
                else:
                    self.assertEqual(actual["response_body"], reference["response_body"])
                self.assertEqual(reference["state"]["leftovers"], [])
                self.assertEqual(actual["state"]["leftovers"], [])


if __name__ == "__main__":
    unittest.main()
