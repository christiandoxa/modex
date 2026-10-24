"""Compare unmodified plain session output in identical disposable homes."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from session_oracle import fixture, sandbox_command
import test_cli
from test_cli import MODEX, ORACLE


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


class SessionTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

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
                     "line\r\nnext", "line\n\nnext\n"):
            arguments = ["session", "current", "--cwd", "/missing/" + text * 20]
            for columns in ("1", "8", "12", "20", "40", "60", "110"):
                with self.subTest(text=text, columns=columns):
                    baseline, modex = compare_text(arguments, columns=columns)
                    self.assertEqual(modex, baseline)

    def test_unimplemented_cell_widths_fail_explicitly(self):
        # Development checks for known gaps; these do not establish baseline parity.
        for title in ("Emoji title \U0001f600", "Control\tcharacter"):
            with self.subTest(title=title), tempfile.TemporaryDirectory(prefix="modex-text-gap-") as directory:
                root = Path(directory)
                fixture(root)
                original = next((root / "home/.codex").rglob("*.jsonl"))
                metadata = json.loads(original.read_text().splitlines()[0])
                metadata["payload"]["thread_name"] = title
                original.write_text(json.dumps(metadata) + "\n")
                result = subprocess.run(sandbox_command(MODEX, root, ["session", "list"]),
                                        capture_output=True, timeout=10, check=False)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"Unicode or control character is not implemented", result.stderr)

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


if __name__ == "__main__":
    unittest.main()
