"""Compare missing/null DeepSeek model routing with frozen Prodex 0.439.5."""

import hashlib
import json
from unittest.mock import patch
import unittest

import test_super_launch
from test_cli import (MODEX, HISTORICAL_04395_ORACLE as ORACLE,
                      HISTORICAL_04395_ORACLE_SHA256 as ORACLE_SHA256)


CODEX_REQUEST = 'body = b"\\x00synthetic\\xff" if passthrough else json.dumps({"model":"deepseek-chat","input":"synthetic prompt","stream":scenario == "stream"},separators=(",",":")).encode()'


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


class ProviderCatalog04395Tests(unittest.TestCase):
    def test_model_fallback_and_explicit_selection_match_release(self):
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        self.assertTrue(MODEX.is_file(), f"Modex binary has not been built: {MODEX}")
        cases = (
            ("missing_launch_chat", {"input": "synthetic prompt", "stream": False}, "deepseek-chat", "deepseek-v4-pro"),
            ("missing_launch_flash", {"input": "synthetic prompt", "stream": False}, "deepseek-flash", "deepseek-v4-pro"),
            ("missing_launch_compat_flash", {"input": "synthetic prompt", "stream": False}, "deepseek-v4-flash", "deepseek-v4-pro"),
            ("null_launch_flash", {"model": None, "input": "synthetic prompt", "stream": False}, "deepseek-flash", "deepseek-v4-pro"),
            ("explicit_model_wins", {"model": "deepseek-v4-flash", "input": "synthetic prompt", "stream": False}, "deepseek-flash", "deepseek-v4-flash"),
            ("non_simple_missing_model", {"input": "synthetic prompt", "safety_identifier": "synthetic-user", "stream": False}, "deepseek-flash", "deepseek-v4-pro"),
        )
        harness = test_super_launch.SuperLaunchTests()
        for name, request, launch_model, expected_model in cases:
            with self.subTest(case=name):
                captures = []
                with patch.object(test_super_launch, "CODEX", _codex_with_request(request)):
                    for binary in (ORACLE, MODEX):
                        result, _, upstream, _ = harness.run_launch(binary=binary, scenario="buffered", model=launch_model)
                        self.assertEqual((result.returncode, result.stdout), (0, b"synthetic-client-complete\n"), result.stderr)
                        self.assertEqual(len(upstream), 1)
                        captures.append(upstream[0])

                baseline, modex = captures
                self.assertEqual(modex["path"], baseline["path"])
                baseline_body = json.loads(bytes.fromhex(baseline["body"]))
                modex_body = json.loads(bytes.fromhex(modex["body"]))
                self.assertEqual(modex_body, baseline_body)
                self.assertEqual(baseline_body["model"], expected_model)
                if name == "non_simple_missing_model":
                    self.assertEqual(baseline_body["user_id"], "synthetic-user")
                for capture in (baseline, modex):
                    headers = {name.lower(): value for name, value in capture["headers"].items()}
                    self.assertEqual(headers["authorization"], "Bearer synthetic-provider-key")


if __name__ == "__main__":
    unittest.main()
