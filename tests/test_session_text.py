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

    def test_unimplemented_cell_widths_fail_explicitly(self):
        # Development checks for known gaps; these do not establish baseline parity.
        for title in ("Unicode title \u754c", "Control\tcharacter"):
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
                self.assertIn(b"Unicode or control characters is not implemented", result.stderr)

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
