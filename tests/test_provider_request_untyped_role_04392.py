"""Compare untyped DeepSeek input role coercion with frozen Prodex 0.439.2."""

import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch
import unittest

import test_super_launch
from test_cli import MODEX


REFERENCE_CACHE = Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    REFERENCE_CACHE / "oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
REFERENCE = Path(os.environ.get(
    "MODEX_REFERENCE_04392_DIR",
    REFERENCE_CACHE / "references/prodex-72b77478a5198fc5da6b4d2253137f9cdbf43be9",
))
REFERENCE_DEEPSEEK_SHA256 = "15fb0e83167fd78b7627859343fe7c6703ab0471a33ab48f0a351c01296eda58"
CONTENT = "synthetic role content"
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


CASES = (
    ("unsupported_string", {"role": "critic", "content": CONTENT}, 200, "user"),
    ("empty_string", {"role": "", "content": CONTENT}, 200, "user"),
    ("null_role", {"role": None, "content": CONTENT}, 200, "user"),
    ("number_role", {"role": 17, "content": CONTENT}, 200, "user"),
    ("object_role", {"role": {"name": "synthetic"}, "content": CONTENT}, 200, "user"),
    ("array_role", {"role": ["assistant"], "content": CONTENT}, 200, "user"),
    ("omitted_role", {"content": CONTENT}, 200, "user"),
    ("typed_tool_control", {"type": "message", "role": "tool", "content": CONTENT}, 502, None),
    ("typed_invalid_role_control", {"type": "message", "role": "critic", "content": CONTENT}, 502, None),
    ("typed_non_string_role_control", {"type": "message", "role": 17, "content": CONTENT}, 502, None),
)


class ProviderRequestUntypedRole04392Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ORACLE.is_file():
            raise AssertionError(f"Pinned Prodex 0.439.2 oracle is missing: {ORACLE}")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.439.2")
        source = REFERENCE / "mojo/prodex_core/deepseek.mojo"
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != REFERENCE_DEEPSEEK_SHA256:
            raise AssertionError("The cached DeepSeek source does not match pinned commit 72b77478")
        if not MODEX.is_file():
            raise AssertionError(f"Modex binary has not been built: {MODEX}")

    def test_untyped_roles_are_coerced_but_typed_message_roles_stay_strict(self):
        harness = test_super_launch.SuperLaunchTests()
        for non_simple in (False, True):
            for name, item, expected_status, expected_role in CASES:
                request = {"model": "deepseek-chat", "input": [item], "stream": False}
                if non_simple:
                    request["safety_identifier"] = "synthetic-user"
                with self.subTest(case=name, non_simple=non_simple):
                    captures = []
                    for binary in (ORACLE, MODEX):
                        with patch.object(test_super_launch, "CODEX", _codex_with_request(request)):
                            result, records, upstream, state = harness.run_launch(
                                binary=binary, scenario="buffered", model="deepseek-chat"
                            )
                        response = next(record for record in records if record["kind"] == "response")
                        self.assertEqual(state["leftovers"], [])
                        self.assertEqual(response["status"], expected_status)
                        if expected_role is None:
                            self.assertEqual((result.returncode, upstream), (1, []))
                            captures.append(None)
                            continue
                        self.assertEqual((result.returncode, result.stdout), (0, b"synthetic-client-complete\n"), result.stderr)
                        self.assertEqual(len(upstream), 1)
                        body = json.loads(bytes.fromhex(upstream[0]["body"]))
                        self.assertEqual(body["messages"], [{"role": expected_role, "content": CONTENT}])
                        if non_simple:
                            self.assertEqual(body["user_id"], "synthetic-user")
                        else:
                            self.assertNotIn("user_id", body)
                        captures.append(body)
                    self.assertEqual(captures[1], captures[0])


if __name__ == "__main__":
    unittest.main()
