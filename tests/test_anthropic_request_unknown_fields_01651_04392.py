"""Compare ignored Anthropic request fields with both pinned releases."""

import hashlib
import json
import os
import unittest
from pathlib import Path

from test_cli import MODEX
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as ORACLE_01651_SHA256
from test_anthropic_mixed_tools_01651 import _run_mode
from test_provider_tools_04392_characterization import _run


ORACLE_04392 = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    Path.home() / ".cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_04392_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"


class AnthropicUnknownRequestFieldsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for oracle, expected in (
            (ORACLE_01651, ORACLE_01651_SHA256),
            (ORACLE_04392, ORACLE_04392_SHA256),
        ):
            if not oracle.is_file() or hashlib.sha256(oracle.read_bytes()).hexdigest() != expected:
                raise AssertionError(f"Pinned Prodex oracle does not match: {oracle}")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def test_unknown_responses_and_search_fields_are_ignored_and_not_forwarded(self):
        base = {
            "model": "deepseek-chat",
            "input": "synthetic query",
            "stream": False,
        }
        cases = (
            (
                "unknown Responses field",
                {**base, "future_extension": {"private_marker": "synthetic"},
                 "tools": [{"type": "web_search_preview"}]},
            ),
            (
                "unknown web-search field",
                {**base, "tools": [{"type": "web_search_preview",
                                    "future_extension": {"private_marker": "synthetic"}}]},
            ),
        )
        binaries = (ORACLE_01651, ORACLE_04392, MODEX)
        for name, request in cases:
            for mode in ("auto", "anthropic"):
                with self.subTest(case=name, mode=mode):
                    results = [
                        _run(binary, request, scenario="anthropic-buffered", mode_override=mode)
                        for binary in binaries
                    ]
                    reference = results[0]
                    for result in results:
                        self.assertEqual((result["exit_code"], result["status"]), (0, 200))
                        self.assertEqual(len(result["upstream"]), 1)
                        self.assertEqual(result["upstream"][0]["path"], "/anthropic/v1/messages")
                        self.assertEqual(result["upstream_body"], reference["upstream_body"])
                        self.assertNotIn("future_extension", json.dumps(result["upstream_body"]))
                        self.assertNotIn("private_marker", json.dumps(result["upstream_body"]))
                        self.assertEqual(result["state"]["leftovers"], [])
                    expected_response = json.loads(reference["response_body"])
                    expected_response.pop("created_at")
                    for result in results[1:]:
                        actual_response = json.loads(result["response_body"])
                        actual_response.pop("created_at")
                        self.assertEqual(actual_response, expected_response)

    def test_unknown_fields_do_not_bypass_known_validation_or_size_limit(self):
        base = {
            "model": "deepseek-chat",
            "input": "synthetic query",
            "stream": False,
            "tools": [{"type": "web_search_preview"}],
            "future_extension": "synthetic",
        }
        binaries = (ORACLE_01651, ORACLE_04392, MODEX)
        for name, fields in (
            ("malformed temperature", {"temperature": "warm"}),
            ("unsupported service_tier", {"service_tier": "priority"}),
        ):
            for mode in ("auto", "anthropic", "openai_chat"):
                with self.subTest(case=name, mode=mode):
                    results = [
                        _run(binary, {**base, **fields}, scenario="anthropic-buffered", mode_override=mode)
                        for binary in binaries
                    ]
                    reference = results[0]
                    for result in results:
                        self.assertEqual((result["exit_code"], result["status"]), (1, 502))
                        self.assertEqual(result["upstream"], [])
                        self.assertEqual(result["response_body"], reference["response_body"])
                        self.assertEqual(result["state"]["leftovers"], [])

        oversized = {**base, "future_extension": "x" * (4 * 1024 * 1024)}
        results = [_run(binary, oversized, scenario="anthropic-buffered") for binary in binaries]
        reference = results[0]
        for result in results:
            self.assertEqual((result["exit_code"], result["status"]), (1, 502))
            self.assertEqual(result["upstream"], [])
            self.assertEqual(result["response_body"], reference["response_body"])
            self.assertEqual(result["state"]["leftovers"], [])

    def test_duplicate_extension_and_known_fields_keep_release_behavior(self):
        requests = (
            (
                "duplicate unknown field",
                '{"model":"deepseek-chat","input":"synthetic query","stream":false,'
                '"tools":[{"type":"web_search_preview"}],'
                '"future_extension":{"private_marker":"first"},'
                '"future_extension":{"private_marker":"last"}}',
                200,
                None,
            ),
            (
                "last valid known value",
                '{"model":"deepseek-chat","input":"synthetic query","stream":false,'
                '"tools":[{"type":"web_search_preview"}],'
                '"temperature":"warm","temperature":0.25}',
                200,
                0.25,
            ),
            (
                "last malformed known value",
                '{"model":"deepseek-chat","input":"synthetic query","stream":false,'
                '"tools":[{"type":"web_search_preview"}],'
                '"temperature":0.25,"temperature":"warm"}',
                502,
                None,
            ),
        )
        binaries = (ORACLE_01651, ORACLE_04392, MODEX)
        for name, raw_request, expected_status, expected_temperature in requests:
            with self.subTest(case=name):
                results = [
                    _run_mode(binary, {}, "anthropic-buffered", "auto", raw_request=raw_request)
                    for binary in binaries
                ]
                reference = results[0]
                for result, response, upstream, state in results:
                    self.assertEqual((result.returncode, response["status"]), (
                        0 if expected_status == 200 else 1, expected_status,
                    ))
                    self.assertEqual(state["leftovers"], [])
                    if expected_status == 502:
                        self.assertEqual(upstream, [])
                        self.assertEqual(response["body"], reference[1]["body"])
                        continue
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["path"], "/anthropic/v1/messages")
                    body = json.loads(bytes.fromhex(upstream[0]["body"]))
                    reference_body = json.loads(bytes.fromhex(reference[2][0]["body"]))
                    self.assertEqual(body, reference_body)
                    self.assertNotIn("future_extension", body)
                    self.assertNotIn("private_marker", body)
                    if expected_temperature:
                        self.assertEqual(body["temperature"], expected_temperature)


if __name__ == "__main__":
    unittest.main()
