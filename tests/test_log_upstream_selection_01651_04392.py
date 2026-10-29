"""Compare upstream event selection with both pinned release processes."""

import base64
import subprocess
import tempfile
from pathlib import Path
import unittest

from session_oracle import sandbox_command
from test_cli import MODEX
from test_log_stream import run_trace, runtime_record
import test_log_stream_escaped_event_01651_04392 as escaped_test


def record(marker, event="upstream_payload", literal=False, escaped=False, timestamp="2026-10-24T01:02:03Z"):
    fields = {"payload_b64": base64.b64encode(marker.encode()).decode()}
    if literal:
        fields["note"] = "upstream_payload"
    line = runtime_record(event, fields, timestamp)
    if escaped:
        line = line.replace(b'"event":"upstream_payload"', b'"event":"upstream\\u005fpayload"')
    return line


def last(binary, mode, contents):
    with tempfile.TemporaryDirectory(prefix="modex-upstream-selection-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        runtime = root / "runtime"
        runtime.mkdir()
        (runtime / "prodex-runtime-primary.log").write_bytes(contents)
        args = ["log", "last"] + (["--json"] if mode == "json" else [])
        result = subprocess.run(sandbox_command(binary, root, args, argv0="modex" if binary == MODEX else "prodex",
                                environment={"TZ": "UTC", "PRODEX_RUNTIME_LOG_DIR": str(runtime)}),
                                capture_output=True, timeout=10, check=False)
        return result.returncode, result.stdout, result.stderr


class UpstreamSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        escaped_test.LogStreamEscapedEventTests.setUpClass()
        cls.binaries = escaped_test.LogStreamEscapedEventTests.binaries

    def test_event_type_and_raw_filter_in_last_and_followers(self):
        rejected = record("escaped-rejected", escaped=True)
        wrong = record("wrong-event", event="synthetic", literal=True)
        accepted = record("escaped-accepted", literal=True, escaped=True)
        normal = record("normal-marker", timestamp="2026-10-24T01:02:04Z")
        for mode in ("json", "plain"):
            for contents in (rejected, wrong, accepted, normal):
                results = [last(binary, mode, contents) for binary in self.binaries]
                with self.subTest(mode=mode, last=contents):
                    self.assertEqual(results[1:], results[:1] * 2)
            for command in ("stream", "upstream"):
                args = ["log", command] + (["--json"] if mode == "json" else [])
                initial = [run_trace(binary, mode, b"", accepted,
                                     lambda follower: follower.require_marker("escaped-accepted"),
                                     arguments=args) for binary in self.binaries]
                self.assertEqual(initial[1:], initial[:1] * 2)
                def follow(follower):
                    follower.require_marker("Waiting for")
                    follower.require_quiet(2.2)
                    with follower.log.open("ab") as stream:
                        stream.write(rejected + wrong + accepted + normal)
                    follower.require_markers(("escaped-accepted", "normal-marker"))
                traces = []
                for binary in self.binaries:
                    trace = run_trace(binary, mode, b"", rejected + wrong, follow, arguments=args)
                    self.assertNotIn(b"escaped-rejected", trace["stdout"] + trace["stderr"])
                    self.assertNotIn(b"wrong-event", trace["stdout"] + trace["stderr"])
                    traces.append(trace)
                with self.subTest(mode=mode, command=command):
                    self.assertEqual(traces[1:], traces[:1] * 2)


if __name__ == "__main__":
    unittest.main()
