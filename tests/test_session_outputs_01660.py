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

    def test_invalid_zstd_magic_prefix_diagnostics_match_release(self):
        cases = (
            (b"x", "Unknown frame descriptor"),
            (b"\x28\x00", "Unknown frame descriptor"),
            (b"\x28", "incomplete frame"),
            (b"\x28\xb5\x2f", "incomplete frame"),
            (b"\x28\xb5\x2f\xfd\x20", "incomplete frame"),
            (b"\x50", "incomplete frame"),
        )
        for encoded, detail in cases:
            with self.subTest(encoded=encoded):
                observations = []
                for binary, argv0 in ((ORACLE, "prodex"), (MODEX, "modex")):
                    with tempfile.TemporaryDirectory(prefix="modex-session-zstd-prefix-") as directory:
                        root = Path(directory)
                        test_sessions.fixture(root)
                        session = next((root / "home/.codex").rglob("*.jsonl"))
                        session.unlink()
                        corrupt = session.with_name("rollout-invalid.jsonl.zst")
                        corrupt.write_bytes(encoded)
                        result = subprocess.run(
                            test_sessions.sandbox_command(
                                binary, root, ["session", "list", "--json"],
                                timezone="UTC", argv0=argv0,
                            ),
                            stdin=subprocess.DEVNULL, capture_output=True, timeout=10, check=False,
                        )
                        self.assertEqual(corrupt.read_bytes(), encoded)
                        observations.append((
                            result.returncode,
                            result.stdout.replace(str(root).encode(), b"<FIXTURE_ROOT>"),
                            result.stderr.replace(str(root).encode(), b"<FIXTURE_ROOT>"),
                        ))
                expected = (
                    1, b"",
                    ("Error: failed to read session <FIXTURE_ROOT>/home/.codex/sessions/2026/10/24/"
                     f"rollout-invalid.jsonl.zst: {detail}\n").encode(),
                )
                self.assertEqual(observations, [expected, expected])

    def test_noncanonical_huffman_rejection_and_compressed_frame_controls(self):
        encoded = (Path(__file__).parent / "fixtures/zstd-noncanonical-huffman.zst").read_bytes()
        overfull_data = b"{}\n"
        overfull = (
            b"\x28\xb5\x2f\xfd\xa0" + (2).to_bytes(4, "little")
            + ((len(overfull_data) << 3 | 1).to_bytes(3, "little")) + overfull_data
        )
        truncated = zstd.compress(
            b'{"type":"session_meta","payload":{"id":"synthetic"}}\n',
            options={zstd.CompressionParameter.checksum_flag: 1},
        )[:-1]
        cases = (
            ("noncanonical", encoded, "stream did not contain valid UTF-8", "Data corruption detected"),
            ("truncated-checksum", truncated, "incomplete frame", "incomplete frame"),
            ("overfull", overfull, "Data corruption detected", "Data corruption detected"),
        )
        for name, data, release_error, modex_error in cases:
            observations = []
            for binary, argv0, detail in (
                (ORACLE, "prodex", release_error), (MODEX, "modex", modex_error),
            ):
                with tempfile.TemporaryDirectory(prefix="modex-session-zstd-control-") as directory:
                    root = Path(directory)
                    test_sessions.fixture(root)
                    session = next((root / "home/.codex").rglob("*.jsonl"))
                    session.unlink()
                    compressed = session.with_name("rollout-" + name + ".jsonl.zst")
                    compressed.write_bytes(data)
                    result = subprocess.run(
                        test_sessions.sandbox_command(
                            binary, root, ["session", "list", "--json"],
                            timezone="UTC", argv0=argv0,
                        ),
                        stdin=subprocess.DEVNULL, capture_output=True, timeout=10, check=False,
                    )
                    self.assertEqual(compressed.read_bytes(), data)
                    observations.append((
                        result.returncode,
                        result.stdout.replace(str(root).encode(), b"<FIXTURE_ROOT>"),
                        result.stderr.replace(str(root).encode(), b"<FIXTURE_ROOT>"),
                    ))
            expected_release = (1, b"", (
                "Error: failed to read session <FIXTURE_ROOT>/home/.codex/sessions/2026/10/24/"
                f"rollout-{name}.jsonl.zst: {release_error}\n"
            ).encode())
            self.assertEqual(observations[0], expected_release)
            expected_modex = (1, b"", (
                "Error: failed to read session <FIXTURE_ROOT>/home/.codex/sessions/2026/10/24/"
                f"rollout-{name}.jsonl.zst: {modex_error}\n"
            ).encode())
            self.assertEqual(observations[1], expected_modex)

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

    def test_equal_timestamp_reports_order_by_id_then_path(self):
        rows = (
            ("019a1234-5678-7123-8123-012345678903", "same", "same-late-path"),
            ("019a1234-5678-7123-8123-012345678901", "same", "same-early-path"),
            ("019a1234-5678-7123-8123-012345678902", "a", "ascii-first"),
            ("019a1234-5678-7123-8123-012345678904", "z", "ascii-last"),
            ("019a1234-5678-7123-8123-012345678905", "雪", "unicode-last"),
            ("019a1234-5678-7123-8123-012345678906", "é", "unicode-middle"),
        )

        def change(root):
            directory = root / "home/.codex/sessions/2026/10/24"
            next(directory.glob("*.jsonl")).unlink()
            for identifier_in_path, identifier, thread_name in rows:
                path = directory / f"rollout-{identifier_in_path}.jsonl"
                record = {
                    "timestamp": "2026-10-24T02:00:00Z",
                    "type": "session_meta",
                    "payload": {"id": identifier, "thread_name": thread_name},
                }
                path.write_text(json.dumps(record, ensure_ascii=False) + "\n")

        reports = self.assert_outputs(["session", "list", "--json"], change)
        self.assertEqual(
            [(report["id"], report["thread_name"]) for report in reports],
            [("a", "ascii-first"), ("same", "same-early-path"),
             ("same", "same-late-path"), ("z", "ascii-last"),
             ("é", "unicode-middle"), ("雪", "unicode-last")],
        )
        self.assertEqual(
            [Path(report["path"]).name for report in reports if report["id"] == "same"],
            [f"rollout-{rows[1][0]}.jsonl", f"rollout-{rows[0][0]}.jsonl"],
        )

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

    def test_plain_table_escapes_terminal_controls_in_untrusted_title(self):
        title = "\x1b[31mN\nX"
        outputs = {}
        for label, binary, argv0 in (
            ("oracle", ORACLE, "prodex"),
            ("modex", MODEX, "modex"),
        ):
            with tempfile.TemporaryDirectory(prefix="modex-session-table-controls-") as directory:
                root = Path(directory)
                (root / "home").mkdir(mode=0o700)
                (root / "workspace").mkdir()
                session = root / "home/.codex/sessions/2026/10/24/rollout-synthetic.jsonl"
                session.parent.mkdir(parents=True)
                session.write_text(json.dumps({
                    "timestamp": "2026-10-24T01:02:03Z",
                    "type": "session_meta",
                    "payload": {"id": "synthetic-id", "thread_name": title},
                }) + "\n")
                before = session.read_bytes()
                result = subprocess.run(
                    test_sessions.sandbox_command(
                        binary,
                        root,
                        ["session", "list"],
                        argv0=argv0,
                        environment={"PRODEX_TERM_COLUMNS": "120"},
                    ),
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                self.assertEqual(session.read_bytes(), before)
                outputs[label] = result.stdout.replace(str(root).encode(), b"<FIXTURE_ROOT>")

        self.assertIn(b"\x1b[31mN\nX", outputs["oracle"])
        self.assertIn(b"\\x1b[31mN\\x0aX", outputs["modex"])
        self.assertNotIn(b"\x1b", outputs["modex"])
