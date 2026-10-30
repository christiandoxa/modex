"""Selected session output comparisons against the active 0.166.0 release."""

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from compression import zstd

import test_sessions
from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256


class SessionOutputs01660Tests(test_sessions.SessionOutputTests):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 Linux release")

    def assert_outputs(self, arguments, change=None, *, timezone="UTC"):
        baseline, modex = test_sessions.compare_outputs(
            arguments, change, timezone=timezone, reference=ORACLE,
        )
        self.assertEqual(modex, baseline)
        return baseline

    def test_pre_epoch_file_time_falls_back_to_unix_epoch(self):
        for format_name in ("json", "jsonl", "jsonl.zst"):
            for mtime_ns in (-1_000_000_000, -1, 0):
                for timestamp in (None, "2026-01-02T03:04:05Z"):
                    def change(root):
                        session = next((root / "home/.codex").rglob("*.jsonl"))
                        metadata = json.loads(session.read_text().splitlines()[0])
                        metadata.pop("timestamp", None)
                        metadata["payload"].pop("timestamp", None)
                        if timestamp is not None:
                            metadata["timestamp"] = timestamp
                        encoded = (json.dumps(metadata) + "\n").encode()
                        if format_name == "json":
                            session.unlink()
                            session = session.with_suffix(".json")
                        elif format_name == "jsonl.zst":
                            session.unlink()
                            session = session.with_name(session.name + ".zst")
                            encoded = zstd.compress(encoded)
                        session.write_bytes(encoded)
                        os.utime(session, ns=(mtime_ns, mtime_ns))
                        self.assertEqual(session.stat().st_mtime_ns, mtime_ns)

                    with self.subTest(format=format_name, mtime_ns=mtime_ns, timestamp=timestamp):
                        reports = self.assert_outputs(["session", "list", "--json"], change)
                        self.assertEqual(len(reports), 1)
                        self.assertEqual(reports[0]["updated_at"],
                                         timestamp or "1970-01-01 00:00:00 +00:00")

    def test_invalid_utf8_json_diagnostics_and_jsonl_controls(self):
        sentinel = b"synthetic-private-session-content"
        cases = (
            ("invalid-leading-byte", lambda raw: b"\xff" + raw,
             "invalid utf-8 sequence of 1 bytes from index 0"),
            ("bad-second-continuation", lambda raw: raw[:80] + b"\xe2(\xa1" + raw[80:],
             "invalid utf-8 sequence of 1 bytes from index 80"),
            ("bad-third-continuation", lambda raw: raw[:80] + b"\xe2\x82(" + raw[80:],
             "invalid utf-8 sequence of 2 bytes from index 80"),
            ("overlong-e0", lambda raw: raw[:80] + b"\xe0\x80\x80" + raw[80:],
             "invalid utf-8 sequence of 1 bytes from index 80"),
            ("surrogate-ed", lambda raw: raw[:80] + b"\xed\xa0\x80" + raw[80:],
             "invalid utf-8 sequence of 1 bytes from index 80"),
            ("out-of-range-f4", lambda raw: raw[:80] + b"\xf4\x90\x80\x80" + raw[80:],
             "invalid utf-8 sequence of 1 bytes from index 80"),
            ("truncated-multibyte", lambda raw: raw + b"\xf0\x9f\x92", None),
        )
        for suffix in ("json", "jsonl"):
            for case, corrupt, expected in cases:
                with self.subTest(format=suffix, case=case), tempfile.TemporaryDirectory(
                    prefix="modex-session-invalid-utf8-"
                ) as directory:
                    parent = Path(directory)
                    observations = []
                    # Equal root-name lengths keep byte offsets comparable.
                    for name, binary, argv0 in (
                        ("oracle", ORACLE, "prodex"), ("modexx", MODEX, "modex")
                    ):
                        root = parent / name
                        root.mkdir()
                        test_sessions.fixture(root)
                        session = next((root / "home/.codex").rglob("*.jsonl"))
                        raw = session.read_bytes().replace(b"Session fixture", sentinel)
                        if suffix == "json":
                            session.unlink()
                            session = session.with_suffix(".json")
                        content = corrupt(raw)
                        session.write_bytes(content)
                        result = subprocess.run(
                            test_sessions.sandbox_command(
                                binary, root, ["session", "list", "--json"], argv0=argv0,
                            ),
                            stdin=subprocess.DEVNULL, capture_output=True,
                            timeout=10, check=False,
                        )
                        self.assertEqual(session.read_bytes(), content)
                        self.assertNotIn(sentinel, result.stdout + result.stderr)
                        observations.append((
                            result.returncode, result.stdout,
                            result.stderr.replace(str(root).encode(), b"<FIXTURE_ROOT>"),
                        ))
                    self.assertEqual(observations[0], observations[1])
                    path = (
                        "<FIXTURE_ROOT>/home/.codex/sessions/2026/10/24/rollout-"
                        + test_sessions.SESSION_ID + "." + suffix
                    )
                    if suffix == "json":
                        detail = expected or (
                            "incomplete utf-8 byte sequence from index "
                            + str(len(raw))
                        )
                        stderr = f"Error: failed to decode session {path}: {detail}\n".encode()
                    else:
                        stderr = (
                            f"Error: failed to read session {path}: "
                            "stream did not contain valid UTF-8\n"
                        ).encode()
                    self.assertEqual(observations[0], (1, b"", stderr))

    def test_valid_unicode_json_and_jsonl_controls(self):
        for suffix in ("json", "jsonl"):
            def change(root):
                session = next((root / "home/.codex").rglob("*.jsonl"))
                lines = session.read_text().splitlines()
                metadata = json.loads(lines[0])
                metadata["payload"]["thread_name"] = "Session 雪"
                if suffix == "json":
                    session.unlink()
                    session = session.with_suffix(".json")
                    content = json.dumps(metadata, ensure_ascii=False) + "\n"
                else:
                    content = "\n".join(
                        [json.dumps(metadata, ensure_ascii=False), *lines[1:]]
                    ) + "\n"
                session.write_text(content)

            with self.subTest(format=suffix):
                reports = self.assert_outputs(["session", "list", "--json"], change)
                self.assertEqual(reports[0]["thread_name"], "Session 雪")

    def test_invalid_json_path_controls_are_escaped(self):
        for label, binary in (("oracle", ORACLE), ("modex", MODEX)):
            with self.subTest(binary=label), tempfile.TemporaryDirectory(
                prefix="modex-session-path-controls-"
            ) as directory:
                root = Path(directory)
                test_sessions.fixture(root)
                session = next((root / "home/.codex").rglob("*.jsonl"))
                session.unlink()
                session = session.parent / "synthetic\x1b[31m.json"
                session.write_bytes(b"\xff")
                result = subprocess.run(
                    test_sessions.sandbox_command(binary, root, ["session", "list", "--json"]),
                    stdin=subprocess.DEVNULL, capture_output=True, timeout=10, check=False,
                )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(session.read_bytes(), b"\xff")
                if label == "oracle":
                    self.assertIn(b"\x1b[31m", result.stderr)
                else:
                    self.assertNotIn(b"\x1b", result.stderr)
                    self.assertIn(b"\\x1b[31m", result.stderr)
