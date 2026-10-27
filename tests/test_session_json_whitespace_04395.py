"""Compare single-object JSON session fallback with the pinned release."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_cli
from session_oracle import SESSION_ID, sandbox_command


def observe(binary, argv0, extension, content, arguments):
    with tempfile.TemporaryDirectory(prefix="modex-session-json-whitespace-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        sessions = root / "home/.codex/sessions/2026/10/24"
        sessions.mkdir(parents=True)
        (sessions / f"rollout-{SESSION_ID}{extension}").write_text(content)
        return subprocess.run(
            sandbox_command(binary, root, ["session", "list", *arguments], argv0=argv0),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10,
            check=False,
        )


class SessionJsonWhitespace04395Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_json_line_fallback_trims_unicode_outer_whitespace(self):
        content = json.dumps({"type": "session_meta", "payload": {"id": SESSION_ID}})
        for label, wrapper in (("leading", "\u2000" + content),
                               ("trailing", content + "\u2000")):
            with self.subTest(label=label):
                outputs = []
                for name, binary, argv0 in (("baseline", test_cli.ORACLE, "prodex"),
                                             ("modex", test_cli.MODEX, "modex")):
                    result = observe(binary, argv0, ".json", wrapper, ["--id-only"])
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    self.assertEqual(result.stderr, b"")
                    outputs.append(result.stdout)

                self.assertEqual(outputs[0], (SESSION_ID + "\n").encode())
                self.assertEqual(outputs[1], outputs[0])

    def test_json_jsonl_whitespace_and_malformed_controls(self):
        metadata = json.dumps({"type": "session_meta", "payload": {
            "id": SESSION_ID, "thread_name": " Left\u2000Center "}})
        update = json.dumps({"type": "event_msg", "payload": {"thread_name": "UpdatedName"}})
        cases = (
            ("JSON ASCII outer whitespace", ".json", " \t" + metadata + "\r\n", ["--id-only"],
             (SESSION_ID + "\n").encode()),
            ("JSONL ASCII outer whitespace", ".jsonl", " \t" + metadata + " \r\n", ["--id-only"],
             (SESSION_ID + "\n").encode()),
            ("JSONL Unicode first-line whitespace stays strict", ".jsonl",
             "\u2000" + metadata + "\u2000\n", ["--id-only"], b""),
            ("JSONL Unicode later-line whitespace is trimmed", ".jsonl",
             metadata + "\n\u2000" + update + "\u2000\n",
             ["--query", "updatedname", "--id-only"], (SESSION_ID + "\n").encode()),
            ("JSON multiline fallback trims and skips malformed followup", ".json",
             metadata + "\n{bad json}\n\u2000" + update + "\u2000\n",
             ["--query", "updatedname", "--id-only"], (SESSION_ID + "\n").encode()),
            ("JSON internal string whitespace is preserved", ".json", metadata,
             ["--query", "left\u2000center", "--id-only"], (SESSION_ID + "\n").encode()),
            ("JSON internal whitespace is not removed", ".json", metadata,
             ["--query", "leftcenter", "--id-only"], b""),
            ("JSON BOM remains invalid", ".json", "\ufeff" + metadata, ["--id-only"], b""),
            ("JSONL BOM remains invalid", ".jsonl", "\ufeff" + metadata + "\n", ["--id-only"], b""),
            ("JSON malformed first line remains invalid", ".json",
             "{bad json}\n" + metadata, ["--id-only"], b""),
            ("JSONL malformed first line remains invalid", ".jsonl",
             "{bad json}\n" + metadata, ["--id-only"], b""),
        )
        for label, extension, content, arguments, expected in cases:
            with self.subTest(label=label):
                outputs = []
                for binary, argv0 in ((test_cli.ORACLE, "prodex"), (test_cli.MODEX, "modex")):
                    result = observe(binary, argv0, extension, content, arguments)
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    self.assertEqual(result.stderr, b"")
                    outputs.append(result.stdout)

                self.assertEqual(outputs, [expected, expected])


if __name__ == "__main__":
    unittest.main()
