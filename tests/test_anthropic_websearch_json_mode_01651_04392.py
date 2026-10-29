"""Compare the web-search JSON-mode fallback with both pinned releases."""

import hashlib
import json
import unittest
from unittest.mock import patch

import test_super_launch
from test_cli import MODEX, ORACLE as ORACLE_04392, ORACLE_SHA256 as ORACLE_04392_SHA256
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as ORACLE_01651_SHA256
from test_provider_tools_04392_characterization import _run


def _run_with_mode(binary, request, mode):
    original_run = test_super_launch.subprocess.run

    def run_with_mode(*args, **kwargs):
        environment = dict(kwargs["env"])
        environment["PRODEX_DEEPSEEK_WEB_SEARCH_MODE"] = mode
        kwargs["env"] = environment
        return original_run(*args, **kwargs)

    with patch.object(test_super_launch.subprocess, "run", side_effect=run_with_mode):
        return _run(binary, request, scenario="buffered")


class AnthropicWebSearchJsonModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for oracle, expected in (
            (ORACLE_01651, ORACLE_01651_SHA256),
            (ORACLE_04392, ORACLE_04392_SHA256),
        ):
            if not oracle.is_file():
                raise AssertionError(f"Pinned Prodex oracle is missing: {oracle}")
            if hashlib.sha256(oracle.read_bytes()).hexdigest() != expected:
                raise AssertionError(f"Prodex oracle checksum mismatch: {oracle}")
        if not MODEX.is_file():
            raise AssertionError(f"Modex binary has not been built: {MODEX}")

    def test_json_formats_fall_back_to_chat_in_auto_mode(self):
        schema = {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
            "additionalProperties": False,
        }
        cases = (
            {"response_format": {"type": "json_object"}},
            {"text": {"format": {"type": "json_object"}}},
            {"response_format": {"type": "json_schema", "name": "answer", "schema": schema}},
            {"text": {"format": {"type": "json_schema", "name": "answer", "schema": schema}}},
        )
        binaries = (ORACLE_01651, ORACLE_04392, MODEX)
        for fields in cases:
            request = {
                "model": "deepseek-chat",
                "input": "synthetic query",
                "stream": False,
                "tools": [{"type": "web_search_preview"}],
                **fields,
            }
            with self.subTest(fields=fields):
                results = [_run(binary, request, scenario="buffered") for binary in binaries]
                reference = results[0]
                expected_response = json.loads(reference["response_body"])
                expected_response.pop("created_at")
                for result in results:
                    self.assertEqual((result["exit_code"], result["status"]), (0, 200))
                    self.assertEqual(len(result["upstream"]), 1)
                    self.assertEqual(result["upstream"][0]["path"], "/v1/chat/completions")
                    self.assertEqual(result["upstream_body"], reference["upstream_body"])
                    self.assertEqual(result["upstream_body"]["response_format"]["type"], "json_object")
                    self.assertEqual(
                        result["upstream_body"]["messages"][0]["content"],
                        "Respond with valid JSON only.",
                    )
                    self.assertNotIn("web_search_options", result["upstream_body"])
                    self.assertEqual(result["state"]["leftovers"], [])
                    response = json.loads(result["response_body"])
                    response.pop("created_at")
                    self.assertEqual(response, expected_response)

    def test_json_format_is_rejected_in_explicit_anthropic_mode(self):
        request = {
            "model": "deepseek-chat",
            "input": "synthetic query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
            "response_format": {"type": "json_object"},
        }
        results = [
            _run_with_mode(binary, request, "anthropic")
            for binary in (ORACLE_01651, ORACLE_04392, MODEX)
        ]
        expected = results[0]
        for result in results:
            self.assertEqual((result["exit_code"], result["status"]), (1, 400))
            self.assertEqual(result["upstream"], [])
            self.assertEqual(result["response_body"], expected["response_body"])
            self.assertEqual(result["state"]["leftovers"], [])


if __name__ == "__main__":
    unittest.main()
