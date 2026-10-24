"""Independent Unicode 17 alphanumeric property checks."""

import hashlib
import os
import subprocess
import unittest

import test_cli
from test_cli import MODEX, ORACLE, ROOT
from test_log_text import oracle_log_last, projection
from test_log_transcript import oracle as transcript_snapshot

DATA = ROOT / "tests/fixtures/unicode17"
DRIVER = ROOT / os.environ.get("MODEX_UNICODE_PROPERTIES_DRIVER", "build/tests/unicode_properties_driver")


def verify_ucd_sources():
    checksums = {}
    for line in (DATA / "SHA256SUMS").read_text().splitlines():
        digest, filename = line.split()
        checksums[filename] = digest
    for filename in ("DerivedCoreProperties.txt", "UnicodeData.txt"):
        actual = hashlib.sha256((DATA / filename).read_bytes()).hexdigest()
        if checksums.get(filename) != actual:
            raise AssertionError(f"unverified Unicode 17 input: {filename}")


def expected_alphanumeric():
    expected = bytearray(0x110000)
    for line in (DATA / "DerivedCoreProperties.txt").read_text().splitlines():
        record = line.split("#", 1)[0].strip()
        if not record:
            continue
        code_range, prop, *_ = map(str.strip, record.split(";"))
        if prop != "Alphabetic":
            continue
        bounds = code_range.split("..")
        start, end = int(bounds[0], 16), int(bounds[-1], 16)
        expected[start : end + 1] = b"\1" * (end - start + 1)

    first = None
    first_category = None
    for line in (DATA / "UnicodeData.txt").read_text().splitlines():
        fields = line.split(";")
        code, name, category = int(fields[0], 16), fields[1], fields[2]
        if name.endswith(", First>"):
            first, first_category = code, category
        elif name.endswith(", Last>"):
            if first_category.startswith("N"):
                expected[first : code + 1] = b"\1" * (code - first + 1)
            first = first_category = None
        elif category.startswith("N"):
            expected[code] = 1
    expected[0xD800:0xE000] = b"\xff" * 0x800
    return expected


class UnicodePropertyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        verify_ucd_sources()

    def test_every_unicode_scalar_against_independent_unicode_17_data(self):
        if not DRIVER.is_file():
            raise AssertionError("Build tests/unicode_properties_driver.mojo first")
        result = subprocess.run([str(DRIVER)], capture_output=True, check=True, timeout=30)
        self.assertEqual(result.stderr, b"")
        expected = expected_alphanumeric()
        self.assertEqual(len(result.stdout), len(expected))
        mismatches = [(hex(code), actual, expected[code])
                      for code, actual in enumerate(result.stdout) if actual != expected[code]]
        self.assertEqual(mismatches[:20], [])

    def test_deseret_letters_are_alphanumeric_and_retained_in_transcript(self):
        result = subprocess.run([str(DRIVER)], capture_output=True, check=True, timeout=30)
        self.assertEqual(result.stdout[0x10400:0x10408], b"\1" * 8)
        text = "\U00010400" * 8
        self.assertEqual(projection("tool", text), text)
        baseline = oracle_log_last("response_item", {
            "type": "function_call_output", "output": text,
        })
        self.assertEqual(baseline[0]["text"], text)
        self.assertEqual(transcript_snapshot("response_item", {"type": "function_call_output", "output": text}, MODEX), baseline)

    def test_tool_output_property_edges_match_production_oracle(self):
        for code in (0x00D7, 0x0345, 0x0378, 0x06DE, 0x10400, 0x16D63, 0x1E030, 0x1F100):
            payload = {"type": "function_call_output", "output": chr(code) * 8}
            with self.subTest(code=hex(code)):
                self.assertEqual(transcript_snapshot("response_item", payload, MODEX),
                                 transcript_snapshot("response_item", payload, ORACLE))


if __name__ == "__main__":
    unittest.main()
