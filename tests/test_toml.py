"""Acceptance differential against Python's independent TOML 1.0 parser."""

import subprocess
import tomllib
from pathlib import Path
import os
import json
from decimal import Decimal
import hashlib
import unittest


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / os.environ.get("MODEX_TOML_TEST_DRIVER", "build/tests/toml_driver")
CORPUS = ROOT / "tests/fixtures/toml11"


def canonical_datetime(kind, value):
    if kind == "date-local":
        return value
    timezone = ""
    if kind == "datetime":
        if value.endswith(("Z", "z")):
            timezone, value = "Z", value[:-1]
        else:
            for i in range(10 if "T" in value or "t" in value or " " in value else 5, len(value)):
                if value[i] in "+-":
                    timezone, value = value[i:], value[:i]
                    break
    if kind.startswith("datetime"):
        value = value[:10] + "T" + value[11:]
    if "T" in value:
        date, value = value.split("T", 1)
    else:
        date = ""
    parts = value.split(":")
    seconds = parts[2] if len(parts) == 3 else "00"
    if "." in seconds:
        whole, fraction = seconds.split(".", 1)
        fraction = fraction.rstrip("0")
        seconds = whole + ("." + fraction if fraction else "")
    time = parts[0] + ":" + parts[1] + ":" + seconds
    return (date + "T" if date else "") + time + timezone


