"""Compare the native request translator with pinned Prodex captures."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/provider-requests/cases.json"
DRIVER = Path(os.environ.get("MODEX_PROVIDER_REQUEST_DRIVER", ROOT / "build/tests/provider_request_driver"))
ORACLE_SHA256 = "2dec9565fd94eb59aeb83ae5e7cc4b772db130cbd45258d86a2104c8f4ba186a"


class ProviderRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(FIXTURE.read_text())
        if cls.catalog["oracle_sha256"] != ORACLE_SHA256:
            raise AssertionError("fixture does not identify the pinned Prodex oracle")
        if not DRIVER.is_file():
            raise AssertionError(f"native request driver has not been built: {DRIVER}")

    def run_native(self, wrapper, *, sandbox=False, expected_body=None):
        with tempfile.TemporaryDirectory(prefix="modex-provider-request-sandbox-") as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir(mode=0o700)
            (root / "workspace").mkdir(mode=0o700)
            environment = {
                "HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
                "NO_COLOR": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TMPDIR": str(root),
            }
            command = sandbox_command(DRIVER, root, []) if sandbox else [str(DRIVER)]
            result = subprocess.run(
                command, input=(json.dumps(wrapper, separators=(",", ":")) + "\n").encode(),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False,
                cwd=root, env=environment,
            )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        lines = result.stdout.decode("utf-8", "replace").splitlines()
        self.assertEqual(len(lines), 1, result.stdout.decode("utf-8", "replace"))
        if expected_body is not None:
            prefix = '{"ok":{"body":'
            self.assertTrue(lines[0].startswith(prefix), lines[0])
            _, end = json.JSONDecoder().raw_decode(lines[0], len(prefix))
            self.assertEqual(lines[0][len(prefix):end], expected_body)
        return json.loads(lines[0])

    def test_catalog_cases_are_observed_or_explicit_gaps(self):
        cases = self.catalog["cases"]
        names = [case["name"] for case in cases]
        self.assertTrue(cases)
        self.assertEqual(len(names), len(set(names)), "case names must be unique")
        for case in cases:
            with self.subTest(case=case["name"]):
                self.assertIn("expected_response_metadata", case)
                if "upstream_request" in case:
                    request = case["upstream_request"]
                    self.assertNotIn("capture_error", case)
                    self.assertIn(case.get("route_kind"), ("deepseek_chat", "other_provider_path"))
                    self.assertTrue(request["destination"].startswith("127.0.0.1:"))
                    self.assertIn(request["authorization"], (None, "Bearer synthetic-provider-key"))
                    self.assertEqual(hashlib.sha256(request["body"].encode()).hexdigest(), case["upstream_body_sha256"])
                    self.assertIn("local_response", case)
                    self.assertEqual(case["local_response"]["status"], 200 if case["route_kind"] == "deepseek_chat" else 502)
                    self.assertEqual(hashlib.sha256(case["local_response"]["body"].encode()).hexdigest(), case["local_response"]["sha256"])
                else:
                    self.assertNotIn("capture_error", case, "incomplete captures cannot pass as parity gaps")
                    self.assertTrue(case.get("oracle_observation"), "missing captures must remain visible gaps")
                    self.assertNotIn("route_kind", case)

    def test_captured_request_bodies(self):
        for case in self.catalog["cases"]:
            if case.get("route_kind") != "deepseek_chat":
                continue
            with self.subTest(case=case["name"]):
                observed = case["upstream_request"]
                body = observed["body"].encode()
                self.assertEqual(hashlib.sha256(body).hexdigest(), case["upstream_body_sha256"])
                wrapper = {
                    "request": case["request"], "history": case.get("history", []),
                    "strict_tools": case.get("strict_tools", False),
                    "web_search_mode": case.get("web_search_mode", "auto"),
                }
                translated = self.run_native(wrapper, expected_body=observed["body"])
                self.assertIn("ok", translated, translated)
                self.assertEqual(translated["ok"]["body"], json.loads(body))
                self.assertIsInstance(translated["ok"]["messages"], list)
                self.assertEqual(translated["ok"]["response_metadata"], case["expected_response_metadata"])

    def test_request_metadata_stays_separate_from_completion_metadata(self):
        cases = {case["name"]: case for case in self.catalog["cases"]}
        for name in ("json_schema", "text_format_json_schema", "metadata", "metadata_reserved_key"):
            with self.subTest(case=name):
                case = cases[name]
                self.assertEqual(case["expected_response_metadata"], self.run_native({"request": case["request"]})["ok"]["response_metadata"])
                response_metadata = json.loads(case["local_response"]["body"])["metadata"]
                self.assertEqual(response_metadata["deepseek"]["finish_reason"], "stop")
                for key, value in case["expected_response_metadata"].items():
                    if key != "deepseek":
                        self.assertEqual(response_metadata[key], value)
                expected_deepseek = case["expected_response_metadata"].get("deepseek", {})
                for key, value in expected_deepseek.items():
                    self.assertEqual(response_metadata["deepseek"][key], value)

    def test_native_rejections_cover_trust_boundaries(self):
        cases = [
            ({"model": 7, "input": "synthetic"}, "DeepSeek model must be a string"),
            ({"model": "deepseek-chat", "input": "synthetic", "response_format": {"type": "xml"}}, "DeepSeek response_format type `xml` is not supported"),
            ({"model": "deepseek-chat", "input": "synthetic", "reasoning": {"effort": "unbounded"}}, "DeepSeek reasoning effort is not supported"),
            ({"model": "deepseek-chat", "input": [False]}, "DeepSeek input items must be objects"),
        ]
        for request, expected in cases:
            with self.subTest(request=request):
                self.assertEqual(self.run_native({"request": request}), {"error": expected})

    def test_isolated_environment_repeats_without_user_configuration(self):
        wrapper = {"request": {"model": "deepseek-chat", "input": "synthetic clean runtime"}}
        self.assertEqual(self.run_native(wrapper), self.run_native(wrapper))

    def test_clean_runtime_with_only_native_binary_and_official_libraries(self):
        case = next(case for case in self.catalog["cases"] if case["name"] == "defaults")
        result = self.run_native({"request": case["request"]}, sandbox=True,
                                 expected_body=case["upstream_request"]["body"])
        self.assertIn("ok", result)
        self.assertEqual(self.run_native({"request": {"input": [False]}}, sandbox=True),
                         {"error": "DeepSeek input items must be objects"})

    def test_recorded_local_rejections_keep_hidden_diagnostics_explicit(self):
        gaps = [case for case in self.catalog["cases"] if case.get("oracle_observation")]
        self.assertTrue(gaps, "the fixture should retain known pre-provider observations")
        for case in gaps:
            with self.subTest(case=case["name"]):
                response = case["local_response"]
                self.assertEqual(response["status"], 502)
                self.assertEqual(response["body"], "upstream request failed")
                self.assertEqual(hashlib.sha256(response["body"].encode()).hexdigest(), response["sha256"])
                self.assertNotIn("upstream_request", case)
                self.assertIn("detailed translator diagnostic unavailable", case["oracle_observation"])
                self.assertIn("error", self.run_native({"request": case["request"]}))

    def test_other_provider_routes_are_recorded_separately(self):
        routes = [case for case in self.catalog["cases"] if case.get("route_kind") == "other_provider_path"]
        self.assertTrue(routes, "web-search route must remain an independent observation")
        for case in routes:
            with self.subTest(case=case["name"]):
                request = case["upstream_request"]
                self.assertTrue(request["destination"].startswith("127.0.0.1:"))
                self.assertEqual(request["path"], "/anthropic/v1/messages")
                self.assertEqual(case["local_response"]["status"], 502)
                body = case["local_response"]["body"].encode()
                self.assertEqual(hashlib.sha256(body).hexdigest(), case["local_response"]["sha256"])


if __name__ == "__main__":
    unittest.main()
