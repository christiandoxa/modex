"""Exact native-vs-frozen-Prodex stream comparisons using committed captures."""

import base64
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from capture_provider_stream import compare_sse_bytes
from session_oracle import sandbox_command


FIXTURE = ROOT / "tests/fixtures/provider-stream/cases.json"
DRIVER = ROOT / "build/tests/provider_chat_stream_driver"
ORACLE_SHA256 = "2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a"
class ProviderChatStreamOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if not DRIVER.is_file():
            raise RuntimeError(f"native driver is not built: {DRIVER}")

    def test_frozen_oracle_identity(self):
        self.assertEqual(self.catalog["oracle_sha256"], ORACLE_SHA256)
        self.assertEqual(self.catalog["baseline_commit"], "433aad44bb249d5c25a231a6b06c2fa522a39a1f")

    def test_frozen_oracle_transport_failures_remain_visible(self):
        for case in self.catalog["cases"]:
            if "oracle_capture_error" in case:
                with self.subTest(case=case["name"]):
                    self.assertNotIn("expected_base64", case)
                    self.assertIn("Codex hook-trust preflight initialize failed", case["oracle_stderr"])

    def test_missing_call_id_is_proven_uuid7_nondeterminism(self):
        case = next(case for case in self.catalog["cases"] if case["name"] == "missing_call_id_multichunk")
        samples = case["observed_uuid7_samples"]
        self.assertEqual(len(samples), 2)
        self.assertEqual(len(set(samples)), 2)
        self.assertTrue(all(uuid.UUID(sample).version == 7 for sample in samples))
        expected = base64.b64decode(case["expected_base64"], validate=True)
        ids = re.findall(rb'"call_id":"call_deepseek_([^"\\]+)"', expected)
        self.assertTrue(ids)
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(uuid.UUID(ids[0].decode()).version, 7)
        self.assertIn(ids[0].decode(), samples)

    def test_oracle_preserves_tool_search_json_argument_shapes(self):
        cases = {case["name"]: case for case in self.catalog["cases"]}
        for name, arguments in [
            ("tool_search_scalar_arguments", "needle"),
            ("tool_search_array_arguments", ["one", "two"]),
        ]:
            with self.subTest(case=name):
                expected = base64.b64decode(cases[name]["expected_base64"], validate=True)
                payloads = [
                    json.loads(line[6:])
                    for line in expected.decode().splitlines()
                    if line.startswith("data: {")
                ]
                items = [
                    payload["item"] for payload in payloads
                    if isinstance(payload.get("item"), dict)
                    and payload["item"].get("type") == "tool_search_call"
                ]
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["arguments"], arguments)

    def test_uuid7_comparison_only_ignores_one_valid_fallback_value(self):
        baseline = b'event: x\r\ndata: {"call_id":"call_deepseek_01a172f8-0826-767d-96bc-56eb7d76be87","ok":true}\r\n\r\n'
        other = b'event: x\r\ndata: {"call_id":"call_deepseek_01a172f8-9d2e-755c-839b-e2d846c92136","ok":true}\r\n\r\n'
        self.assertEqual(compare_sse_bytes(baseline, other, True)["comparison"], "uuid7_normalized")
        self.assertEqual(compare_sse_bytes(baseline, other + b"x", True)["comparison"], "different")
        deterministic = other.replace(b"01a172f8-9d2e-755c-839b-e2d846c92136", b"12345678-1234-4234-8234-123456789abc")
        self.assertEqual(compare_sse_bytes(baseline, deterministic, True)["comparison"], "different")
        uppercase = other.replace(b"01a172f8-9d2e-755c-839b-e2d846c92136", b"01A172F8-9D2E-755C-839B-E2D846C92136")
        self.assertEqual(compare_sse_bytes(baseline, uppercase, True)["comparison"], "different")
        inconsistent = baseline.replace(b"\r\n\r\n", b"\r\ndata: {\"call_id\":\"call_deepseek_01a172f8-9d2e-755c-839b-e2d846c92136\"}\r\n\r\n")
        self.assertEqual(compare_sse_bytes(baseline, inconsistent, True)["comparison"], "different")

    def test_all_captured_streams_match_byte_for_byte(self):
        for case in self.catalog["cases"]:
            with self.subTest(case=case["name"]):
                if "oracle_capture_error" in case:
                    continue
                expected = base64.b64decode(case["expected_base64"], validate=True)
                upstream = base64.b64decode(case["upstream_base64"], validate=True)
                self.assertEqual(hashlib.sha256(expected).hexdigest(), case["oracle_response_sha256"])
                request_id = case["header"]["request_id"]
                header = json.dumps({
                    "request_id": request_id,
                    "response_id": case["header"]["response_id"],
                    "created_at": case["header"]["created_at"],
                    "metadata": case["header"].get("metadata"),
                }, separators=(",", ":"))
                transcript = f"{header}\n{upstream.hex()}\n".encode()
                result = subprocess.run(
                    [str(DRIVER)], input=transcript, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, timeout=10, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                actual = result.stdout
                comparison = compare_sse_bytes(
                    expected, actual, "observed_uuid7_samples" in case,
                )
                self.assertTrue(comparison["matches_oracle_bytes"], json.dumps(comparison))
                if comparison["comparison"] == "uuid7_normalized":
                    self.assertFalse(comparison["raw_matches_oracle_bytes"])

    def test_chunk_replay_is_stable_bytewise_and_at_seeded_boundaries(self):
        cases = {case["name"]: case for case in self.catalog["cases"]}
        for name in ["missing_call_id_multichunk", "apply_patch_multiline_path_content", "fragmented_json_data_lines"]:
            case = cases[name]
            upstream = base64.b64decode(case["upstream_base64"], validate=True)
            header = json.dumps({
                "request_id": case["header"]["request_id"],
                "response_id": case["header"]["response_id"],
                "created_at": case["header"]["created_at"],
                "metadata": case["header"].get("metadata"),
            }, separators=(",", ":"))
            chunks = [[upstream]]
            chunks.append([upstream[i:i + 1] for i in range(len(upstream))])
            rng = random.Random(0x5EED)
            seeded = []
            offset = 0
            while offset < len(upstream):
                size = rng.randint(1, 53)
                seeded.append(upstream[offset:offset + size])
                offset += size
            chunks.append(seeded)
            outputs = []
            for split in chunks:
                transcript = (header + "\n" + "".join(chunk.hex() + "\n" for chunk in split)).encode()
                result = subprocess.run(
                    [str(DRIVER)], input=transcript, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, timeout=10, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                outputs.append(result.stdout)
            for output in outputs[1:]:
                comparison = compare_sse_bytes(outputs[0], output, allow_uuid7_nondeterminism=True)
                self.assertTrue(comparison["matches_oracle_bytes"], json.dumps(comparison))

    def test_clean_runtime_uuid7_and_malformed_utf8(self):
        cases = {case["name"]: case for case in self.catalog["cases"]}
        with tempfile.TemporaryDirectory(prefix="provider-chat-stream-sandbox-") as directory:
            root = Path(directory)
            (root / "home").mkdir(mode=0o700)
            (root / "workspace").mkdir(mode=0o700)

            def run(case):
                header = json.dumps(case["header"], separators=(",", ":"))
                wire = base64.b64decode(case["upstream_base64"], validate=True)
                transcript = (header + "\n" + wire.hex() + "\n").encode()
                return subprocess.run(
                    sandbox_command(DRIVER, root, []), input=transcript,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False,
                )

            missing_id = run(cases["missing_call_id_multichunk"])
            self.assertEqual(missing_id.returncode, 0, missing_id.stderr.decode("utf-8", "replace"))
            call_ids = re.findall(rb'"call_id":"call_deepseek_([^"\\]+)"', missing_id.stdout)
            self.assertTrue(call_ids)
            self.assertEqual(len(set(call_ids)), 1)
            self.assertEqual(uuid.UUID(call_ids[0].decode()).version, 7)

            invalid_utf8 = run(cases["invalid_utf8_after_seed"])
            self.assertEqual(invalid_utf8.returncode, 0, invalid_utf8.stderr.decode("utf-8", "replace"))
            self.assertIn(b'"code":"provider_stream_error"', invalid_utf8.stdout)
            self.assertIn(b'"message":"stream did not contain valid UTF-8"', invalid_utf8.stdout)


if __name__ == "__main__":
    unittest.main()
