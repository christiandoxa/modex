"""Black-box comparisons for the detached general log stream."""

import base64
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import tempfile
import time
import unittest

from session_oracle import sandbox_command
import test_cli
from test_cli import MODEX, ORACLE


def runtime_record(event, fields, timestamp):
    return json.dumps({"timestamp": timestamp, "event": event, "fields": fields},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def upstream_record(marker, timestamp="2026-10-24T01:02:04Z"):
    payload = marker.encode("utf-8")
    return runtime_record("upstream_payload", {
        "request": "7", "transport": "http", "route": "responses", "profile": "main",
        "bytes": str(len(payload)), "logged_bytes": str(len(payload)), "truncated": "false",
        "payload_b64": base64.b64encode(payload).decode("ascii"),
    }, timestamp)


def token_record(timestamp="2026-10-24T01:02:05Z"):
    return runtime_record("token_usage", {
        "request": "7", "transport": "http", "profile": "main", "source": "responses",
        "input_tokens": "12", "cached_input_tokens": "3", "output_tokens": "4",
        "reasoning_tokens": "1",
    }, timestamp)


def session_record(timestamp, message):
    return json.dumps({"timestamp": timestamp, "type": "event_msg", "payload": {
        "type": "user_message", "message": message,
    }}, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def session_context_record(timestamp="2026-10-24T01:00:07Z"):
    return json.dumps({"timestamp": timestamp, "type": "session_meta", "payload": {
        "base_instructions": {"text": "synthetic prompt marker"},
        "model_provider": "synthetic-provider",
    }}, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


class StreamProcess:
    def __init__(self, binary, mode, root, session_bytes, runtime_bytes, *, arguments=None,
                 prepare=None, nofile=None):
        self.root = root
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        self.runtime = root / "runtime"
        self.runtime.mkdir()
        self.log = self.runtime / "prodex-runtime-primary.log"
        self.log.write_bytes(runtime_bytes)
        self.session = root / "home/.codex/sessions/2026/10/24/rollout-fixture.jsonl"
        self.session.parent.mkdir(parents=True)
        self.session.write_bytes(session_bytes)
        if prepare is not None:
            prepare(self)
        arguments = arguments if arguments is not None else (
            ["log", "stream"] + (["--json"] if mode == "json" else [])
        )
        command = sandbox_command(
            binary,
            root,
            arguments,
            argv0="prodex" if binary == ORACLE else "modex",
            environment={"TZ": "UTC", "PRODEX_RUNTIME_LOG_DIR": str(self.runtime)},
        )
        preexec_fn = None
        if nofile is not None:
            def set_nofile_limit():
                resource.setrlimit(resource.RLIMIT_NOFILE, (nofile, nofile))
            preexec_fn = set_nofile_limit
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            preexec_fn=preexec_fn,
        )
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ, "stdout")
        self.selector.register(self.process.stderr, selectors.EVENT_READ, "stderr")
        self.output = {"stdout": bytearray(), "stderr": bytearray()}
        self.stopped = False

    def collect(self, timeout, marker=None):
        start = {stream: len(data) for stream, data in self.output.items()}
        marker_bytes = marker.encode("utf-8") if isinstance(marker, str) else marker
        deadline = time.monotonic() + timeout
        found = marker_bytes is None
        quiet_deadline = None
        while time.monotonic() < deadline:
            for key, _ in self.selector.select(min(0.1, max(0.0, deadline - time.monotonic()))):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if chunk:
                    self.output[key.data].extend(chunk)
                else:
                    self.selector.unregister(key.fileobj)
            if marker_bytes is not None and not found:
                found = any(marker_bytes in data[start[name]:]
                            for name, data in self.output.items())
                if found:
                    quiet_deadline = time.monotonic() + 0.15
            if found and quiet_deadline is not None and time.monotonic() >= quiet_deadline:
                break
            if found and marker_bytes is None and not self.selector.get_map():
                break
        return {name: bytes(data[start[name]:]) for name, data in self.output.items()}

    def require_marker(self, marker, timeout=5):
        return self.require_markers((marker,), timeout)

    def require_markers(self, markers, timeout=5):
        markers = tuple(marker.encode("utf-8") for marker in markers)
        result = self.collect(timeout, markers[-1])
        merged = result["stdout"] + result["stderr"]
        missing = [marker for marker in markers if marker not in merged]
        if missing:
            raise AssertionError(f"log stream did not emit {missing!r}: {result!r}")
        if self.process.poll() is not None:
            raise AssertionError(f"log stream exited early: {self.process.returncode}")
        return result

    def require_quiet(self, duration):
        result = self.collect(duration)
        if result["stdout"] or result["stderr"]:
            raise AssertionError(f"log stream emitted unexpected output: {result!r}")
        if self.process.poll() is not None:
            raise AssertionError(f"log stream exited early: {self.process.returncode}")

    def stop(self):
        if self.stopped:
            return {name: bytes(data) for name, data in self.output.items()}
        self.stopped = True
        try:
            if self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait(timeout=2)
            self.collect(0.5)
            return {name: bytes(data) for name, data in self.output.items()}
        finally:
            self.selector.close()
            self.process.stdout.close()
            self.process.stderr.close()


def run_trace(binary, mode, session_bytes, runtime_bytes, scenario, *, arguments=None,
              prepare=None, nofile=None):
    with tempfile.TemporaryDirectory(prefix="modex-log-stream-") as directory:
        follower = StreamProcess(binary, mode, Path(directory), session_bytes, runtime_bytes,
                                 arguments=arguments, prepare=prepare, nofile=nofile)
        try:
            scenario(follower)
            if follower.process.poll() is not None:
                raise AssertionError(f"log stream exited: {follower.process.returncode}")
            return follower.stop()
        finally:
            follower.stop()


class LogStreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def assert_matches_oracle(self, mode, session_bytes, runtime_bytes, scenario, *, arguments=None):
        expected = run_trace(ORACLE, mode, session_bytes, runtime_bytes, scenario,
                             arguments=arguments)
        actual = run_trace(MODEX, mode, session_bytes, runtime_bytes, scenario,
                           arguments=arguments)
        self.assertEqual(actual, expected)
        return expected

    def test_initial_snapshot_order_and_empty_waiting_message(self):
        session = json.dumps({"timestamp": "2026-10-24T01:00:00Z", "type": "session_meta",
                              "payload": {"id": "fixture", "cwd": "/workspace"}}).encode() + b"\n"
        session += session_record("2026-10-24T01:00:01Z", "transcript-marker")
        runtime = runtime_record("stream_payload", {"source": "fixture-stream", "stream": "stream-marker"},
                                 "2026-10-24T01:00:02Z")
        runtime += upstream_record("upstream-marker", "2026-10-24T01:00:03Z")
        runtime += token_record("2026-10-24T01:00:04Z")

        def snapshot(follower):
            follower.require_markers(("transcript-marker", "stream-marker", "upstream-marker",
                                      '"event":"token_usage"'))
            follower.require_quiet(0.2)

        expected = self.assert_matches_oracle("json", session, runtime, snapshot)
        events = [json.loads(line) for line in expected["stdout"].splitlines()]
        self.assertEqual([events[0]["source"], events[1]["source"]], ["user", "fixture-stream"])
        self.assertIn("payload", events[2])
        self.assertNotIn("event", events[2])
        self.assertEqual(events[3]["event"], "token_usage")
        self.assertEqual(events[3]["source"], "responses")

        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                def empty(follower):
                    follower.require_marker("Waiting for transcript, upstream payload, or token events.")
                    follower.require_quiet(0.2)

                expected = self.assert_matches_oracle(mode, b"", b"invalid runtime line\n", empty)
                self.assertEqual(expected["stdout"], b"")
                self.assertEqual(expected["stderr"],
                                 b"Waiting for transcript, upstream payload, or token events.\n")

    def test_default_stream_and_option_before_mode_wait_and_follow(self):
        cases = (
            (["log"], "plain"),
            (["log", "--json"], "json"),
            (["log", "--json", "stream"], "json"),
        )
        runtime = b"invalid runtime line\n"
        appended = runtime_record("stream_payload", {
            "source": "argument-order-source", "stream": "argument-order-live-marker",
        }, "2026-10-24T01:02:03Z")
        for arguments, mode in cases:
            with self.subTest(arguments=arguments):
                def follow(follower):
                    follower.require_marker("Waiting for transcript, upstream payload, or token events.")
                    follower.require_quiet(2.2)  # Allow the documented runtime path reconciliation interval.
                    with follower.log.open("ab") as stream:
                        stream.write(appended)
                    follower.require_marker("argument-order-live-marker")
                    follower.require_quiet(0.2)

                expected = self.assert_matches_oracle(
                    mode, b"", runtime, follow, arguments=arguments,
                )
                self.assertEqual(expected["stderr"],
                                 b"Waiting for transcript, upstream payload, or token events.\n")
                self.assertIn(b"argument-order-live-marker", expected["stdout"])

    def test_runtime_and_session_appends_follow_existing_paths(self):
        session = json.dumps({"timestamp": "2026-10-24T01:00:00Z", "type": "session_meta",
                              "payload": {"id": "fixture", "cwd": "/workspace"}}).encode() + b"\n"
        session += session_record("2026-10-24T01:00:01Z", "initial-transcript")
        runtime = runtime_record("stream_payload", {"source": "fixture-stream", "stream": "initial-runtime"},
                                 "2026-10-24T01:00:02Z")

        def follow(follower):
            follower.require_markers(("initial-transcript", "initial-runtime"))
            follower.require_quiet(2.2)  # Allow the documented runtime path reconciliation interval.

            partial = runtime_record("stream_payload", {
                "source": "fixture-stream", "stream": "append-café-marker",
            }, "2026-10-24T01:00:03Z")[:-1]
            split = partial.index(b"\xc3\xa9") + 1
            with follower.log.open("ab") as stream:
                stream.write(partial[:split])
            follower.require_quiet(0.2)
            with follower.log.open("ab") as stream:
                stream.write(partial[split:] + b"\n" + upstream_record("append-upstream-marker") + token_record())
            follower.require_markers(("append-café-marker", "append-upstream-marker",
                                      '"event":"token_usage"'))

            context = session_context_record()
            with follower.session.open("ab") as stream:
                stream.write(context)
            follower.require_markers(("synthetic prompt marker", "synthetic-provider"), timeout=3)
            follower.require_quiet(0.2)
            with follower.session.open("ab") as stream:
                stream.write(context)
            follower.require_markers(("synthetic prompt marker", "synthetic-provider"), timeout=3)
            follower.require_quiet(0.2)

            with follower.session.open("ab") as stream:
                stream.write(session_record("2026-10-24T01:00:08Z", "append-session-marker"))
            follower.require_marker("append-session-marker", timeout=3)
            follower.require_quiet(0.2)

            duplicate = session_record("2026-10-24T01:00:09Z", "same-batch-duplicate-marker")
            with follower.session.open("ab") as stream:
                stream.write(duplicate + duplicate)
            follower.require_marker("same-batch-duplicate-marker", timeout=3)
            follower.require_quiet(0.2)

        expected = self.assert_matches_oracle("json", session, runtime, follow)
        lines = [json.loads(line) for line in expected["stdout"].splitlines()]
        values = [json.dumps(line, ensure_ascii=False) for line in lines]
        self.assertTrue(any("append-café-marker" in line for line in values))
        self.assertTrue(any("append-session-marker" in line for line in values))
        self.assertEqual(sum("same-batch-duplicate-marker" in line for line in values), 1)
        self.assertEqual(sum("synthetic prompt marker" in line for line in values), 2)
        self.assertEqual(sum("synthetic-provider" in line for line in values), 2)

    def test_operational_routine_load_suppression_and_error_output(self):
        fields = {
            "request": "17", "profile": "fixture", "route": "responses", "lane": "responses",
            "transport": "http", "context": "fresh", "provider": "openai", "model": "fixture",
            "limit": "8", "hard_limit": "16", "reason": "busy-marker",
        }
        routine_load = runtime_record("profile_inflight_saturated", fields,
                                      "2026-10-24T01:02:03Z")
        overload = runtime_record("runtime_proxy_queue_overloaded", fields,
                                  "2026-10-24T01:02:04Z")

        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                def follow(follower):
                    follower.require_marker("Waiting for transcript, upstream payload, or token events.")
                    follower.require_quiet(2.2)  # Allow the documented runtime path reconciliation interval.
                    with follower.log.open("ab") as stream:
                        stream.write(routine_load)
                    if mode == "json":
                        follower.require_marker("busy-marker")
                        follower.require_quiet(0.2)
                    else:
                        follower.require_quiet(0.3)
                    with follower.log.open("ab") as stream:
                        stream.write(overload)
                    follower.require_marker("busy-marker")
                    follower.require_quiet(0.2)

                expected = self.assert_matches_oracle(mode, b"", b"invalid runtime line\n", follow)
                if mode == "json":
                    events = [json.loads(line) for line in expected["stdout"].splitlines()]
                    self.assertEqual([event["source"] for event in events], ["load", "error"])
                else:
                    self.assertNotIn(b"profile busy", expected["stdout"])
                    self.assertIn(b"ERROR", expected["stdout"])


if __name__ == "__main__":
    unittest.main()
