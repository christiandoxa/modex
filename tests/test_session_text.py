"""Compare unmodified plain session output in identical disposable homes."""

import errno
import fcntl
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import tempfile
import termios
import unittest

from session_oracle import fixture, sandbox_command
import test_cli
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as SHA256_01651
from test_cli import MODEX, ORACLE
from test_session_profile_04392 import profile_state, write_state
from test_unicode_width import emoji_sequence_cases, properties


def compare_text(arguments, *, columns=None, change=None):
    with tempfile.TemporaryDirectory(prefix="modex-session-text-") as directory:
        root = Path(directory) / "fixture with spaces"
        outputs = []
        for binary in (ORACLE, MODEX):
            root.mkdir()
            fixture(root)
            if change:
                change(root)
            environment = {"COLUMNS": "37"}
            if columns is not None:
                environment["PRODEX_TERM_COLUMNS"] = columns
            result = subprocess.run(sandbox_command(binary, root, arguments, environment=environment),
                                    capture_output=True, timeout=10, check=False)
            if (result.returncode, result.stderr) != (0, b""):
                raise AssertionError(f"{binary.name}: exit {result.returncode}, stderr {result.stderr!r}")
            outputs.append(result.stdout)
            # Only this test's disposable fixture is removed between runs.
            shutil.rmtree(root)
        return outputs


def compare_tty(arguments, *, environment=None, change=None):
    outputs = []
    with tempfile.TemporaryDirectory(prefix="modex-session-tty-") as directory:
        for name, binary in (
            ("prodex-01651", ORACLE_01651),
            ("prodex-04392", ORACLE),
            ("modex", MODEX),
        ):
            root = Path(directory) / name
            root.mkdir()
            fixture(root)
            if change:
                change(root)
            master, slave = os.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
            try:
                result = subprocess.run(
                    sandbox_command(binary, root, arguments, environment=environment),
                    stdin=subprocess.DEVNULL, stdout=slave, stderr=subprocess.PIPE,
                    timeout=10, check=False,
                )
            finally:
                os.close(slave)
            output = bytearray()
            try:
                while True:
                    block = os.read(master, 65536)
                    if not block:
                        break
                    output.extend(block)
            except OSError as error:
                if error.errno != errno.EIO:
                    raise
            finally:
                os.close(master)
            outputs.append((
                result.returncode,
                bytes(output).replace(str(root).encode(), b"<ROOT>"),
                result.stderr.replace(str(root).encode(), b"<ROOT>"),
            ))
    return outputs


class SessionTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if (
            not ORACLE_01651.is_file()
            or hashlib.sha256(ORACLE_01651.read_bytes()).hexdigest() != SHA256_01651
        ):
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 release")

    def assert_title_batch(self, values):
        def change(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            metadata = json.loads(original.read_text().splitlines()[0])
            original.unlink()
            for index, value in enumerate(values):
                metadata["payload"]["id"] = f"glyph-{index:05}"
                metadata["payload"]["thread_name"] = value
                (original.parent / f"glyph-{index:05}.jsonl").write_text(json.dumps(metadata) + "\n")
        baseline, modex = compare_text(["session", "list"], change=change)
        expected = baseline.split(b"\nglyph-")
        actual = modex.split(b"\nglyph-")
        self.assertEqual(len(expected), len(values) + 1)
        self.assertEqual(len(actual), len(expected))
        self.assertEqual(actual[0], expected[0])
        for index, value in enumerate(values, 1):
            with self.subTest(value=value):
                self.assertEqual(actual[index], expected[index])

    def test_table_columns_truncation_and_full_ids(self):
        for columns in (None, "1", "2", "3", "4", "12", "13", "14", "22", "36",
                        "60", "79", "80", "99", "110", "111", "120", "160", "240", "300"):
            with self.subTest(columns=columns):
                baseline, modex = compare_text(["session", "list"], columns=columns)
                self.assertEqual(modex, baseline)
                self.assertFalse(baseline.endswith(b"\n"))

    def test_empty_panels_and_wrapping(self):
        for arguments in (["session", "list", "--limit", "0"],
                          ["session", "list", "--query", "missing phrase"],
                          ["session", "current", "--cwd", "./missing/path"],
                          ["session", "current", "--cwd", "/" + "long-path" * 20]):
            for columns in ("1", "3", "12", "20", "28", "40", "60", "110", "240"):
                with self.subTest(arguments=arguments, columns=columns):
                    baseline, modex = compare_text(arguments, columns=columns)
                    self.assertEqual(modex, baseline)

    def test_width_override_grammar_and_fallback(self):
        for columns in ("", "0", "-1", "+", "1_0", "bad", "18446744073709551616",
                        " \u2003+60\u3000 ", "00060", "+60", "60.0", "60 trailing"):
            with self.subTest(columns=columns):
                baseline, modex = compare_text(["session", "list"], columns=columns)
                self.assertEqual(modex, baseline)

    def test_optional_cells_multiple_rows_and_current(self):
        def change(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            metadata = json.loads(original.read_text().splitlines()[0])
            metadata["payload"]["id"] = "short-id"
            metadata["payload"].pop("thread_name")
            metadata["payload"]["cwd"] = ""
            archived = root / "home/.codex/archived_sessions"
            archived.mkdir()
            (archived / "short.jsonl").write_text(json.dumps(metadata) + "\n")
            metadata["payload"]["id"] = "another-id"
            metadata["payload"]["thread_name"] = "A very long title " * 10
            metadata["timestamp"] = "2026-10-24T03:00:00Z"
            metadata["payload"]["cwd"] = str(root / "workspace")
            (archived / "long.jsonl").write_text(json.dumps(metadata) + "\n")
        for arguments in (["session", "list"], ["session", "current"],
                          ["session", "list", "--limit", "1"]):
            with self.subTest(arguments=arguments):
                baseline, modex = compare_text(arguments, columns="160", change=change)
                self.assertEqual(modex, baseline)

    def test_unicode_titles_ids_and_cell_boundaries(self):
        titles = ("R\u00e9sum\u00e9", "Cafe\u0301", "\u754c\u9762", "\u306f\u3058\u3081\u3066",
                  "\u30ab\u30bf\u30ab\u30ca", "\ud55c\uad6d\uc5b4", "\u041f\u0440\u0438\u0432\u0435\u0442",
                  "\u0395\u03bb\u03bb\u03b7\u03bd\u03b9\u03ba\u03ac", "\u0301" * 6, "A\u00a0B", "A\u3000B")
        for title in titles:
            def change(root):
                original = next((root / "home/.codex").rglob("*.jsonl"))
                metadata = json.loads(original.read_text().splitlines()[0])
                metadata["payload"]["id"] = title * 5
                metadata["payload"]["thread_name"] = title * 8
                original.write_text(json.dumps(metadata) + "\n")
            for columns in ("22", "60", "110", "160"):
                with self.subTest(title=title, columns=columns):
                    baseline, modex = compare_text(["session", "list"], columns=columns, change=change)
                    self.assertEqual(modex, baseline)

    def test_unicode_range_edges(self):
        codes = (0xA0, 0xAD, 0xFF, 0x100, 0x2FF, 0x300, 0x34F, 0x36F,
                 0x370, 0x482, 0x483, 0x489, 0x48A, 0x52F, 0x1E00, 0x1FFF,
                 0x3000, 0x3029, 0x302A, 0x302F, 0x3030, 0x303E, 0x303F,
                 0x3041, 0x3096, 0x3099, 0x309A, 0x309B, 0x30FF, 0x31F0,
                 0x31FF, 0x3400, 0x4DBF, 0x4E00, 0x9FFF, 0xAC00, 0xD7A3,
                 0xF900, 0xFAFF, 0xFF01, 0xFF60, 0xFFE0, 0xFFE6,
                 0x20000, 0x2FFFD, 0x30000, 0x3FFFD)
        for code in codes:
            def change(root):
                original = next((root / "home/.codex").rglob("*.jsonl"))
                metadata = json.loads(original.read_text().splitlines()[0])
                value = "Prefix" + chr(code) * 12 + "Suffix"
                metadata["payload"]["id"] = value
                metadata["payload"]["thread_name"] = value
                original.write_text(json.dumps(metadata) + "\n")
            with self.subTest(code=hex(code)):
                baseline, modex = compare_text(["session", "list"], change=change)
                self.assertEqual(modex, baseline)

    def test_unicode_path_wrapping(self):
        for text in ("caf\u00e9", "\u754c\u9762", "\u306f\u3058\u3081\u3066", "\ud55c\uad6d\uc5b4",
                     "Cafe\u0301", "\u0301", "A\u00a0B", "A\u3000B", "A\tB",
                     "line\r\nnext", "line\n\nnext\n", "\u0644\u0627", "\u05d0\u200d\u05dc",
                     "\u2d4f\u2d7f\u2d3e", "\U0001f600", "\U0001f469\u200d\U0001f4bb",
                     "\U0001f44d\U0001f3fd", "1\ufe0f\u20e3"):
            arguments = ["session", "current", "--cwd", "/missing/" + text * 20]
            for columns in ("1", "8", "12", "20", "40", "60", "110"):
                with self.subTest(text=text, columns=columns):
                    baseline, modex = compare_text(arguments, columns=columns)
                    self.assertEqual(modex, baseline)

    def test_unicode_scalar_property_boundaries(self):
        east_asian = properties("EastAsianWidth.txt")
        core = properties("DerivedCoreProperties.txt")
        grapheme = properties("GraphemeBreakProperty.txt")
        codes = set(range(0xA0)) | {0x115F, 0x17A4, 0x17D8, 0x2D7F, 0xA8FA, 0x11A3A}
        for values in (east_asian["W"] | east_asian["F"], core["Default_Ignorable_Code_Point"],
                       core["Grapheme_Extend"], grapheme["V"] | grapheme["T"], grapheme["Prepend"]):
            for code in values:
                if code - 1 not in values:
                    codes.update((code - 1, code))
                if code + 1 not in values:
                    codes.update((code, code + 1))
        values = ["P" + chr(code) * 6 + "Q" for code in sorted(codes)
                  if 0 <= code <= 0x10FFFF and not 0xD800 <= code <= 0xDFFF]
        self.assert_title_batch(values)

    def test_emoji_script_ligatures_and_control_cells(self):
        values = ("\U0001f600", "\U0001f600\ufe0e", "\u2764\ufe0f", "\u2764\ufe0e",
                  "\U0001f44d\U0001f3fd", "\U0001f469\u200d\U0001f4bb", "\U0001f469\u200d\u2764\ufe0f\u200d\U0001f469",
                  "\U0001f1fa\U0001f1f8", "1\ufe0f\u20e3", "1\u20e3", "\u261d\U0001f3fb",
                  "\u0644\u0627", "\u0644\u065f\u065e\u0623", "\u0644\u200c\u0627",
                  "\u05d0\u200d\u05dc", "\u1a15\u1a17\u200d\u1a10", "\u17d2\u1780",
                  "\ua4f9\ua4fc", "\U00010c32\u200d\U00010c03", "\u2d4f\u2d7f\u2d3e",
                  "\U00016d67\U00016d67", "\U00016d63\U00016d67\U00016d67",
                  "\U00016d63", "\U00016d6a", "\u0644\ufff9\u0627", "\u2d4f\u2d7f\u2d3e\u2d7f\u2d4f",
                  "\u2018\ufe01", "\u2019\ufe00", "\u201c\ufe02", "\u115f\u1161\u11a8",
                  "\u0939\u093f\u0928\u094d\u0926\u0940", "\u0e44\u0e17\u0e22", "\u1acf", "\U0001faea",
                  "A\0B", "A\tB", "A\r\nB", "A\x1fB", "A\x7fB", "A\x85B", "A\x1b[31mB")
        for value in values:
            def change(root):
                original = next((root / "home/.codex").rglob("*.jsonl"))
                metadata = json.loads(original.read_text().splitlines()[0])
                metadata["payload"]["id"] = value * 5
                metadata["payload"]["thread_name"] = value * 8
                original.write_text(json.dumps(metadata) + "\n")
            for columns in ("22", "60", "110", "160"):
                with self.subTest(value=value, columns=columns):
                    baseline, modex = compare_text(["session", "list"], columns=columns, change=change)
                    self.assertEqual(modex, baseline)

    def test_all_short_kirat_vowel_sequences(self):
        vowels = "\U00016d63\U00016d67\U00016d68\U00016d69\U00016d6a"
        self.assert_title_batch(["P" + "".join(sequence) + "Q"
                                 for length in range(1, 6)
                                 for sequence in itertools.product(vowels, repeat=length)])

    def test_generated_unicode_width_sequences(self):
        generator = random.Random(43917)
        pools = ("\u0644\u0627\u0622\u065f\u034f\u200c\u200d\ufff9", "\u05d0\u05dc\u200d\u034f",
                 "\u1a15\u1a17\u1a10\u200d\u034f", "\u2d4f\u2d3e\u2d7f\u200d\u034f",
                 "\U00016d63\U00016d67\U00016d68\U00016d69\U00016d6a\u200d\u034f",
                 "\ua4f8\ua4fc\ua4fd\u200d\u034f", "\u17d2\u1780\u1783\u17a4\u200d\u034f",
                 "\U0001f600\U0001f469\U0001f3fb\U0001f1e6\u200d\ufe0e\ufe0f\u20e3\u2764A1")
        values = ["P" + "".join(generator.choices(pool, k=generator.randint(1, 7))) + "Q"
                  for pool in pools for _ in range(120)]
        self.assert_title_batch(values)

    def test_official_emoji_sequences_match_oracle(self):
        cases = emoji_sequence_cases()
        self.assertTrue(all(width + 2 <= 20 for _, width in cases))
        self.assert_title_batch(["P" + sequence + "Q" for sequence, _ in cases])

    def test_interactive_view_remains_explicitly_unimplemented(self):
        with tempfile.TemporaryDirectory(prefix="modex-text-tty-") as directory:
            root = Path(directory)
            fixture(root)
            master, slave = os.openpty()
            try:
                result = subprocess.run(sandbox_command(MODEX, root, ["session", "list"]),
                                        stdout=slave, stderr=subprocess.PIPE, timeout=10, check=False)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stderr, b"Error: session terminal rendering is not implemented\n")
            finally:
                os.close(slave)
                os.close(master)

    def test_ci_tty_fallback_matches_both_releases(self):
        for environment in (
            {"CODEX_CI": "1"},
            {"CODEX_CI": ""},
            {"PRODEX_TUI_STRICT": "TRUE"},
        ):
            with self.subTest(environment=environment):
                old, current, modex = compare_tty(["session", "list"], environment=environment)
                self.assertEqual(old[0:1] + old[2:3], (0, b""))
                self.assertEqual(current[0:1] + current[2:3], (0, b""))
                self.assertEqual(modex[0:1] + modex[2:3], (0, b""))
                self.assertEqual(old[1], current[1])
                self.assertEqual(modex[1], old[1])

    def test_profile_details_are_safe_on_ci_tty_fallback(self):
        controls = list(range(0x20)) + list(range(0x7F, 0xA0))
        profiles = (
            "Résumé界e\u0301 🚀",
            "Résumé界e\u0301" + "".join(map(chr, controls)) + "終🚀",
        )
        for profile in profiles:
            label = "controls" if any(
                ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F for char in profile
            ) else "unicode"
            with self.subTest(profile=label):
                def bind_profile(root):
                    state = profile_state(
                        root,
                        profile_name=profile,
                        profiles={profile: {"codex_home": "/private/CODEX_HOME_SENTINEL", "managed": False}},
                    )
                    state["active_profile"] = profile
                    write_state(root, state)

                old, current, modex = compare_tty(
                    ["session", "list"],
                    environment={"CODEX_CI": "1", "PRODEX_TERM_COLUMNS": "20"},
                    change=bind_profile,
                )
                for result in (old, current, modex):
                    self.assertEqual(result[0], 0)
                    self.assertEqual(result[2], b"")
                self.assertEqual(old[1], current[1])
                if profile == profiles[0]:
                    self.assertEqual(modex[1], old[1])
                    continue

                escaped = "Résumé界e\u0301" + "".join(f"\\x{code:02x}" for code in controls) + "終🚀"
                tty_profile = profile.replace("\n", "\r\n").encode()
                self.assertIn(tty_profile, old[1])
                self.assertEqual(modex[1], old[1].replace(tty_profile, escaped.encode()))
                profile_line = modex[1].split(b"  profile: ", 1)[1].split(b"\r\n", 1)[0]
                self.assertEqual(profile_line, escaped.encode())
                for code in controls:
                    self.assertNotIn(chr(code).encode(), profile_line)
                safe_output = modex[1].replace(b"\r\n", b"")
                for code in controls:
                    self.assertNotIn(chr(code).encode(), safe_output)

    def test_unset_and_false_tui_controls_keep_the_tty_guard(self):
        for environment in ({}, {"PRODEX_TUI_STRICT": "0"}, {"PRODEX_TUI_STRICT": "false"}):
            with self.subTest(environment=environment):
                old, current, modex = compare_tty(["session", "list"], environment=environment)
                self.assertEqual(old[0:1] + old[2:3], (0, b""))
                self.assertEqual(current[0:1] + current[2:3], (0, b""))
                self.assertEqual(old[1], current[1])
                self.assertEqual(modex, (
                    1, b"", b"Error: session terminal rendering is not implemented\n",
                ))

    def test_tty_fallback_does_not_bypass_session_state_guard(self):
        def locked_without_primary(root):
            state_root = root / "home/.prodex"
            state_root.mkdir(mode=0o700)
            (state_root / "state.json.lock").write_bytes(b"synthetic held lock marker\n")

        old, current, modex = compare_tty(
            ["session", "list"], environment={"CODEX_CI": "1"}, change=locked_without_primary,
        )
        self.assertEqual(old[0:1] + old[2:3], (0, b""))
        self.assertEqual(current[0:1] + current[2:3], (0, b""))
        self.assertEqual(modex, (
            1, b"", b"Error: locked state loading and recovery are not implemented\n",
        ))


if __name__ == "__main__":
    unittest.main()
