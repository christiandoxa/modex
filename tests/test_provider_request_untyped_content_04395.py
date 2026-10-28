"""Compare untyped DeepSeek message content with 0.439.2 and historical 0.439.5."""

import hashlib
import json
from unittest.mock import patch
import unittest

import test_super_launch
from test_cli import (MODEX, ORACLE as ACTIVE_ORACLE, ORACLE_SHA256 as ACTIVE_ORACLE_SHA256,
                      HISTORICAL_04395_ORACLE as ORACLE,
                      HISTORICAL_04395_ORACLE_SHA256 as ORACLE_SHA256)
from test_provider_catalog_04395 import _codex_with_request


CASES = (
    ("null", {"role": "user", "content": None}, "null"),
    ("number", {"role": "user", "content": 17}, "17"),
    ("boolean", {"role": "user", "content": True}, "true"),
    ("unknown-object", {"role": "user", "content": {"unknown": 7}}, '{"unknown":7}'),
    ("image-object", {"role": "user", "content": {"type": "input_image"}}, '{"type":"input_image"}'),
    ("image-array", {"role": "user", "content": [{"type": "input_image"}]}, ""),
    ("mixed-array", {"role": "user", "content": [{"text": "hi"}, 7, {"type": "input_image"}]}, "hi"),
    ("cache-control", {"role": "user", "content": [{"text": "hi", "cache_control": {}}]}, "hi"),
    ("unsupported-role", {"role": "critic", "content": "hi"}, "hi"),
    ("typed-valid", {"type": "message", "role": "user", "content": "hi"}, "hi"),
    ("typed-null", {"type": "message", "role": "user", "content": None}, None),
    ("typed-number", {"type": "message", "role": "user", "content": 17}, None),
    ("typed-image", {"type": "message", "role": "user", "content": [{"type": "input_image"}]}, None),
    ("typed-cache-control", {"type": "message", "role": "user", "content": [{"text": "hi", "cache_control": {}}]}, None),
    ("untyped-prefix", {"role": "user", "content": "hi", "prefix": True}, None),
)


class UntypedContent04395Tests(unittest.TestCase):
    def test_content_mapping_and_typed_validation_match_release(self):
        self.assertEqual(hashlib.sha256(ACTIVE_ORACLE.read_bytes()).hexdigest(), ACTIVE_ORACLE_SHA256)
        self.assertEqual(hashlib.sha256(ORACLE.read_bytes()).hexdigest(), ORACLE_SHA256)
        harness = test_super_launch.SuperLaunchTests()
        for non_simple in (False, True):
            for name, item, expected in CASES:
                request = {"model": "deepseek-chat", "input": [item], "stream": False}
                if non_simple:
                    request["safety_identifier"] = "synthetic-user"
                with self.subTest(case=name, non_simple=non_simple):
                    captures = []
                    for binary in (ACTIVE_ORACLE, ORACLE, MODEX):
                        with patch.object(test_super_launch, "CODEX", _codex_with_request(request)):
                            result, records, upstream, state = harness.run_launch(
                                binary=binary, scenario="buffered", model="deepseek-chat"
                            )
                        response = next(record for record in records if record["kind"] == "response")
                        self.assertEqual(state["leftovers"], [])
                        if expected is None:
                            self.assertEqual((result.returncode, response["status"], upstream), (1, 502, []))
                            captures.append(None)
                            continue
                        self.assertEqual((result.returncode, response["status"]), (0, 200), result.stderr)
                        self.assertEqual(len(upstream), 1)
                        body = json.loads(bytes.fromhex(upstream[0]["body"]))
                        self.assertEqual(body["messages"], [{"role": "user", "content": expected}])
                        captures.append(body)
                    self.assertEqual(captures[1:], [captures[0], captures[0]])


if __name__ == "__main__":
    unittest.main()
