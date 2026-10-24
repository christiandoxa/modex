"""Generated JSON differentials use only the independent Python standard parser."""

import json
from pathlib import Path
import random
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "build/tests/json_driver"


def generated_value(randomizer, depth=0):
    choice = randomizer.randrange(4 if depth >= 5 else 6)
    if choice == 0:
        return randomizer.choice((None, True, False))
    if choice == 1:
        return randomizer.randrange(-(2**63), 2**64)
    if choice == 2:
        return randomizer.uniform(-1e90, 1e90)
    if choice == 3:
        alphabet = 'abcXYZ012"\\\n\r\t\0\b\f/é雪🔥\u2028\u2000'
        return "".join(randomizer.choice(alphabet) for _ in range(randomizer.randrange(60)))
    if choice == 4:
        return [generated_value(randomizer, depth + 1) for _ in range(randomizer.randrange(6))]
    return {f"field-{index}": generated_value(randomizer, depth + 1)
            for index in range(randomizer.randrange(6))}


def driver(lines):
    result = subprocess.run([str(DRIVER)], input=b"\n".join(lines) + b"\n",
                            capture_output=True, timeout=15, check=False)
    if result.returncode != 0 or result.stderr:
        raise AssertionError(f"JSON driver failed: {result.returncode}: {result.stderr!r}")
    output = result.stdout.splitlines()
    if len(output) != len(lines):
        raise AssertionError(f"Expected {len(lines)} responses; got {len(output)}")
    return output


class JsonDifferentialTests(unittest.TestCase):
    def test_generated_values_round_trip_through_mojo_tree(self):
        randomizer = random.Random(433_439)
        values = [generated_value(randomizer) for _ in range(500)]
        lines = [json.dumps(value, ensure_ascii=index % 2 == 0,
                            separators=(",", ":")).encode() for index, value in enumerate(values)]
        for original, output in zip(values, driver(lines), strict=True):
            self.assertNotEqual(output, b"ERROR")
            self.assertEqual(json.loads(output), original)

    def test_invalid_syntax_utf8_and_number_overflow_are_rejected(self):
        malformed = [b"", b" ", b"+1", b"00", b"-01", b".1", b"1.", b"1e", b"1e+",
                     b"1e999", b"-1e999", b"NaN", b"Infinity", b"[1,]", b"[,1]", b"[1 2]",
                     b'{"x":1,}', b'{"x" 1}', b'{1:2}', b'{"x":}', b'"unterminated',
                     b'"\\q"', b'"\\u123"', b'"\\u12xz"', b'"\\uD800"', b'"\\uDC00"',
                     b'"\\uD800\\u0041"', b'"\xff"', b'"\xc0\x80"', b'"\xed\xa0\x80"',
                     b'"\xf4\x90\x80\x80"', b'"\x00"', b"true false", b"nullx",
                     b"[" * 128 + b"0" + b"]" * 128]
        self.assertEqual(driver(malformed), [b"ERROR"] * len(malformed))

    def test_escaped_keys_duplicate_keys_and_boundary_values(self):
        lines = [b'{"a":1,"\\u0061":2}', b'"\\u0000\\u001f\\u007f"',
                 b'"\\uD800\\uDC00\\uDBFF\\uDFFF"', b"-0", b"1e-9999",
                 b"18446744073709551615", b"-9223372036854775808",
                 b"1.7976931348623157e308", b"2.2250738585072014e-308"]
        for source, output in zip(lines, driver(lines), strict=True):
            self.assertNotEqual(output, b"ERROR")
            self.assertEqual(json.loads(output), json.loads(source))


if __name__ == "__main__":
    unittest.main()
