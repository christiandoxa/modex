"""Frozen-source regressions for native chat choice and error decoding."""

import json
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "build/tests/provider_chat_chunk_driver"
METADATA = {"finish_reason": None, "logprobs": None}
DELTA = {"annotations": [], "content": None, "reasoning_content": None,
         "refusal": None, "tool_calls": []}
DEFAULT_ERROR = {"code": "provider_stream_error", "message": "Provider stream returned an embedded error"}


def project(sources):
    result = subprocess.run([str(DRIVER)], input=("\n".join(sources) + "\n").encode(),
                            capture_output=True, timeout=10, check=False)
    if result.returncode or result.stderr:
        raise AssertionError((result.returncode, result.stderr))
    values = [json.loads(line) for line in result.stdout.splitlines()]
    if len(values) != len(sources):
        raise AssertionError(f"expected {len(sources)} projections, got {len(values)}")
    return values


class ProviderChatChunkTests(unittest.TestCase):
    def test_absent_and_wrong_type_choices(self):
        sources = ["null", "[]", "{}", '{"choices":null}', '{"choices":{}}', '{"choices":[]}']
        self.assertEqual(project(sources), [
            {"choice": None, "metadata": METADATA, "delta": DELTA, "error": None}
        ] * len(sources))

    def test_first_array_element_and_unknown_choice_fields(self):
        first = {"index": 9, "unknown": {"kept": True}, "delta": {"content": "first"}}
        source = json.dumps({"choices": [first, {"index": 0, "delta": {"content": "second"}}]})
        value, = project([source])
        self.assertEqual(value, {"choice": first, "metadata": METADATA,
                                 "delta": {**DELTA, "content": "first"}, "error": None})

    def test_typed_delta_defaults_and_empty_string_rules(self):
        choices = [
            {"delta": {"content": "", "reasoning_content": 7, "refusal": False,
                       "annotations": {}, "tool_calls": None}, "finish_reason": "", "logprobs": False},
            {"delta": {"content": " ", "reasoning_content": "reason", "refusal": "refusal",
                       "annotations": [None, {"unknown": 1}], "tool_calls": [2, {"unknown": True}]},
             "finish_reason": 3, "logprobs": None},
            {"delta": [], "message": {"content": "ignored"}},
        ]
        values = project([json.dumps({"choices": [choice]}) for choice in choices])
        self.assertEqual(values[0]["metadata"], {"finish_reason": "", "logprobs": False})
        self.assertEqual(values[0]["delta"], DELTA)
        self.assertEqual(values[1]["metadata"], METADATA)
        self.assertEqual(values[1]["delta"], choices[1]["delta"])
        self.assertEqual(values[2]["delta"], DELTA)

    def test_embedded_error_presence_and_fallback_precedence(self):
        sources = ['{}', '{"error":null}', '{"error":""}',
                   '{"error":{"type":null,"code":"ignored","message":null,"detail":"ignored"}}',
                   '{"error":{"type":"","message":""}}',
                   '{"error":{"code":429,"detail":"retry"}}', '{"error":[]}']
        self.assertEqual([value["error"] for value in project(sources)], [
            None, DEFAULT_ERROR, {**DEFAULT_ERROR, "message": ""}, DEFAULT_ERROR,
            {"code": "", "message": ""}, {"code": "429", "message": "retry"}, DEFAULT_ERROR,
        ])

    def test_numeric_error_code_boundaries_and_number_spellings(self):
        tokens = ["-9223372036854775808", "9223372036854775807", "-9223372036854775809",
                  "9223372036854775808", "18446744073709551615", "-0", "1.0", "1e0", "0"]
        values = project(['{"error":{"code":' + token + '}}' for token in tokens])
        codes = [tokens[0], tokens[1], *(["provider_stream_error"] * 6), "0"]
        self.assertEqual([value["error"] for value in values], [
            {**DEFAULT_ERROR, "code": code} for code in codes])

    def test_selected_nonobject_choices_and_malformed_json_fail_explicitly(self):
        for source in ('{"choices":[null]}', '{"choices":[3]}', '{"choices":[[]]}', '{"choices":'):
            with self.subTest(source=source):
                result = subprocess.run([str(DRIVER)], input=(source + "\n").encode(),
                                        capture_output=True, timeout=10, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertTrue(result.stderr)


if __name__ == "__main__":
    unittest.main()