def normalize_toml_test_value(value):
    if isinstance(value, list):
        return [normalize_toml_test_value(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"type", "value"} and value["type"] in {
            "string", "integer", "float", "bool", "datetime", "datetime-local",
            "date-local", "time-local",
        }:
            kind, raw = value["type"], value["value"]
            if kind == "integer":
                return kind, int(raw.replace("_", ""), 0 if raw.lstrip("+-").startswith(("0x", "0o", "0b")) else 10)
            if kind == "float":
                number = Decimal(raw.replace("_", ""))
                if number.is_nan():
                    raw = "nan"
                elif number.is_infinite():
                    raw = "-inf" if number.is_signed() else "inf"
                elif number.is_zero():
                    raw = ("zero", number.is_signed())
                else:
                    raw = number
            elif kind in {"datetime", "datetime-local", "date-local", "time-local"}:
                raw = canonical_datetime(kind, raw)
            return kind, raw
        return {key: normalize_toml_test_value(item) for key, item in value.items()}
    return value


class TomlDifferentialTests(unittest.TestCase):
    def compare(self, source):
        try:
            tomllib.loads(source)
            standard_accepts = True
        except tomllib.TOMLDecodeError:
            standard_accepts = False
        result = subprocess.run([str(DRIVER)], input=source.encode(), capture_output=True,
                                cwd=ROOT, timeout=10, check=True)
        native_accepts = result.stdout.strip() != b"ERROR"
        self.assertEqual(native_accepts, standard_accepts, source)

    def test_spec_overlap_examples(self):
        valid = [
            'title = "TOML Example"\n[owner]\nname = "Tom"\ndob = 1979-05-27T07:32:00Z\n',
            'a.b = 1\narr = [1, 2, { x = "y" }]\n',
            'text = """\nRoses are red\nViolets are blue\n"""\n',
            "literal = '''\nraw\\ntext\n'''\n",
            'hex = 0xDEAD_BEEF\nbin = 0b1101\noct = 0o755\nfloat = 1_000.5e+1\n',
            '[[products]]\nname = "A"\n[[products]]\nname = "B"\n',
            '"127.0.0.1" = "value"\nsite."google.com" = true\n"" = "empty key"\n',
            'mixed = [1, "two", [3], {name = "four"}]\ninline = {point = {x = 1, y = 2}, enabled = true}\n',
            'date = 1979-05-27\ntime = 07:32:00.5\nlocal = 1979-05-27T07:32:00\noffset = 1979-05-27T07:32:00-07:00\n',
            'trailing = [1, 2,]\n',
        ]
        invalid = [
            'x=1\nx=2\n', 'x=01\n', '[a]\nx=1\n[a]\ny=2\n',
            'x = "bad\\q"\n', 'x = {a=1, a=2}\n',
            'fruit.apple = 1\n[fruit.apple]\n',
            'a = { b = 1 }\na.c = 2\n',
            'a = [1]\n[[a]]\n',
            'x = 1__0\n', 'x = 01.2\n', 'x = 1.\n', 'x = .1\n', 'x = 1e+\n',
            'x = 2023-02-29\n', 'x = 2024-13-01\n', 'x = 25:00:00\n',
        ]
        for source in valid + invalid:
            with self.subTest(source=source):
                self.compare(source)

    def test_invalid_utf8_is_rejected(self):
        result = subprocess.run([str(DRIVER)], input=b"x = \xff\n", capture_output=True,
                                cwd=ROOT, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), b"ERROR")

    def test_value_normalization_preserves_precision_and_signed_zero(self):
        self.assertNotEqual(
            canonical_datetime("datetime-local", "1979-05-27T07:32:00.0000001"),
            canonical_datetime("datetime-local", "1979-05-27T07:32:00.0000002"),
        )
        self.assertEqual(
            canonical_datetime("datetime-local", "1979-05-27T07:32:00.6000"),
            canonical_datetime("datetime-local", "1979-05-27T07:32:00.6"),
        )
        negative_zero = normalize_toml_test_value({"type": "float", "value": "-0.0"})
        positive_zero = normalize_toml_test_value({"type": "float", "value": "0.0"})
        self.assertNotEqual(negative_zero, positive_zero)

    def test_pinned_upstream_conformance_corpus(self):
        manifest = CORPUS / "files-toml-1.1.0"
        checksums = CORPUS / "SHA256SUMS"
        self.assertTrue(manifest.is_file(), f"missing pinned TOML manifest: {manifest}")
        self.assertTrue(checksums.is_file(), f"missing TOML fixture checksums: {checksums}")
        expected_hashes = {}
        for line in checksums.read_text().splitlines():
            digest, name = line.split(maxsplit=1)
            expected_hashes[name.removeprefix("*")] = digest
        paths = [line.strip() for line in manifest.read_text().splitlines() if line.strip()]
        valid = [name for name in paths if name.startswith("valid/") and name.endswith(".toml")]
        invalid = [name for name in paths if name.startswith("invalid/") and name.endswith(".toml")]
        self.assertTrue(valid and invalid)
        self.assertEqual((len(valid), len(invalid)), (218, 494))
        for name in paths:
            source = CORPUS / name
            self.assertTrue(source.is_file(), f"manifest file missing: {source}")
            relative = source.relative_to(CORPUS).as_posix()
            expected = expected_hashes.get(relative)
            self.assertIsNotNone(expected, f"checksum missing: {relative}")
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), expected, relative)
        for name in valid:
            source = CORPUS / name
            with self.subTest(path=name):
                result = subprocess.run([str(DRIVER)], input=source.read_bytes(), capture_output=True,
                                        cwd=ROOT, timeout=10, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotEqual(result.stdout.strip(), b"ERROR")
                expected_path = source.with_suffix(".json")
                self.assertTrue(expected_path.is_file(), f"missing expected output: {expected_path}")
                expected_name = expected_path.relative_to(CORPUS).as_posix()
                self.assertIn(expected_name, expected_hashes, f"checksum missing: {expected_name}")
                actual = json.loads(result.stdout)
                expected = json.loads(expected_path.read_text())
                self.assertEqual(normalize_toml_test_value(actual), normalize_toml_test_value(expected))
        for name in invalid:
            source = CORPUS / name
            with self.subTest(path=name):
                result = subprocess.run([str(DRIVER)], input=source.read_bytes(), capture_output=True,
                                        cwd=ROOT, timeout=10, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), b"ERROR")


if __name__ == "__main__":
    unittest.main()
