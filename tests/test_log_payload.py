"""Focused checks for readable upstream payload projections."""

import base64
import json
from pathlib import Path
import subprocess
import unittest
from compression import zstd

from test_cli import MODEX, ORACLE
import test_log_runtime

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "build/tests/log_payload_driver"


class LogPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_cli
        test_cli.CliTests.setUpClass()

    def test_text_is_preserved_and_known_binary_has_label(self):
        self.assertEqual(display(b"hello\n"), "hello\n\n")
        self.assertEqual(display(b"\x89PNG\r\n\x1a\n"), "[binary payload: PNG image]\n")
        self.assertEqual(self.oracle_payload(b"hello\n"), "hello\n")
        self.assertEqual(self.oracle_payload(b"\x89PNG\r\n\x1a\n"), display(b"\x89PNG\r\n\x1a\n").rstrip("\n"))

    def test_zstd_limit_requires_complete_frame(self):
        exact = zstd.compress(b"a" * (128 * 1024))
        self.assertEqual(display(exact), "a" * (128 * 1024) + "\n")
        self.assertEqual(self.oracle_payload(exact), "a" * (128 * 1024))
        too_large = zstd.compress(b"a" * (128 * 1024 + 1))
        self.assertEqual(display(too_large), "[binary payload: zstd stream]\n")
        self.assertEqual(self.oracle_payload(too_large), display(too_large).rstrip("\n"))
        self.assertEqual(display(exact[:-1]), "[binary payload: zstd stream]\n")
        self.assertEqual(display(zstd.compress(b"a") + zstd.compress(b"b")), "ab\n")
        self.assertEqual(display(exact + zstd.compress(b"b")), "[binary payload: zstd stream]\n")

    def test_binary_signatures_and_first_present_path(self):
        self.assertEqual(display(b"GIF87a"), "GIF87a\n")
        self.assertEqual(display(b"GIF87a\x00"), "[binary payload: GIF image]\n")
        self.assertEqual(display(b"GIF8\x00x"), "[binary payload: unknown binary data]\n")
        self.assertEqual(display(b"RIFFxxxxWEBP"), "RIFFxxxxWEBP\n")
        self.assertEqual(display(b"RIFFxxxxWEBP\x00"), "[binary payload: WebP image]\n")
        self.assertEqual(display(b"xxxx\x00xxxWEBP"), "[binary payload: unknown binary data]\n")
        self.assertEqual(display(b"\x00PNG-ish", ["", "  /tmp/表  "], [False, True]),
                         "[binary payload: path=/tmp/表]\n")
        self.assertEqual(self.oracle_payload(b"\x00PNG-ish", {"path": "", "file_path": "later"}),
                         "[binary payload: unknown binary data]")

    def oracle_payload(self, payload, fields=None):
        fields = {"payload_b64": base64.b64encode(payload).decode(), **(fields or {})}
        record = {"timestamp": "2026-10-24T01:02:04Z", "event": "upstream_payload", "fields": fields}
        def prepare(root, runtime):
            (runtime / "prodex-runtime-fixture.log").write_text(json.dumps(record) + "\n")
        runner = test_log_runtime.LogRuntimeTests()
        expected = runner.invoke(ORACLE, prepare)
        actual = runner.invoke(MODEX, prepare)
        self.assertEqual(actual, expected)
        self.assertEqual(expected[0], 0, expected[2])
        self.assertTrue(expected[1], "The oracle must observe the runtime fixture")
        return json.loads(expected[1])["payload"]


def display(payload, paths=None, present=None):
    paths = list(paths or [])[:7] + [""] * (7 - len(paths or []))
    present = list(present or [])[:7] + [False] * (7 - len(present or []))
    request = b"".join((b"1" if flag else b"0") + path.encode() + b"\n"
                       for path, flag in zip(paths, present)) + payload
    result = subprocess.run([str(DRIVER)], input=request, capture_output=True, check=True)
    return result.stdout.decode()


if __name__ == "__main__":
    unittest.main()
