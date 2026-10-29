"""Compare raw stream-payload event selection across the pinned releases."""

import hashlib
import os
from pathlib import Path
import unittest

from test_cli import MODEX
from test_log_stream import run_trace, runtime_record


ORACLES = (
    ("PRODEX_ORACLE_01651", "0.165.1", "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"),
    ("PRODEX_ORACLE_04392", "0.439.2", "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"),
)


def escaped_record(source, text):
    return runtime_record("stream_payload", {"source": source, "stream": text},
                          "2026-10-24T01:02:03Z").replace(b'"event":"stream_payload"', b'"event":"stream\\u005fpayload"')


class LogStreamEscapedEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binaries = []
        for environment, version, checksum in ORACLES:
            path = Path(os.environ.get(environment, Path.home() / f".cache/modex/oracles/{version}/prodex-x86_64-unknown-linux-gnu"))
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
                raise AssertionError(f"{environment} must identify pinned Prodex {version}: {path}")
            cls.binaries.append(path)
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        cls.binaries.append(MODEX)

    def test_escaped_event_raw_filter_matches_initial_and_followed_records(self):
        rejected = escaped_record("synthetic-source", "omitted-marker")
        accepted = escaped_record("literal-stream_payload-source", "accepted-marker")
        normal = runtime_record("stream_payload", {"source": "fixture", "stream": "normal-marker"},
                                "2026-10-24T01:02:04Z")
        self.assertNotIn(b"stream_payload", rejected)
        self.assertIn(b"stream_payload", accepted)
        for mode in ("json", "plain"):
            traces = []
            initial_traces = []
            for binary in self.binaries:
                with self.subTest(mode=mode, binary=binary):
                    initial_traces.append(run_trace(
                        binary, mode, b"", accepted,
                        lambda follower: follower.require_marker("accepted-marker"),
                    ))
                    def follow(follower):
                        follower.require_marker("Waiting for transcript, upstream payload, or token events.")
                        follower.require_quiet(2.2)
                        with follower.log.open("ab") as stream:
                            stream.write(rejected + accepted + normal)
                        follower.require_markers(("accepted-marker", "normal-marker"))

                    trace = run_trace(binary, mode, b"", rejected, follow)
                    self.assertNotIn(b"omitted-marker", trace["stdout"] + trace["stderr"])
                    traces.append(trace)
            self.assertEqual(initial_traces[1:], initial_traces[:1] * 2)
            self.assertEqual(traces[1:], traces[:1] * 2)


if __name__ == "__main__":
    unittest.main()
