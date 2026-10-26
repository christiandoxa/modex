"""Differential checks for Gateway's frozen Clap argument behavior."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_GATEWAY_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_GATEWAY_ORACLE",
    "/home/doxa/.cache/modex/oracles/0.439.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "b4511d679dd6da53f706400dba5b368ffc5b5663f8764fa0c8f148b358b9255a"


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
    return '{"source":"GitHub","latest_version":"0.439.1","checked_at":' + str(int(time.time())) + '}\n'


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


if __name__ == "__main__":
    unittest.main()
