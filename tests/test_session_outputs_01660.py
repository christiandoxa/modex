"""Selected session output comparisons against the active 0.166.0 release."""

import hashlib
import json
import os
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
