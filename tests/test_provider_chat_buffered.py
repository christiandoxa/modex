"""Check the native buffered mapper against frozen Prodex response captures."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/provider-buffered/cases.json"
REQUEST_FIXTURE = ROOT / "tests/fixtures/provider-requests/cases.json"
DRIVER = ROOT / "build/tests/provider_chat_buffered_driver"
ORACLE_SHA256 = "2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a"
BASELINE_COMMIT = "433aad44bb249d5c25a231a6b06c2fa522a39a1f"


class ProviderChatBufferedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if cls.catalog["oracle_sha256"] != ORACLE_SHA256:
            raise AssertionError("fixture does not identify the pinned Prodex oracle")
        if cls.catalog["baseline_commit"] != BASELINE_COMMIT:
            raise AssertionError("fixture does not identify the frozen baseline commit")
        cls.cases = {case["name"]: case for case in cls.catalog["cases"]}
        if len(cls.cases) != len(cls.catalog["cases"]):
            raise AssertionError("buffered case names must be unique")
        request_catalog = json.loads(REQUEST_FIXTURE.read_text(encoding="utf-8"))
        if request_catalog["oracle_sha256"] != ORACLE_SHA256:
            raise AssertionError("request fixture does not identify the pinned Prodex oracle")
        if request_catalog["baseline_commit"] != BASELINE_COMMIT:
            raise AssertionError("request fixture does not identify the frozen baseline commit")
        cls.request_cases = {
            case["name"]: case
            for case in request_catalog["cases"]
        }

    def test_captures_are_checksum_verified_oracle_observations(self):
        self.assertEqual(self.catalog["oracle_version"], "0.439.0")
        self.assertEqual(self.catalog["capture_harness"], "tests/capture_provider_buffered.py")
        self.assertIn("synthetic loopback", self.catalog["scope"])
        self.assertTrue(self.cases)
        for case in self.cases.values():
            with self.subTest(case=case["name"]):
                upstream_request = case["upstream_request"]
                upstream_response = case["upstream_response"]
                oracle_response = case["oracle_response"]
                self.assertEqual(upstream_request["method"], "POST")
                self.assertEqual(upstream_request["path"], "/v1/chat/completions")
                self.assertTrue(upstream_request["destination"].startswith("127.0.0.1:"))
                self.assertEqual(upstream_request["authorization"], "Bearer synthetic-provider-key")
                self.assertEqual(
                    hashlib.sha256(upstream_request["body"].encode()).hexdigest(),
                    upstream_request["body_sha256"],
                )
                upstream_bytes = upstream_response["body"].encode()
                self.assertEqual(upstream_response["content_type"], "application/json")
                self.assertEqual(hashlib.sha256(upstream_bytes).hexdigest(), upstream_response["sha256"])
                oracle_bytes = oracle_response["body"].encode()
                self.assertEqual(hashlib.sha256(oracle_bytes).hexdigest(), oracle_response["sha256"])
                self.assertEqual(oracle_response["status"], upstream_response["status"])
                self.assertEqual(oracle_response["content_type"], "application/json; charset=utf-8")
                self.assertEqual(case["oracle_super_returncode"], 1)
                self.assertIn("Codex hook-trust preflight initialize failed", case["oracle_stderr"])

    def run_native(self, body, metadata):
        if not DRIVER.is_file():
            raise AssertionError(f"native buffered driver has not been built: {DRIVER}")
        header = {
            "created_at": 1,
            "response_id": "resp_buffered_fallback",
            "metadata": metadata,
        }
        with tempfile.TemporaryDirectory(prefix="modex-buffered-native-") as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir(mode=0o700)
            environment = {
                "HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
                "NO_COLOR": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                "TMPDIR": str(root),
            }
            transcript = (
                json.dumps(header, ensure_ascii=False, separators=(",", ":"))
                + "\n" + body + "\n"
            )
            result = subprocess.run(
                [str(DRIVER)], input=transcript.encode("utf-8"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
                check=False, cwd=root, env=environment,
            )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        lines = result.stdout.decode("utf-8").splitlines()
        self.assertEqual(len(lines), 1, result.stdout.decode("utf-8", "replace"))
        return json.loads(lines[0])

    def test_native_buffered_results_match_frozen_oracle_captures(self):
        for case in self.cases.values():
            with self.subTest(case=case["name"]):
                expected = json.loads(case["oracle_response"]["body"])
                actual = self.run_native(
                    case["upstream_response"]["body"], case["request"].get("metadata"),
                )
                if case["name"].startswith("missing_tool_call_id_sample_"):
                    for response in (actual, expected):
                        call_id = response["output"][0]["call_id"]
                        self.assertTrue(call_id.startswith("call_deepseek_"))
                        identifier = call_id.removeprefix("call_deepseek_")
                        parsed = uuid.UUID(identifier)
                        self.assertEqual(parsed.version, 7)
                        self.assertEqual(str(parsed), identifier)
                        response["output"][0]["call_id"] = "<generated-call-id>"
                self.assertEqual(actual, expected)

    def test_buffered_edge_observations_and_exact_tool_errors(self):
        blank = json.loads(self.cases["blank_provider_metadata"]["oracle_response"]["body"])
        self.assertEqual(blank["metadata"], {"trace": "synthetic"})

        self.assertEqual(
            json.loads(self.cases["standalone_name_trim"]["oracle_response"]["body"])["output"][0]["name"],
            "lookup",
        )
        spaced = json.loads(self.cases["spaced_namespace_trim"]["oracle_response"]["body"])["output"][0]
        self.assertEqual((spaced["namespace"], spaced["name"]), ("functions", "lookup"))
        command_only = json.loads(self.cases["shell_command_only"]["oracle_response"]["body"])
        self.assertEqual(command_only["output"][0]["arguments"], "{\"command\":\"cargo test\"}")
        cmd_active = json.loads(self.cases["shell_cmd_rewrite"]["oracle_response"]["body"])
        self.assertEqual(cmd_active["output"][0]["arguments"], "{\"cmd\":\"rtk cargo test\"}")
        wrong_type = json.loads(self.cases["wrong_type_arguments"]["oracle_response"]["body"])
        self.assertEqual(wrong_type["output"][0]["arguments"], "{}")
        patch = json.loads(self.cases["apply_patch_raw"]["oracle_response"]["body"])
        self.assertEqual(patch["output"][0]["input"], "{\"patch\":\"*** Begin Patch\\n*** End Patch\"}")

        expected_errors = {
            "malformed_tool_arguments": "DeepSeek returned malformed JSON arguments for tool call `lookup`: key must be a string at line 1 column 2",
            "malformed_nested_trailing_comma": "DeepSeek returned malformed JSON arguments for tool call `lookup`: trailing comma at line 1 column 9",
            "malformed_nested_eof": "DeepSeek returned malformed JSON arguments for tool call `lookup`: EOF while parsing a value at line 1 column 5",
            "empty_tool_search_whitespace": "DeepSeek returned malformed JSON arguments for tool call `tool_search`: EOF while parsing a value at line 1 column 3",
            "tool_search_invalid_literal": "DeepSeek Mojo returned invalid response tool-call JSON: expected ident at line 1 column 90",
        }
        for name, message in expected_errors.items():
            with self.subTest(error_case=name):
                response = json.loads(self.cases[name]["oracle_response"]["body"])
                self.assertEqual(response["status"], "failed")
                self.assertEqual(response["error"]["message"], message)

        unicode_malformed = json.loads(
            self.cases["malformed_nested_unicode"]["oracle_response"]["body"]
        )
        self.assertNotEqual(unicode_malformed.get("status"), "failed")
        self.assertEqual(
            unicode_malformed["output"][0]["arguments"],
            '{\n"é": 1,\n"x":truX}',
        )
        scalar = json.loads(self.cases["structural_invalid_literal"]["oracle_response"]["body"])
        self.assertNotEqual(scalar.get("status"), "failed")
        self.assertEqual(scalar["output"][0]["arguments"], "truX")

    def test_missing_oracle_tool_call_ids_are_unique_uuid7(self):
        ids = []
        for name in ("missing_tool_call_id_sample_a", "missing_tool_call_id_sample_b"):
            response = json.loads(self.cases[name]["oracle_response"]["body"])
            call_id = response["output"][0]["call_id"]
            self.assertTrue(call_id.startswith("call_deepseek_"))
            identifier = call_id.removeprefix("call_deepseek_")
            parsed = uuid.UUID(identifier)
            self.assertEqual(parsed.version, 7)
            self.assertEqual(str(parsed), identifier)
            ids.append(identifier)
        self.assertEqual(len(set(ids)), 2)

    def test_oracle_maps_buffered_text_tool_usage_metadata_and_tool_errors(self):
        rich = json.loads(self.cases["text_tool_usage_metadata"]["oracle_response"]["body"])
        self.assertEqual((rich["id"], rich["created_at"], rich["model"]),
                         ("chatcmpl_buffered_1", 1700000000, "deepseek-chat"))
        self.assertEqual(rich["output"][0]["content"][0]["text"], "こんにちは 🌋")
        self.assertEqual(rich["output"][1], {
            "type": "function_call", "call_id": "call_東京", "namespace": "functions",
            "name": "検索", "arguments": "{\"query\":\"café 🍜\"}",
        })
        self.assertEqual(rich["usage"]["input_tokens_details"]["cached_tokens"], 5)
        self.assertEqual(rich["usage"]["output_tokens_details"]["reasoning_tokens"], 2)
        self.assertEqual(rich["metadata"]["trace"], "synthetic")
        self.assertEqual(rich["metadata"]["deepseek"]["reasoning_content"], "考えています")

        failed = json.loads(self.cases["malformed_tool_arguments"]["oracle_response"]["body"])
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error"]["code"], "invalid_tool_call_arguments")
        self.assertIn("malformed JSON arguments for tool call `lookup`", failed["error"]["message"])
        self.assertEqual(failed["output"][0]["content"][0]["text"], "before error")

    def test_existing_oracle_text_and_request_metadata_cases_match_native(self):
        upstream = json.dumps({
            "id": "chatcmpl-synthetic",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "deepseek-chat",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "synthetic response"},
                "finish_reason": "stop",
            }],
        }, separators=(",", ":"))
        for name in ("defaults", "metadata"):
            with self.subTest(case=name):
                case = self.request_cases[name]
                self.assertEqual(
                    self.run_native(upstream, case["expected_response_metadata"]),
                    json.loads(case["local_response"]["body"]),
                )

    def test_provider_request_fixture_has_oracle_buffered_text_and_metadata_cases(self):
        for name in ("defaults", "metadata"):
            with self.subTest(case=name):
                case = self.request_cases[name]
                self.assertEqual(case["local_response"]["status"], 200)
                self.assertEqual(
                    hashlib.sha256(case["local_response"]["body"].encode()).hexdigest(),
                    case["local_response"]["sha256"],
                )
                translated = json.loads(case["local_response"]["body"])
                self.assertEqual(translated["object"], "response")
                self.assertEqual(translated["output"][0]["content"][0]["text"], "synthetic response")
        self.assertEqual(
            json.loads(self.request_cases["metadata"]["local_response"]["body"])["metadata"]["trace"],
            "synthetic",
        )


if __name__ == "__main__":
    unittest.main()
