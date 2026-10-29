"""Compare Anthropic web-search sampling parameters with both pinned releases."""

import hashlib
import json
import unittest

from test_cli import MODEX, ORACLE as ORACLE_04392, ORACLE_SHA256 as ORACLE_04392_SHA256
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as ORACLE_01651_SHA256
from test_provider_tools_04392_characterization import _run


class AnthropicRequestSamplingTests(unittest.TestCase):
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

    def test_sampling_and_stop_parameters_match_both_releases(self):
        cases = (
            (
                "sampling with string stop",
                {"temperature": 0.25, "top_p": 0.8, "stop": "END"},
                {"temperature": 0.25, "top_p": 0.8, "stop_sequences": ["END"]},
            ),
            (
                "stop sequence alias",
                {"stop_sequences": ["END", "STOP"]},
                {"stop_sequences": ["END", "STOP"]},
            ),
            (
                "camel-case stop alias",
                {"stopSequences": "END"},
                {"stop_sequences": ["END"]},
            ),
            (
                "stop alias precedence",
                {"stop": "primary", "stop_sequences": ["secondary"], "stopSequences": ["tertiary"]},
                {"stop_sequences": ["primary"]},
            ),
        )
        binaries = (ORACLE_01651, ORACLE_04392, MODEX)
        for name, fields, expected_fields in cases:
            request = {
                "model": "deepseek-chat",
                "input": "synthetic query",
                "stream": False,
                "tools": [{"type": "web_search_preview"}],
                **fields,
            }
            with self.subTest(case=name):
                results = [
                    _run(binary, request, scenario="anthropic-buffered")
                    for binary in binaries
                ]
                reference = results[0]
                for result in results:
                    self.assertEqual((result["exit_code"], result["status"]), (0, 200))
                    self.assertEqual(len(result["upstream"]), 1)
                    self.assertEqual(result["upstream"][0]["path"], "/anthropic/v1/messages")
                    self.assertEqual(result["upstream_body"], reference["upstream_body"])
                    for key, value in expected_fields.items():
                        self.assertEqual(result["upstream_body"].get(key), value, key)
                    self.assertEqual(result["state"]["leftovers"], [])
                expected_response = json.loads(reference["response_body"])
                expected_response.pop("created_at")
                for result in results[1:]:
                    actual_response = json.loads(result["response_body"])
                    actual_response.pop("created_at")
                    self.assertEqual(actual_response, expected_response)

    def test_invalid_sampling_and_stop_values_still_fail_before_provider_post(self):
        cases = (
            {"temperature": "0.25"},
            {"top_p": None},
            {"stop": ["END", 7]},
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
                results = [
                    _run(binary, request, scenario="anthropic-buffered")
                    for binary in binaries
                ]
                expected = results[0]
                for result in results:
                    self.assertEqual((result["exit_code"], result["status"]), (1, 502))
                    self.assertEqual(result["upstream"], [])
                    self.assertEqual(result["response_body"], expected["response_body"])
                    self.assertEqual(result["state"]["leftovers"], [])


if __name__ == "__main__":
    unittest.main()
