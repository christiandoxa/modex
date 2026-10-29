"""Reproduce natural terminal width behavior against frozen release oracles."""

import fcntl
import hashlib
import os
import struct
import termios
import unittest

import test_cli
import test_cli_01651 as active_cli
import test_super_launch as launch_support


def run_with_terminal_size(binary, rows, columns):
    original_run = launch_support.subprocess.run

    def run(*args, **kwargs):
        tty = kwargs.get("stderr")
        if isinstance(tty, int) and os.isatty(tty):
            fcntl.ioctl(tty, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))

            def acquire_controlling_terminal():
                os.setsid()
                fcntl.ioctl(tty, termios.TIOCSCTTY, 0)

            kwargs["preexec_fn"] = acquire_controlling_terminal
        return original_run(*args, **kwargs)

    launch_support.subprocess.run = run
    try:
        result, records, upstream, state = launch_support.SuperLaunchTests().run_launch(
            binary=binary,
            scenario="exit-seven",
            environment_overrides={"TERM": "dumb", "MODEX_TEST_CODEX_VERSION": "codex-cli 0.153.1"},
            stderr_tty=True,
        )
        return result, records, upstream, state
    finally:
        launch_support.subprocess.run = original_run


class TerminalDimensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (
            not active_cli.ORACLE.is_file()
            or hashlib.sha256(active_cli.ORACLE.read_bytes()).hexdigest() != active_cli.ORACLE_SHA256
        ):
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 Linux release")
        if (
            not test_cli.ORACLE.is_file()
            or hashlib.sha256(test_cli.ORACLE.read_bytes()).hexdigest() != test_cli.ORACLE_SHA256
        ):
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.439.2 Linux release")
        if not launch_support.MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def test_natural_tty_width_gap_against_both_releases(self):
        outputs = {}
        for name, binary in (
            ("0.165.1", active_cli.ORACLE),
            ("0.439.2", test_cli.ORACLE),
            ("Modex", launch_support.MODEX),
        ):
            with self.subTest(binary=name):
                result, records, upstream, state = run_with_terminal_size(binary, 24, 42)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual([record["args"] for record in records if record["kind"] == "probe"], [["--version"]])
                self.assertEqual((upstream, state["leftovers"]), ([], []))
                self.assertNotIn(b"synthetic-provider-key", result.stdout + result.stderr)
                normalized = launch_support.normalized_codex_path(result.stderr)
                outputs[name] = normalized.splitlines()[0]

        self.assertEqual(len(outputs["0.165.1"]), 42)
        self.assertEqual(outputs["0.439.2"], outputs["0.165.1"])
        self.assertEqual(len(outputs["Modex"]), 110)
        self.assertNotEqual(outputs["Modex"], outputs["0.439.2"])


if __name__ == "__main__":
    unittest.main()
