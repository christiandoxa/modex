"""Check log follower TTY routing with isolated runtime-log fixtures."""

import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pty
import selectors
import signal
import struct
import subprocess
import tempfile
import termios
import time
import unittest

from session_oracle import sandbox_command
import test_cli
from test_cli import MODEX


ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
))
MARKER = "fixture-terminal-marker"


def _append_output(selector, output, timeout):
    for key, _ in selector.select(timeout):
        try:
            data = os.read(key.fd, 65536)
        except OSError:
            data = b""
        if data:
            output[key.data].extend(data)
        else:
            selector.unregister(key.fileobj)


def run_log(binary, mode, tty_names, *, no_color=True, controlling=False, live_registry=False):
    with tempfile.TemporaryDirectory(prefix="modex-log-tty-") as directory:
        root = Path(directory)
        home = root / "home"
        home.mkdir(mode=0o700)
        (root / "workspace").mkdir()
        prodex_home = home / ".prodex"
        prodex_home.mkdir(mode=0o700)
        if live_registry:
            (prodex_home / "runtime-broker-fixture.json").write_text("{}\n")
        runtime = root / "runtime"
        runtime.mkdir()
        payload = MARKER.encode()
        record = {
            "timestamp": "2026-10-24T01:02:03Z",
            "event": "upstream_payload",
            "fields": {
                "request": "7",
                "transport": "http",
                "route": "responses",
                "profile": "synthetic",
                "bytes": str(len(payload)),
                "logged_bytes": str(len(payload)),
                "truncated": "false",
                "payload_b64": base64.b64encode(payload).decode("ascii"),
            },
        }
        (runtime / "prodex-runtime-fixture.log").write_text(json.dumps(record) + "\n")
        environment = {
            "PRODEX_HOME": str(prodex_home),
            "PRODEX_RUNTIME_LOG_DIR": str(runtime),
            "TERM": "xterm-256color",
            "TZ": "UTC",
        }
        if no_color:
            environment["NO_COLOR"] = "1"
        command = sandbox_command(
            binary, root, ["log", mode],
            argv0="prodex" if binary != MODEX else "modex",
            environment=environment,
        )
        if controlling:
            command.remove("--new-session")
            no_color_index = command.index("NO_COLOR")
            del command[no_color_index - 1:no_color_index + 2]

        master, slave = pty.openpty()
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 120, 0, 0))
        stdin = slave if "stdin" in tty_names else subprocess.DEVNULL
        stdout = slave if "stdout" in tty_names else subprocess.PIPE
        stderr = slave if "stderr" in tty_names else subprocess.PIPE

        def acquire_controlling_terminal():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        process = subprocess.Popen(
            command,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            preexec_fn=acquire_controlling_terminal if controlling else None,
            bufsize=0,
        )
        os.close(slave)
        selector = selectors.DefaultSelector()
        output = {"stdout": bytearray(), "stderr": bytearray(), "tty": bytearray()}
        if stdout == subprocess.PIPE:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        if stderr == subprocess.PIPE:
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        if "stdout" in tty_names or "stderr" in tty_names:
            selector.register(master, selectors.EVENT_READ, "tty")
        marker = MARKER.encode()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and marker not in b"".join(output.values()) and process.poll() is None:
            _append_output(selector, output, 0.1)

        if process.poll() is None and marker in b"".join(output.values()) and controlling:
            os.write(master, b"q")
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=2)
        elif process.poll() is None:
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=2)

        deadline = time.monotonic() + 0.3
        while selector.get_map() and time.monotonic() < deadline:
            _append_output(selector, output, 0.05)
        selector.close()
        os.close(master)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        return process.returncode, bytes(output["stdout"]), bytes(output["stderr"]), bytes(output["tty"])


class LogTtyFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary, checksum in ((ORACLE_01651, ORACLE_01651_SHA256),
                                 (ORACLE, test_cli.ORACLE_SHA256)):
            if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != checksum:
                raise AssertionError(f"Invalid pinned Prodex oracle: {binary}")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")

    def test_plain_follower_matches_both_releases_for_non_tui_tty_combinations(self):
        combinations = (
            ("stderr only without NO_COLOR", {"stderr"}, False),
            ("stdout only without NO_COLOR", {"stdout"}, False),
            ("stdin only without NO_COLOR", {"stdin"}, False),
            ("stdin and stdout with NO_COLOR", {"stdin", "stdout"}, True),
        )
        for mode in ("stream", "upstream"):
            for label, tty_names, no_color in combinations:
                with self.subTest(mode=mode, combination=label):
                    expected = run_log(ORACLE_01651, mode, tty_names, no_color=no_color)
                    current = run_log(ORACLE, mode, tty_names, no_color=no_color)
                    actual = run_log(MODEX, mode, tty_names, no_color=no_color)
                    self.assertEqual(expected, current)
                    self.assertEqual(actual, expected)
                    self.assertEqual(expected[0], -signal.SIGTERM)
                    self.assertIn(MARKER.encode(), b"".join(expected[1:]))

    def test_interactive_release_tui_stays_guarded_and_quits_cleanly(self):
        for mode, error in (
            ("stream", b"Error: log stream terminal rendering is not implemented"),
            ("upstream", b"Error: upstream terminal rendering is not implemented"),
        ):
            with self.subTest(mode=mode):
                for oracle in (ORACLE_01651, ORACLE):
                    result = run_log(
                        oracle, mode, {"stdin", "stdout"}, no_color=False, controlling=True,
                    )
                    self.assertEqual(result[0], 0)
                    self.assertIn(MARKER.encode(), result[3])
                    for sequence in (b"\x1b[?1049h", b"\x1b[?25l", b"\x1b[?25h", b"\x1b[?1049l"):
                        self.assertIn(sequence, result[3])

                modex = run_log(
                    MODEX, mode, {"stdin", "stdout"}, no_color=False, controlling=True,
                )
                self.assertEqual(modex[0], 1)
                self.assertEqual(modex[1], b"")
                self.assertIn(error, modex[2])

    def test_plain_tty_fallback_keeps_live_source_guard(self):
        for mode in ("stream", "upstream"):
            with self.subTest(mode=mode):
                result = run_log(MODEX, mode, {"stderr"}, live_registry=True)
                self.assertEqual(result[0], 1)
                self.assertEqual(result[1], b"")
                self.assertIn(b"live runtime log sources are not implemented", result[3])
                self.assertNotIn(b"terminal rendering is not implemented", result[3])


if __name__ == "__main__":
    unittest.main()
