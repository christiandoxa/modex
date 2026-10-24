"""Output-focused differential checks; full side-effect parity is tracked separately."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import SESSION_ID, fixture, sandbox_command
import test_cli
from test_cli import MODEX, ORACLE


def normalize_output(data, root, arguments, *, modex=False):
    if "--json" in arguments:
        reports = json.loads(data)
        for report in reports:
            for field in ("cwd", "path"):
                value = report.get(field)
                if value and value.startswith(str(root) + "/"):
                    report[field] = "<FIXTURE_ROOT>" + value[len(str(root)):]
        # Only fixture-root paths change; field order, whitespace and Unicode stay checked.
        original = json.loads(data)
        expected_raw = json.dumps(original, ensure_ascii=False, indent=2) + "\n"
        if data.decode() != expected_raw:
            raise AssertionError("JSON output does not match baseline pretty serialization")
        return reports
    if "--resume-command" in arguments and modex:
        return b"\n".join(b"prodex run " + line[len(b"modex run "):]
                           if line.startswith(b"modex run ") else line
                           for line in data.split(b"\n"))
    return data


def compare_outputs(arguments, change=None):
    with tempfile.TemporaryDirectory(prefix="modex-session-pair-") as directory:
        parent = Path(directory)
        observations = []
        for name, binary in (("baseline", ORACLE), ("modex", MODEX)):
            root = parent / name
            root.mkdir()
            fixture(root)
            if change:
                change(root)
            result = subprocess.run(sandbox_command(binary, root, arguments),
                                    capture_output=True, timeout=10, check=False)
            if result.returncode != 0:
                raise AssertionError(f"{name} exited {result.returncode}: {result.stderr!r}")
            if result.stderr:
                raise AssertionError(f"{name} wrote unexpected stderr: {result.stderr!r}")
            observations.append(normalize_output(result.stdout, root, arguments, modex=name == "modex"))
        return observations


class SessionOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def assert_outputs(self, arguments, change=None):
        baseline, modex = compare_outputs(arguments, change)
        self.assertEqual(modex, baseline)
        return baseline

    def test_populated_json(self):
        reports = self.assert_outputs(["session", "list", "--json"])
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["id"], SESSION_ID)

    def test_filters_limits_and_machine_output_modes(self):
        for arguments in (
            ["session", "list", "--json", "--limit", "0"],
            ["session", "list", "--json", "--limit", "18446744073709551615"],
            ["session", "list", "--json", "--profile", "missing"],
            ["session", "list", "--json", "--query", "SESSION FIXTURE"],
            ["session", "list", "--json", "--query", "absent phrase"],
            ["session", "current", "--json"],
            ["session", "current", "--json", "--cwd", "/elsewhere"],
            ["session", "list", "--id-only"],
            ["session", "list", "--resume-command"],
            ["session", "list", "--json", "--include-subagents"],
            ["session", "list", "--json", "--parent-only"],
        ):
            with self.subTest(arguments=arguments):
                self.assert_outputs(arguments)

    def test_json_file_and_metadata_precedence(self):
        def change(root):
            session = next((root / "home/.codex").rglob("*.jsonl"))
            metadata = json.loads(session.read_text().splitlines()[0])
            metadata["payload"]["title"] = "Wrong title"
            metadata["thread_name"] = "Wrong root name"
            metadata["payload"]["thread_name"] = "Résumé CHECK"
            metadata["payload"]["metadata"] = {"cwd": "/wrong-directory"}
            session.unlink()
            session.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        reports = self.assert_outputs(["session", "list", "--json", "--query", "résumé"], change)
        self.assertEqual(reports[0]["thread_name"], "Résumé CHECK")

    def test_archived_children_and_newest_first_ordering(self):
        def change(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            metadata = json.loads(original.read_text().splitlines()[0])
            metadata["payload"]["id"] = "child-session"
            metadata["payload"]["source"] = {"subagent": {"thread_spawn": {"parent_thread_id": SESSION_ID}}}
            metadata["timestamp"] = "2026-10-24T03:00:00+01:00"
            archived = root / "home/.codex/archived_sessions"
            archived.mkdir()
            (archived / "child.jsonl").write_text(json.dumps(metadata) + "\n")
        reports = self.assert_outputs(["session", "list", "--json"], change)
        self.assertEqual([report["id"] for report in reports], ["child-session", SESSION_ID])
        self.assert_outputs(["session", "list", "--json", "--parent-only"], change)

    def test_malformed_records_and_symlinks(self):
        def change(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            original.write_text("\n\n" + original.read_text() + "{bad json}\n")
            (original.parent / "invalid.jsonl").write_text("{bad json}\n" + original.read_text())
            (original.parent / "link.jsonl").symlink_to(original)
        self.assert_outputs(["session", "list", "--json"], change)

    def test_unicode_whitespace_and_blank_string_fallbacks(self):
        def change(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            metadata = json.loads(original.read_text().splitlines()[0])
            metadata["payload"]["thread_name"] = "\u2000\u00a0"
            metadata["payload"]["title"] = "\u2000Trimmed title\u00a0"
            original.write_text(json.dumps(metadata) + "\n")
        reports = self.assert_outputs(["session", "list", "--json"], change)
        self.assertEqual(reports[0]["thread_name"], "Trimmed title")

    def test_unicode_prefix_on_first_metadata_record_is_not_accepted(self):
        def change(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            original.write_text("\u2000" + original.read_text())
        self.assertEqual(self.assert_outputs(["session", "list", "--json"], change), [])

    def test_nonobject_followup_records_do_not_crash_modex(self):
        # Safe behavior differs from a baseline panic; this is not a parity PASS.
        with tempfile.TemporaryDirectory(prefix="modex-session-scalar-") as directory:
            root = Path(directory)
            fixture(root)
            original = next((root / "home/.codex").rglob("*.jsonl"))
            original.write_text(original.read_text() + "[]\nnull\n")
            result = subprocess.run(sandbox_command(MODEX, root, ["session", "list", "--json"]),
                                    capture_output=True, timeout=10, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)[0]["id"], SESSION_ID)


if __name__ == "__main__":
    unittest.main()
