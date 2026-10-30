"""Compare large session text behavior with the checksum-verified 0.439.2 release."""

import json
import shutil
import tempfile
from pathlib import Path
import subprocess
import unittest

import test_cli
import test_text_memory
from session_oracle import fixture, sandbox_command


MIB = 1024 * 1024
SESSION_LINE_LIMIT = 64 * MIB


def _set_title(path, title):
    records = path.read_text().splitlines()
    metadata = json.loads(records[0])
    metadata["payload"]["thread_name"] = title
    path.write_text(json.dumps(metadata, ensure_ascii=False) + "\n" + "\n".join(records[1:]) + "\n")


class SessionTextMemoryParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_large_mixed_title_output_matches_checksum_verified_oracle(self):
        title = test_text_memory.MIXED * 100_000

        def change(root):
            path = next((root / "home/.codex").rglob("*.jsonl"))
            _set_title(path, title)

        with tempfile.TemporaryDirectory(prefix="modex-large-title-") as directory:
            root = Path(directory) / "fixture"
            outputs = []
            for binary in (test_cli.ORACLE, test_cli.MODEX):
                root.mkdir()
                fixture(root)
                change(root)
                command = sandbox_command(binary, root, ["session", "list"],
                                          environment={"PRODEX_TERM_COLUMNS": "110"})
                result = subprocess.run(command, capture_output=True, timeout=120, check=False)
                outputs.append((result.returncode, result.stdout, result.stderr))
                shutil.rmtree(root)
            self.assertEqual(outputs[0], outputs[1])

    def test_session_line_limit_and_overflow_match_oracle(self):
        with tempfile.TemporaryDirectory(prefix="modex-session-line-boundary-") as directory:
            root = Path(directory) / "fixture"
            for line_size in (SESSION_LINE_LIMIT, SESSION_LINE_LIMIT + 1):
                outputs = []
                for binary in (test_cli.ORACLE, test_cli.MODEX):
                    root.mkdir()
                    fixture(root)
                    path = next((root / "home/.codex").rglob("*.jsonl"))
                    records = path.read_text().splitlines()
                    metadata = json.loads(records[0])
                    metadata["payload"]["thread_name"] = ""
                    empty = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
                    title_size = line_size - len(empty) - 1
                    metadata["payload"]["thread_name"] = "x" * title_size
                    header = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
                    self.assertEqual(len(header) + 1, line_size)
                    path.write_bytes(header + b"\n" + records[1].encode() + b"\n")
                    command = sandbox_command(binary, root, ["session", "list"],
                                              environment={"PRODEX_TERM_COLUMNS": "110"})
                    result = subprocess.run(command, capture_output=True, timeout=300, check=False)
                    outputs.append((result.returncode, result.stdout, result.stderr))
                    shutil.rmtree(root)
                self.assertEqual(outputs[0], outputs[1], f"line size {line_size}")
                self.assertEqual(outputs[0][0] == 0, line_size == SESSION_LINE_LIMIT,
                                 f"baseline behavior at line size {line_size}")
