"""Recording mode must read disk logs without touching live broker registries."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from test_cli import MODEX, ORACLE
from test_log_stream import StreamProcess, upstream_record, runtime_record


REGISTRY = b'{"format":"inert fixture"}\n'


def run_recording_trace(binary, arguments, initial, *, token, append_data=None):
    with TemporaryDirectory(prefix="modex-recording-") as directory:
        root = Path(directory)
        runtime = root / "runtime"
        initial_bytes = b"invalid disk record\n" if append_data is not None else initial
        registry = runtime / "runtime-broker-inert.json"
        log = runtime / "prodex-runtime-primary.log"
        def prepare(_follower):
            os.chmod(runtime, 0o700)
            if append_data is None: registry.write_bytes(REGISTRY)

        follower = StreamProcess(binary, "json", root, b"", initial_bytes, arguments=arguments,
                                 prepare=prepare,
                                 environment={"PRODEX_RUNTIME_LOG_RECORD": token,
                                              "PRODEX_HOME": str(runtime)})
        try:
            if append_data is not None:
                follower.require_marker("Waiting for transcript, upstream payload, or token events."
                                        if "upstream" not in arguments else
                                        "Waiting for processed upstream payload events.")
                registry.write_bytes(REGISTRY)
                with log.open("ab") as stream:
                    stream.write(append_data)
                follower.require_marker("recording-follow-marker")
            else:
                follower.require_marker("recording-initial-marker")
                follower.require_quiet(0.2)
            output = follower.stop()
            return output, registry.read_bytes(), sorted(path.name for path in runtime.iterdir())
        finally:
            follower.stop()


class RecordingLogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_cli
        test_cli.CliTests.setUpClass()

    def test_recorded_files_bypass_preexisting_and_new_registries(self):
        cases = (
            (["log"], "stream", "1"),
            (["log", "stream", "--json"], "stream", "yes"),
            (["log", "stream"], "stream", "on"),
            (["log", "upstream", "--json"], "upstream", "\u00a0TrUe\u00a0"),
            (["log", "upstream"], "upstream", "1"),
        )
        for arguments, mode, token in cases:
            with self.subTest(arguments=arguments, token=token):
                line = (runtime_record("stream_payload", {"source": "disk", "stream": "recording-initial-marker"},
                                       "2026-10-24T01:02:03Z") if mode == "stream" else
                        upstream_record("recording-initial-marker"))
                expected = run_recording_trace(ORACLE, arguments, line, token=token)
                actual = run_recording_trace(MODEX, arguments, line, token=token)
                self.assertEqual(actual, expected)
                self.assertEqual(actual[1], REGISTRY)
                self.assertEqual(actual[2], ["prodex-runtime-primary.log", "runtime-broker-inert.json"])

                appended = (runtime_record("stream_payload", {"source": "disk", "stream": "recording-follow-marker"},
                                           "2026-10-24T01:02:04Z") if mode == "stream" else
                            upstream_record("recording-follow-marker", "2026-10-24T01:02:04Z"))
                expected = run_recording_trace(ORACLE, arguments, b"", token=token,
                                               append_data=appended)
                actual = run_recording_trace(MODEX, arguments, b"", token=token,
                                             append_data=appended)
                self.assertEqual(actual, expected)
                self.assertEqual(actual[1], REGISTRY)
                self.assertEqual(actual[2], ["prodex-runtime-primary.log", "runtime-broker-inert.json"])

    def test_disabled_or_absent_recording_keeps_unsupported_live_guard(self):
        for token in (None, " false "):
            with self.subTest(token=token):
                with TemporaryDirectory(prefix="modex-recording-disabled-") as directory:
                    root = Path(directory)
                    runtime = root / "runtime"
                    registry = runtime / "runtime-broker-inert.json"

                    def prepare(_follower):
                        os.chmod(runtime, 0o700)
                        registry.write_bytes(REGISTRY)

                    environment = {"PRODEX_HOME": str(runtime)}
                    if token is not None:
                        environment["PRODEX_RUNTIME_LOG_RECORD"] = token
                    follower = StreamProcess(
                        MODEX, "json", root, b"", b"invalid disk record\n",
                        arguments=["log", "stream", "--json"], prepare=prepare,
                        environment=environment,
                    )
                    try:
                        follower.collect(2.0)
                        output = follower.stop()
                        self.assertEqual(follower.process.returncode, 1)
                        self.assertIn(b"live runtime log sources are not implemented",
                                      output["stderr"])
                        self.assertEqual(registry.read_bytes(), REGISTRY)
                        self.assertEqual(sorted(path.name for path in runtime.iterdir()),
                                         ["prodex-runtime-primary.log", "runtime-broker-inert.json"])
                    finally:
                        follower.stop()


if __name__ == "__main__":
    unittest.main()
