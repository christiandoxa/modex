"""Multiprocess oracle coverage for detached upstream log following."""

import base64
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import tempfile
import time
import unittest

from session_oracle import sandbox_command
import test_cli
from test_cli import MODEX, ORACLE


def upstream_record(marker, *, timestamp="2026-10-24T01:02:03Z", profile="main"):
    payload = marker.encode("utf-8")
    record = {
        "timestamp": timestamp,
        "event": "upstream_payload",
        "fields": {
            "request": "7",
            "transport": "http",
            "route": "responses",
            "profile": profile,
            "bytes": str(len(payload)),
            "logged_bytes": str(len(payload)),
            "truncated": "false",
            "payload_b64": base64.b64encode(payload).decode("ascii"),
        },
    }
    return json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


class UpstreamProcess:
    def __init__(self, binary, mode, root, initial_log):
        self.root = root
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        (root / ".prodex").mkdir(mode=0o700)
        self.runtime = root / "runtime"
        self.runtime.mkdir()
        self.log = self.runtime / "prodex-runtime-primary.log"
        self.log.write_bytes(initial_log)
        arguments = ["log", "upstream"] + ([] if mode == "plain" else ["--json"])
        command = sandbox_command(
            binary,
            root,
            arguments,
            argv0="prodex" if binary == ORACLE else "modex",
            environment={"TZ": "UTC", "PRODEX_RUNTIME_LOG_DIR": str(self.runtime)},
        )
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ, "stdout")
        self.selector.register(self.process.stderr, selectors.EVENT_READ, "stderr")
        self.output = {"stdout": bytearray(), "stderr": bytearray()}

    def collect(self, timeout, marker=None):
        start = {stream: len(data) for stream, data in self.output.items()}
        deadline = time.monotonic() + timeout
        marker_bytes = marker.encode() if isinstance(marker, str) else marker
        found = marker_bytes is None
        quiet_after_marker = None
        while time.monotonic() < deadline:
            for key, _ in self.selector.select(min(0.1, max(0.0, deadline - time.monotonic()))):
                data = os.read(key.fileobj.fileno(), 65536)
                if data:
                    self.output[key.data].extend(data)
                else:
                    self.selector.unregister(key.fileobj)
            if marker_bytes is not None and not found:
                found = marker_bytes in self.output["stdout"][start["stdout"]:] or marker_bytes in self.output["stderr"][start["stderr"]:]
                if found:
                    quiet_after_marker = time.monotonic() + 0.15
            if found and quiet_after_marker is not None and time.monotonic() >= quiet_after_marker:
                break
            if found and marker_bytes is None and not self.selector.get_map():
                break
        return {stream: bytes(data[start[stream]:]) for stream, data in self.output.items()}

    def require_marker(self, marker, timeout=5):
        result = self.collect(timeout, marker)
        merged = result["stdout"] + result["stderr"]
        if marker.encode() not in merged:
            raise AssertionError(f"upstream follower did not emit {marker!r}: {result!r}")
        if self.process.poll() is not None:
            raise AssertionError(f"upstream follower exited early: {self.process.returncode}")
        return result

    def require_quiet(self, duration):
        result = self.collect(duration)
        if result["stdout"] or result["stderr"]:
            raise AssertionError(f"upstream follower emitted before a complete event: {result!r}")
        if self.process.poll() is not None:
            raise AssertionError(f"upstream follower exited early: {self.process.returncode}")
        return result

    def stop(self):
        try:
            if self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait(timeout=2)
            return self.process.returncode
        finally:
            self.selector.close()
            self.process.stdout.close()
            self.process.stderr.close()

    def wait_for_exit(self, timeout):
        deadline = time.monotonic() + timeout
        while self.process.poll() is None and time.monotonic() < deadline:
            self.collect(min(0.1, deadline - time.monotonic()))
        if self.process.poll() is None:
            raise AssertionError("upstream follower did not exit after its tracked path became invalid")
        self.collect(0.1)
        return self.process.returncode, bytes(self.output["stdout"]), bytes(self.output["stderr"])


def run_trace(binary, mode, initial_log, scenario):
    with tempfile.TemporaryDirectory(prefix="modex-upstream-follow-") as directory:
        follower = UpstreamProcess(binary, mode, Path(directory), initial_log)
        try:
            trace = scenario(follower)
            if follower.process.poll() is not None:
                raise AssertionError(f"upstream follower exited: {follower.process.returncode}")
            return trace
        finally:
            follower.stop()


class LogUpstreamFollowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def assert_matches_oracle(self, mode, initial_log, scenario):
        expected = run_trace(ORACLE, mode, initial_log, scenario)
        actual = run_trace(MODEX, mode, initial_log, scenario)
        self.assertEqual(actual, expected)
        return expected

    def test_initial_latest_event_and_empty_waiting_message(self):
        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                def latest(follower):
                    initial = follower.require_marker("latest-marker")
                    follower.require_quiet(0.25)
                    self.assertNotIn(b"older-marker", initial["stdout"])
                    return [initial]

                lines = upstream_record("older-marker", timestamp="2026-10-24T01:02:02Z")
                lines += upstream_record("latest-marker", timestamp="2026-10-24T01:02:03Z")
                self.assert_matches_oracle(mode, lines, latest)

                def empty(follower):
                    initial = follower.require_marker("Waiting for processed upstream payload events...")
                    follower.require_quiet(0.25)
                    return [initial]

                self.assert_matches_oracle(mode, b"not an upstream event\n", empty)

    def test_append_and_partial_line_delivery(self):
        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                def scenario(follower):
                    initial = follower.require_marker("Waiting for processed upstream payload events...")
                    follower.require_quiet(2.2)  # Allow the documented two-second path reconciliation.
                    with follower.log.open("ab") as stream:
                        stream.write(upstream_record("append-marker"))
                    appended = follower.require_marker("append-marker")

                    partial = upstream_record("partial-marker")[:-1]
                    cut = len(partial) // 2
                    with follower.log.open("ab") as stream:
                        stream.write(partial[:cut])
                    follower.require_quiet(0.3)
                    with follower.log.open("ab") as stream:
                        stream.write(partial[cut:] + b"\n")
                    completed = follower.require_marker("partial-marker")
                    return [initial, appended, completed]

                self.assert_matches_oracle(mode, b"not an upstream event\n", scenario)

    def test_split_utf8_waits_for_complete_line(self):
        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                def scenario(follower):
                    initial = follower.require_marker("Waiting for processed upstream payload events...")
                    follower.require_quiet(2.2)
                    line = upstream_record("café-utf8-marker", profile="météor")[:-1]
                    split = line.index(b"\xc3\xa9") + 1
                    with follower.log.open("ab") as stream:
                        stream.write(line[:split])
                    follower.require_quiet(0.3)
                    with follower.log.open("ab") as stream:
                        stream.write(line[split:] + b"\n")
                    complete = follower.require_marker("café-utf8-marker")
                    return [initial, complete]

                self.assert_matches_oracle(mode, b"not an upstream event\n", scenario)

    def test_truncation_and_rotation_reopen_followed_file(self):
        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                def scenario(follower):
                    initial = follower.require_marker("initial-marker")
                    follower.require_quiet(2.2)
                    long_line = b"x" * 512 + b"\n"
                    with follower.log.open("ab") as stream:
                        stream.write(long_line + upstream_record("before-truncate"))
                    before = follower.require_marker("before-truncate")
                    with follower.log.open("wb") as stream:
                        stream.write(upstream_record("after-truncate"))
                    truncated = follower.require_marker("after-truncate")

                    rotated = follower.log.with_suffix(".old")
                    replacement = follower.log.with_suffix(".new")
                    replacement.write_bytes(upstream_record("after-rotation"))
                    os.link(follower.log, rotated)
                    os.replace(replacement, follower.log)
                    rotated_output = follower.require_marker("after-rotation")
                    return [initial, before, truncated, rotated_output]

                self.assert_matches_oracle(mode, upstream_record("initial-marker"), scenario)

    def test_missing_path_before_replacement_skips_initial_record_like_release(self):
        def scenario(follower):
            initial = follower.require_marker("initial-marker")
            follower.require_quiet(0.25)
            os.replace(follower.log, follower.log.with_suffix(".old"))
            follower.require_quiet(0.5)
            follower.log.write_bytes(upstream_record("after-rotation"))
            follower.require_quiet(0.5)
            with follower.log.open("ab") as stream:
                stream.write(upstream_record("after-append"))
            appended = follower.require_marker("after-append")
            self.assertNotIn(b"after-rotation", appended["stdout"] + appended["stderr"])
            return [initial, appended]

        self.assert_matches_oracle("json", upstream_record("initial-marker"), scenario)

    def test_new_log_file_is_followed_after_reconciliation(self):
        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                def scenario(follower):
                    initial = follower.require_marker("Waiting for processed upstream payload events...")
                    follower.require_quiet(2.2)
                    second = follower.runtime / "prodex-runtime-new.log"
                    second.write_bytes(b"")
                    follower.require_quiet(2.2)
                    with second.open("ab") as stream:
                        stream.write(upstream_record("new-file-marker"))
                    new_file = follower.require_marker("new-file-marker")
                    return [initial, new_file]

                self.assert_matches_oracle(mode, b"not an upstream event\n", scenario)

    def test_invalid_parent_of_tracked_log_exits_with_inspect_error(self):
        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                def run(binary):
                    with tempfile.TemporaryDirectory(prefix="modex-upstream-path-error-") as directory:
                        root = Path(directory)
                        follower = UpstreamProcess(binary, mode, root, upstream_record("initial-marker"))
                        try:
                            initial = follower.require_marker("initial-marker")
                            follower.require_quiet(2.2)
                            with follower.log.open("ab") as stream:
                                stream.write(upstream_record("tracked-marker", timestamp="2026-10-24T01:02:04Z"))
                            appended = follower.require_marker("tracked-marker")
                            old_runtime = follower.runtime.with_name("runtime-old")
                            os.replace(follower.runtime, old_runtime)
                            follower.runtime.write_text("replacement file\n")
                            exit_code, stdout, stderr = follower.wait_for_exit(2)
                            self.assertEqual(exit_code, 1)
                            root_bytes = str(root).encode()
                            return (
                                initial["stdout"].replace(root_bytes, b"<fixture-root>"),
                                initial["stderr"].replace(root_bytes, b"<fixture-root>"),
                                appended["stdout"].replace(root_bytes, b"<fixture-root>"),
                                appended["stderr"].replace(root_bytes, b"<fixture-root>"),
                                stdout.replace(root_bytes, b"<fixture-root>"),
                                stderr.replace(root_bytes, b"<fixture-root>"),
                            )
                        finally:
                            follower.stop()

                self.assertEqual(run(MODEX), run(ORACLE))


if __name__ == "__main__":
    unittest.main()
