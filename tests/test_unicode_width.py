"""Independent width-data checks; production never imports this harness."""

import json
import subprocess
import unittest

from test_cli import ROOT


DATA = ROOT / "tests/fixtures/unicode17"
DRIVER = ROOT / "build/tests/text_driver"


def properties(filename):
    result = {}
    for line in (DATA / filename).read_text().splitlines():
        value = line.split("#", 1)[0].strip()
        if not value:
            continue
        codes, name, *_ = map(str.strip, value.split(";"))
        bounds = codes.split("..")
        result.setdefault(name, set()).update(range(int(bounds[0], 16), int(bounds[-1], 16) + 1))
    return result


def emoji_sequence_cases():
    emoji = properties("emoji-data.txt")
    east_asian = properties("EastAsianWidth.txt")
    wide = east_asian["W"] | east_asian["F"]
    cases = []
    for line in (DATA / "emoji-variation-sequences.txt").read_text().splitlines():
        data = line.split("#", 1)[0].strip()
        if not data:
            continue
        code, selector = (int(value, 16) for value in data.split(";")[0].split())
        width = 2 if code in wide else 1
        if selector == 0xFE0F:
            width = 2
        elif code in emoji["Emoji_Presentation"] and not 0x1F200 <= code <= 0x1F2FF:
            width = 1
        cases.append((chr(code) + chr(selector), width))
    for base in sorted(emoji["Emoji_Modifier_Base"]):
        for modifier in range(0x1F3FB, 0x1F400):
            cases.append((chr(base) + chr(modifier), 2))
    for line in (DATA / "emoji-zwj-sequences.txt").read_text().splitlines():
        data = line.split("#", 1)[0].strip()
        if data:
            cases.append(("".join(chr(int(value, 16)) for value in data.split(";")[0].split()), 2))
    return cases


class UnicodeWidthTests(unittest.TestCase):
    def assert_widths(self, cases):
        request = "".join(json.dumps(value) + "\n" for value, _ in cases)
        result = subprocess.run([str(DRIVER)], input=request.encode(), capture_output=True, check=True, timeout=20)
        self.assertEqual(result.stderr, b"")
        widths = result.stdout.decode().splitlines()
        self.assertEqual(len(widths), len(cases))
        for (value, expected), width in zip(cases, widths):
            with self.subTest(value=value):
                self.assertEqual(width, str(expected))

    def test_every_scalar_against_unicode_17_data(self):
        east_asian = properties("EastAsianWidth.txt")
        core = properties("DerivedCoreProperties.txt")
        grapheme = properties("GraphemeBreakProperty.txt")
        hangul = properties("HangulSyllableType.txt")
        expected = bytearray([1]) * 0x110000
        for code in east_asian["W"] | east_asian["F"]:
            expected[code] = 2
        prepended_marks = set(range(0x600, 0x606)) | {0x6DD, 0x70F, 0x890, 0x891, 0x8E2, 0x110BD, 0x110CD}
        zero = (core["Default_Ignorable_Code_Point"] | core["Grapheme_Extend"] | hangul["V"]
                | hangul["T"] | (grapheme["Prepend"] - prepended_marks)
                | {0x605, 0x70F, 0x890, 0x891, 0x8E2, 0xA8FA}
                | set(range(0x20)) | set(range(0x7F, 0xA0)))
        for code in zero:
            expected[code] = 0
        expected[0x115F] = expected[0x17A4] = 2
        expected[0x17D8] = 3
        expected[0x2D7F] = 1
        expected[0xD800:0xE000] = b"\xff" * 0x800
        result = subprocess.run([str(DRIVER), "--scalars"], capture_output=True, check=True, timeout=20)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(len(result.stdout), len(expected))
        mismatches = [(hex(code), actual, expected[code]) for code, actual in enumerate(result.stdout)
                      if actual != expected[code]]
        self.assertEqual(mismatches[:30], [])

    def test_auxiliary_properties_against_unicode_data(self):
        joining = properties("DerivedJoiningType.txt")["T"]
        emoji = properties("emoji-data.txt")
        variants = {int(line.split()[0], 16) for line in (DATA / "emoji-variation-sequences.txt").read_text().splitlines()
                    if line and not line.startswith("#")}
        text_variants = {code for code in variants & emoji["Emoji_Presentation"] if not 0x1F200 <= code <= 0x1F2FF}
        variants -= emoji["Emoji_Presentation"]
        expected = bytearray(0x110000)
        for flag, values in enumerate((joining, emoji["Emoji_Presentation"], variants, emoji["Emoji_Modifier_Base"], text_variants)):
            for code in values:
                expected[code] |= 1 << flag
        expected[0xD800:0xE000] = b"\xff" * 0x800
        result = subprocess.run([str(DRIVER), "--properties"], capture_output=True, check=True, timeout=20)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(len(result.stdout), len(expected))
        mismatches = [(hex(code), actual, expected[code]) for code, actual in enumerate(result.stdout)
                      if actual != expected[code]]
        self.assertEqual(mismatches[:30], [])

    def test_emoji_data_sequences(self):
        self.assert_widths(emoji_sequence_cases())

    def test_controls_and_script_ligatures(self):
        cases = [("\0", 1), ("\t", 1), ("\r\n", 1), ("A\r\nB", 3),
                 ("\u0644\u0627", 1), ("\u0644\u065f\u065e\u0623", 1),
                 ("\u1a15\u1a17\u200d\u1a10", 1), ("\u05d0\u200d\u05dc", 1),
                 ("\u17d2\u1780", 0), ("\ua4f9\ua4fc", 1),
                 ("\U00010c32\u200d\U00010c03", 1), ("\u2d4f\u2d7f\u2d3e", 1),
                 ("\U00016d67\U00016d67", 1), ("\U00016d63\U00016d67", 1),
                 ("\U00016d63\U00016d67\U00016d67", 1), ("\U00016d69\U00016d67", 1),
                 ("\U00016d63\U00016d68", 1), ("\U00016d63\u200d\U00016d67", 2),
                 ("\U00016d63\u034f\U00016d67", 2), ("\u2018\ufe01", 2),
                 ("\u2018\ufe00", 1), ("\u2018\ufe02", 1)]
        self.assert_widths(cases)

    def test_all_arabic_lam_alef_groups(self):
        groups = {}
        for line in (DATA / "ArabicShaping.txt").read_text().splitlines():
            data = line.split("#", 1)[0].strip()
            if data:
                code, _, _, group = map(str.strip, data.split(";"))
                groups.setdefault(group, []).append(chr(int(code, 16)))
        self.assert_widths([(lam + mark + alef, 1) for lam in groups["LAM"] for alef in groups["ALEF"]
                            for mark in ("", "\u065f", "\u034f")])


if __name__ == "__main__":
    unittest.main()
