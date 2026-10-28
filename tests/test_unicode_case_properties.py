"""Compare every scalar's case properties with the pinned Unicode 17 data."""

import subprocess
import unittest

from test_unicode_properties import DATA, DRIVER, verify_ucd_sources


class UnicodeCasePropertiesTests(unittest.TestCase):
    def test_all_scalars_match_unicode_17(self):
        verify_ucd_sources()
        if not DRIVER.is_file():
            raise AssertionError("Build tests/unicode_properties_driver.mojo first")
        expected = bytearray(0x110000)
        for line in (DATA / "DerivedCoreProperties.txt").read_text().splitlines():
            record = line.split("#", 1)[0].strip()
            if not record:
                continue
            code_range, prop, *_ = map(str.strip, record.split(";"))
            bit = {"Cased": 1, "Case_Ignorable": 2}.get(prop, 0)
            if not bit:
                continue
            bounds = code_range.split("..")
            for code in range(int(bounds[0], 16), int(bounds[-1], 16) + 1):
                expected[code] |= bit
        expected[0xD800:0xE000] = b"\xff" * 0x800
        result = subprocess.run([str(DRIVER), "--case"], capture_output=True, check=True, timeout=30)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(len(result.stdout), len(expected))
        differences = [(hex(code), actual, expected[code]) for code, actual in enumerate(result.stdout)
                       if actual != expected[code]]
        self.assertEqual(differences[:20], [])


if __name__ == "__main__":
    unittest.main()
