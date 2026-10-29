"""Differential coverage for malformed UTF-8 session and state names."""

import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile
import unittest

import test_cli
from session_oracle import SESSION_ID, fixture, sandbox_command


ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
DEEP_SESSION_ID = "019a1234-5678-7123-8123-1123456789ab"
ARCHIVED_SESSION_ID = "019a1234-5678-7123-8123-2123456789ab"


def add_empty_file(directory, name):
    descriptor = os.open(directory + b"/" + name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)


def add_session(directory, identifier, thread_name, workspace):
    timestamp = "2026-10-24T00:00:00Z"
    record = {"timestamp": timestamp, "type": "session_meta", "payload": {
        "id": identifier,
        "timestamp": timestamp,
        "cwd": str(workspace),
        "thread_name": thread_name,
        "model_provider": "openai",
    }}
    path = directory + b"/rollout-" + identifier.encode() + b".jsonl"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as session:
        session.write((json.dumps(record, ensure_ascii=False) + "\n").encode())


def add_invalid_entries(root):
    workspace = fixture(root)
    app_root = root / "home/.prodex"
    app_root.mkdir(mode=0o700)
    add_empty_file(os.fsencode(app_root), b"\x80-root")
    add_empty_file(os.fsencode(app_root), b"state.json.\x80.tmp")

    sessions = root / "home/.codex/sessions"
    date = sessions / "2026/10/24"
    archived = root / "home/.codex/archived_sessions"
    archived.mkdir()
    sessions_bytes = os.fsencode(sessions)
    date_bytes = os.fsencode(date)
    archived_bytes = os.fsencode(archived)

    add_empty_file(sessions_bytes, b"\x80.jsonl")
    add_empty_file(date_bytes, b"\xff.jsonl")
    add_empty_file(archived_bytes, b"\xc3(.jsonl")

    tie_z = date_bytes + b"/\x80z"
    tie_a = date_bytes + b"/\xffa"
    os.mkdir(tie_z, 0o700)
    os.mkdir(tie_a, 0o700)
    add_session(tie_z, SESSION_ID, "tie-z", workspace)
    add_session(tie_a, SESSION_ID, "tie-a", workspace)

    deep = date_bytes + b"/\xc3("
    os.mkdir(deep, 0o700)
    deeper = deep + b"/\xff"
    os.mkdir(deeper, 0o700)
    add_session(deeper, DEEP_SESSION_ID, "deep", workspace)

    archive_dir = archived_bytes + b"/\x80"
    os.mkdir(archive_dir, 0o700)
    add_session(archive_dir, ARCHIVED_SESSION_ID, "archived-deep", workspace)

    valid_file = date_bytes + b"/rollout-" + SESSION_ID.encode() + b".jsonl"
    os.symlink(valid_file, date_bytes + b"/file-link.jsonl")
    os.symlink(tie_z, date_bytes + b"/directory-link")
    return app_root


def disable_core_dumps():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run(binary, root, arguments, argv0):
    return subprocess.run(
        sandbox_command(
            binary,
            root,
            arguments,
            argv0=argv0,
            environment={"PRODEX_HOME": str(root / "home/.prodex")},
        ),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=10,
        check=False,
        preexec_fn=disable_core_dumps,
    )


def normalize_reports(output, root):
    reports = json.loads(output)
    for report in reports:
        for field in ("cwd", "path"):
            value = report.get(field)
            if value and value.startswith(str(root) + "/"):
                report[field] = "<FIXTURE_ROOT>" + value[len(str(root)):]
    return reports


class SessionInvalidUtf8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if not ORACLE_01651.is_file():
            raise AssertionError(f"Pinned Prodex 0.165.1 oracle is missing: {ORACLE_01651}")
        if hashlib.sha256(ORACLE_01651.read_bytes()).hexdigest() != ORACLE_01651_SHA256:
            raise AssertionError("The Prodex oracle does not match pinned release 0.165.1")

    def test_invalid_session_entries_match_releases_and_queries(self):
        commands = (
            ("prodex-01651", ORACLE_01651, "prodex"),
            ("prodex-04392", test_cli.ORACLE, "prodex"),
            ("modex", test_cli.MODEX, "modex"),
        )
        arguments = (
            ["session", "list", "--json"],
            ["session", "list", "--query", "�", "--id-only"],
            ["session", "list", "--query", "�(", "--id-only"],
        )
        observations = {}
        with tempfile.TemporaryDirectory(prefix="modex-session-invalid-utf8-") as directory:
            parent = Path(directory)
            for name, binary, argv0 in commands:
                root = parent / name
                root.mkdir()
                app_root = add_invalid_entries(root)
                results = [run(binary, root, argv, argv0) for argv in arguments]
                for result in results:
                    self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                    self.assertEqual(result.stderr, b"")
                self.assertTrue(os.path.lexists(
                    os.fsencode(app_root) + b"/state.json.\x80.tmp"
                ))
                observations[name] = (
                    normalize_reports(results[0].stdout, root),
                    results[1].stdout,
                    results[2].stdout,
                )

        self.assertEqual(observations["modex"], observations["prodex-04392"])
        self.assertEqual(observations["modex"], observations["prodex-01651"])
        reports = observations["modex"][0]
        duplicate_id_reports = [report for report in reports if report["id"] == SESSION_ID]
        self.assertEqual([report["thread_name"] for report in duplicate_id_reports], [
            "Session fixture", "tie-a", "tie-z",
        ])
        self.assertEqual(observations["modex"][1], (
            f"{SESSION_ID}\n{SESSION_ID}\n{DEEP_SESSION_ID}\n{ARCHIVED_SESSION_ID}\n"
        ).encode())
        self.assertEqual(observations["modex"][2], f"{DEEP_SESSION_ID}\n".encode())

    def test_malformed_root_names_do_not_bypass_state_guards(self):
        for protected_name in (
            b"state.json.lock",
            b"profile-lifecycle-journal",
            b"state.json.123.456.0.tmp",
        ):
            with self.subTest(protected_name=protected_name):
                with tempfile.TemporaryDirectory(prefix="modex-state-guard-") as directory:
                    root = Path(directory)
                    fixture(root)
                    app_root = root / "home/.prodex"
                    app_root.mkdir(mode=0o700)
                    app_bytes = os.fsencode(app_root)
                    add_empty_file(app_bytes, b"\x80-root")
                    add_empty_file(app_bytes, b"state.json.\x80.tmp")
                    if protected_name == b"profile-lifecycle-journal":
                        os.mkdir(app_bytes + b"/" + protected_name, 0o700)
                    else:
                        add_empty_file(app_bytes, protected_name)
                    result = run(test_cli.MODEX, root, ["session", "list", "--json"], "modex")
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(
                        b"locked state loading and recovery are not implemented",
                        result.stderr,
                    )


if __name__ == "__main__":
    unittest.main()
