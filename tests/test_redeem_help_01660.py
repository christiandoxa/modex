"""Compare the offline redeem help routes with Prodex 0.166.0."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256


def run(binary, root, arguments, argv0):
    home = root / "home"
    home.mkdir(mode=0o700)
    workspace = root / "workspace"
    workspace.mkdir(mode=0o700)
    environment = {
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_DATA_HOME": str(home / ".local/share"),
        "XDG_STATE_HOME": str(home / ".local/state"),
        "TMPDIR": "/tmp",
    }
    command = sandbox_command(
        binary, root, list(arguments), argv0=argv0, environment=environment,
    )
    result = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )
    created = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path not in (home, workspace)
    }
    return result, created


class RedeemHelp01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")
        if not ORACLE.is_absolute() or not ORACLE.is_file():
            raise AssertionError(f"Use the pinned 0.166.0 oracle: {ORACLE}")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The 0.166.0 oracle checksum is wrong")

    def test_help_aliases_render_without_local_state_or_provider_traffic(self):
        cases = (
            ("prodex", "modex", ("redeem", "--help")),
            ("prodex", "modex", ("redeem", "-h")),
            ("prodex", "modex", ("redeem", "-hh")),
            ("prodex", "modex", ("help", "redeem")),
            ("prodex", "modex", ("redeem", "synthetic-profile", "--help")),
            ("prodex", "modex", (
                "redeem", "--base-url", "http://127.0.0.1:1", "--no-proxy",
                "synthetic-profile", "--help",
            )),
            ("custom-prodex", "custom-modex", ("redeem", "--help")),
        )
        for oracle_argv0, modex_argv0, arguments in cases:
            with self.subTest(arguments=arguments):
                observations = []
                for binary, argv0 in ((ORACLE, oracle_argv0), (MODEX, modex_argv0)):
                    with tempfile.TemporaryDirectory(prefix="modex-redeem-help-01660-") as directory:
                        result, created = run(binary, Path(directory), arguments, argv0)
                        self.assertEqual((result.returncode, result.stderr), (0, b""))
                        self.assertEqual(created, set())
                        observations.append(result.stdout)
                expected = observations[0].replace(
                    b"Usage: " + oracle_argv0.encode() + b" ",
                    b"Usage: " + modex_argv0.encode() + b" ",
                    1,
                )
                self.assertEqual(observations[1], expected)

    def test_redemption_stays_fail_closed_without_state_or_network_access(self):
        with tempfile.TemporaryDirectory(prefix="modex-redeem-guard-01660-") as directory:
            result, created = run(
                MODEX, Path(directory), ("redeem", "synthetic-profile", "--yes"), "modex",
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"has not implemented the requested command", result.stderr)
            self.assertEqual(created, set())

    def test_invalid_option_before_help_is_rejected_without_state(self):
        arguments = ("redeem", "--not-a-redeem-option", "--help")
        results = []
        for binary, argv0 in ((ORACLE, "prodex"), (MODEX, "modex")):
            with tempfile.TemporaryDirectory(prefix="modex-redeem-invalid-01660-") as directory:
                result, created = run(binary, Path(directory), arguments, argv0)
                self.assertEqual(created, set())
                results.append(result)

        baseline, modex = results
        self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
        self.assertTrue(
            baseline.stderr.startswith(b"error: unexpected argument '--not-a-redeem-option' found\n"),
            baseline.stderr,
        )
        expected = baseline.stderr.replace(
            b"Usage: prodex ", b"Usage: modex ", 1
        )
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr), (2, b"", expected))

    def test_help_alias_rejects_extra_operand(self):
        arguments = ("help", "redeem", "extra")
        results = []
        for binary, argv0 in ((ORACLE, "prodex"), (MODEX, "modex")):
            with tempfile.TemporaryDirectory(prefix="modex-redeem-extra-help-01660-") as directory:
                result, created = run(binary, Path(directory), arguments, argv0)
                self.assertEqual(created, set())
                results.append(result)

        baseline, modex = results
        self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
        expected = baseline.stderr.replace(
            b"Usage: prodex ", b"Usage: modex ", 1
        )
        self.assertEqual((modex.returncode, modex.stdout, modex.stderr), (2, b"", expected))


if __name__ == "__main__":
    unittest.main()
