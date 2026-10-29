"""Differential checks for Gateway's frozen Clap argument behavior."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
from test_cli import ORACLE as ACTIVE_ORACLE, ORACLE_SHA256 as ACTIVE_ORACLE_SHA256

BUILD_ROOT = Path(os.environ.get("BUILD_DIR", ROOT / "build"))
MODEX = Path(os.environ.get("MODEX_GATEWAY_BINARY", BUILD_ROOT / "modex"))
ORACLE = Path(os.environ.get("PRODEX_GATEWAY_ORACLE", ACTIVE_ORACLE))
ORACLE_SHA256 = ACTIVE_ORACLE_SHA256
MODEX_REFERENCE_VERSION = os.environ.get(
    "MODEX_REFERENCE_VERSION",
    json.loads((ROOT / "docs/baseline.json").read_text(encoding="utf-8"))["reference"]["tag"],
)


def run_cli(binary, executable_name, arguments):
    with tempfile.TemporaryDirectory(prefix="modex-gateway-cli-") as temporary:
        root = Path(temporary)
        paths = {
            "HOME": root / "home",
            "PRODEX_HOME": root / "prodex",
            "PRODEX_SHARED_CODEX_HOME": root / "shared-codex",
            "XDG_CONFIG_HOME": root / "xdg-config",
            "XDG_CACHE_HOME": root / "xdg-cache",
            "TMPDIR": root,
        }
        for path in paths.values():
            path.mkdir(mode=0o700, exist_ok=True)
        cache = paths["PRODEX_HOME"] / "update-check.json"
        cache.write_text(json_cache(), encoding="utf-8")
        cache.chmod(0o600)
        environment = {
            **{name: str(path) for name, path in paths.items()},
            "PATH": "/usr/bin:/bin",
            "TERM": "dumb",
            "NO_COLOR": "1",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        bin_directory = root / "bin"
        bin_directory.mkdir(mode=0o700)
        executable = bin_directory / executable_name
        executable.symlink_to(binary.resolve())
        return subprocess.run(
            [str(executable), *arguments],
            cwd=root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )


def json_cache():
    return ('{"source":"GitHub","latest_version":"' + MODEX_REFERENCE_VERSION
            + '","checked_at":' + str(int(time.time())) + '}\n')


@unittest.skipUnless(ORACLE.is_file(), f"pinned Prodex oracle unavailable: {ORACLE}")
class GatewayCLIDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"build the actual Modex CLI first: {MODEX}")
        digest = hashlib.sha256(ORACLE.read_bytes()).hexdigest()
        if digest != ORACLE_SHA256:
            raise AssertionError(f"pinned Prodex oracle checksum mismatch: {digest}")

    def assert_matches_oracle(self, arguments):
        baseline = run_cli(ORACLE, "prodex", arguments)
        actual = run_cli(MODEX, "modex", arguments)
        self.assertEqual(actual.returncode, baseline.returncode)
        self.assertEqual(actual.stdout, baseline.stdout)
        self.assertEqual(
            actual.stderr,
            baseline.stderr.replace(b"Usage: prodex ", b"Usage: modex "),
        )

    def test_switch_options_reject_values_with_the_option_usage(self):
        for arguments in (
            ("gateway", "--smart-context=true"),
            ("gateway", "--presidio=false"),
        ):
            with self.subTest(arguments=arguments):
                self.assert_matches_oracle(arguments)

    def test_provider_lone_dash_is_parsed_as_a_value(self):
        self.assert_matches_oracle(("gateway", "--provider", "-"))

    def test_help_short_clusters_and_attached_values_match(self):
        for arguments in (
            ("gateway", "-hfoo"),
            ("gateway", "-hx"),
            ("gateway", "-xhfoo"),
            ("gateway", "--help=true"),
            ("gateway", "--help="),
            ("gateway", "--api-key", "synthetic-gateway-key", "--help=true"),
            ("gateway", "--api-key=synthetic-gateway-key", "--help=true"),
        ):
            with self.subTest(arguments=arguments):
                baseline = run_cli(ORACLE, "prodex", arguments)
                actual = run_cli(MODEX, "modex", arguments)
                self.assertEqual(
                    (actual.returncode, actual.stdout, actual.stderr),
                    (
                        baseline.returncode,
                        baseline.stdout.replace(b"Usage: prodex ", b"Usage: modex "),
                        baseline.stderr.replace(b"Usage: prodex ", b"Usage: modex "),
                    ),
                )
                self.assertNotIn(b"synthetic-gateway-key", actual.stdout + actual.stderr)

    def test_option_terminator_reports_first_trailing_argument(self):
        cases = (
            (("gateway", "--", "synthetic-positional"), b"synthetic-positional"),
            (("gateway", "--no-presidio", "--", "--help"), b"--help"),
            (("gateway", "--api-key", "synthetic-gateway-key", "--", "synthetic-positional"),
             b"synthetic-positional"),
        )
        for arguments, first_trailing_argument in cases:
            with self.subTest(arguments=arguments):
                baseline = run_cli(ORACLE, "prodex", arguments)
                actual = run_cli(MODEX, "modex", arguments)
                self.assertEqual(baseline.returncode, 2)
                self.assertIn(
                    b"unexpected argument '" + first_trailing_argument + b"' found",
                    baseline.stderr,
                )
                self.assertEqual(
                    (actual.returncode, actual.stdout, actual.stderr),
                    (
                        baseline.returncode,
                        baseline.stdout.replace(b"Usage: prodex ", b"Usage: modex "),
                        baseline.stderr.replace(b"Usage: prodex ", b"Usage: modex "),
                    ),
                )
                self.assertNotIn(b"synthetic-gateway-key", actual.stdout + actual.stderr)


if __name__ == "__main__":
    unittest.main()
