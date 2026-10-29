"""Anthropic Messages request limits against both pinned Prodex releases."""

import hashlib
import json
import unittest

from test_cli import MODEX, ORACLE as ORACLE_04392, ORACLE_SHA256 as ORACLE_04392_SHA256
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as ORACLE_01651_SHA256
from test_provider_tools_04392_characterization import _run


class AnthropicRequestMaxOutputTokens01651Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for oracle, expected in (
            (ORACLE_01651, ORACLE_01651_SHA256),
            (ORACLE_04392, ORACLE_04392_SHA256),
        ):
            if not oracle.is_file():
                raise AssertionError(f"Pinned Prodex oracle is missing: {oracle}")
            if hashlib.sha256(oracle.read_bytes()).hexdigest() != expected:
                raise AssertionError(f"Prodex oracle does not match pinned release: {oracle}")
        if not MODEX.is_file():
            raise AssertionError(f"Modex binary has not been built: {MODEX}")

    def test_valid_anthropic_limits_match_release_translation(self):
        cases = (
            ("default", {}, 4096),
            ("max_output_tokens", {"max_output_tokens": 128}, 128),
            ("max_tokens", {"max_tokens": 64}, 64),
            ("max_completion_tokens", {"max_completion_tokens": 32}, 32),
            ("max_tokens_precedence", {"max_output_tokens": 128, "max_tokens": 64}, 64),
            ("max_completion_precedence", {"max_output_tokens": 128, "max_completion_tokens": 32}, 32),
        )
        binaries = (ORACLE_01651, ORACLE_04392, MODEX)
        for name, fields, expected_tokens in cases:
            request = {
                "model": "deepseek-chat",
                "input": "synthetic prompt",
                "stream": False,
                "tools": [{"type": "web_search_preview"}],
                **fields,
            }
            with self.subTest(case=name):
                results = [
                    _run(binary, request, scenario="anthropic-buffered")
                    for binary in binaries
                ]
                expected = results[0]
                for result in results:
                    self.assertEqual((result["exit_code"], result["status"]), (0, 200))
                    self.assertEqual(len(result["upstream"]), 1)
                    self.assertEqual(result["upstream"][0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(result["upstream"][0]["body"], expected["upstream"][0]["body"])
                    self.assertEqual(result["upstream_body"]["max_tokens"], expected_tokens)
                    self.assertEqual(result["state"]["leftovers"], [])
                reference = json.loads(expected["response_body"])
                actual = json.loads(results[2]["response_body"])
                for key in ("id", "model", "metadata", "output", "usage"):
                    self.assertEqual(actual.get(key), reference.get(key), key)

    def test_invalid_anthropic_limits_fail_before_provider_post(self):
        invalid_values = (0, -1, 1.5, "128", None, 18446744073709551616)
        binaries = (ORACLE_01651, ORACLE_04392, MODEX)
        for value in invalid_values:
            request = {
                "model": "deepseek-chat",
                "input": "synthetic prompt",
                "stream": False,
                "max_output_tokens": value,
                "tools": [{"type": "web_search_preview"}],
            }
            with self.subTest(value=value):
                for binary in binaries:
                    result = _run(binary, request, scenario="anthropic-buffered")
                    self.assertEqual((result["exit_code"], result["status"]), (1, 502))
                    self.assertEqual(result["upstream"], [])
                    self.assertEqual(result["state"]["leftovers"], [])

        for key, value in (("max_tokens", 0), ("max_completion_tokens", "32")):
            request = {
                "model": "deepseek-chat",
                "input": "synthetic prompt",
                "stream": False,
                "max_output_tokens": 128,
                key: value,
                "tools": [{"type": "web_search_preview"}],
            }
            with self.subTest(key=key, value=value):
                for binary in binaries:
                    result = _run(binary, request, scenario="anthropic-buffered")
                    self.assertEqual((result["exit_code"], result["status"]), (1, 502))
                    self.assertEqual(result["upstream"], [])
                    self.assertEqual(result["state"]["leftovers"], [])

    def test_non_anthropic_limit_translation_remains_unchanged(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic prompt",
            "stream": False,
            "max_output_tokens": 128,
        }
        results = [_run(binary, request, scenario="buffered") for binary in (
            ORACLE_01651, ORACLE_04392, MODEX,
        )]
        expected = results[0]
        for result in results:
            self.assertEqual((result["exit_code"], result["status"]), (0, 200))
            self.assertEqual(len(result["upstream"]), 1)
            self.assertEqual(result["upstream"][0]["path"], "/v1/chat/completions")
            self.assertEqual(result["upstream"][0]["body"], expected["upstream"][0]["body"])
            self.assertEqual(result["upstream_body"]["max_tokens"], 128)
