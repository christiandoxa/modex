"""Compare DeepSeek model fallback types with frozen Prodex 0.439.5."""

import hashlib
import json
from unittest.mock import patch
import unittest

import test_super_launch
from test_cli import MODEX, ORACLE, ORACLE_SHA256


CODEX_REQUEST = 'body = b"\\x00synthetic\\xff" if passthrough else json.dumps({"model":"deepseek-chat","input":"synthetic prompt","stream":scenario == "stream"},separators=(",",":")).encode()'
MODEL_CASES = (
    ("number", 7, "deepseek-v4-pro"),
    ("boolean-false", False, "deepseek-v4-pro"),
    ("boolean-true", True, "deepseek-v4-pro"),
    ("array", [], "deepseek-v4-pro"),
    ("object", {}, "deepseek-v4-pro"),
    ("null", None, "deepseek-v4-pro"),
    ("empty-string", "", "deepseek-v4-pro"),
    ("unicode-whitespace-string", " \u2003 ", "deepseek-v4-pro"),
    ("explicit-flash", "deepseek-flash", "deepseek-flash"),
    ("explicit-compat-flash", "deepseek-v4-flash", "deepseek-v4-flash"),
    ("combo-flash-pro", "combo:flash>pro", "deepseek-flash"),
    ("combo-pro-flash", "combo:pro,flash", "deepseek-v4-pro"),
)


def _codex_with_request(request):
    source = test_super_launch.CODEX
    if source.count(CODEX_REQUEST) != 1:
        raise AssertionError("Expected one synthetic Codex request body")
    replacement = (
        'body = b"\\x00synthetic\\xff" if passthrough else json.dumps('
        + repr(request)
        + ',separators=(",",":")).encode()'
    )
    return source.replace(CODEX_REQUEST, replacement)


class ProviderNonStringModel04395Tests(unittest.TestCase):
    def test_model_fallback_types_match_release_in_simple_and_non_simple_requests(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        self.assertTrue(MODEX.is_file(), f"Modex binary has not been built: {MODEX}")
        harness = test_super_launch.SuperLaunchTests()
        for name, model, expected_model in MODEL_CASES:
            for shape in ("simple", "non-simple"):
                with self.subTest(model=name, shape=shape):
                    request = {"model": model, "input": "synthetic prompt", "stream": False}
                    if shape == "non-simple":
                        request["safety_identifier"] = "synthetic-user"
                    captures = []
                    with patch.object(test_super_launch, "CODEX", _codex_with_request(request)):
                        for binary in (ORACLE, MODEX):
                            result, _, upstream, _ = harness.run_launch(
                                binary=binary, scenario="buffered", model="deepseek-flash"
                            )
                            self.assertEqual(
                                (result.returncode, result.stdout),
                                (0, b"synthetic-client-complete\n"),
                                result.stderr,
                            )
                            self.assertEqual(len(upstream), 1)
                            captures.append(upstream[0])

                    baseline, modex = captures
                    self.assertEqual(modex["path"], baseline["path"])
                    baseline_body = json.loads(bytes.fromhex(baseline["body"]))
                    modex_body = json.loads(bytes.fromhex(modex["body"]))
                    self.assertEqual(modex_body, baseline_body)
                    self.assertEqual(baseline_body["model"], expected_model)
                    if shape == "non-simple":
                        self.assertEqual(baseline_body["user_id"], "synthetic-user")
                    for capture in (baseline, modex):
                        headers = {key.lower(): value for key, value in capture["headers"].items()}
                        self.assertEqual(headers["authorization"], "Bearer synthetic-provider-key")


if __name__ == "__main__":
    unittest.main()
