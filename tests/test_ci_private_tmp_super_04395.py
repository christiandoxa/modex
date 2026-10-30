"""Ensure CI replaces an unsafe inherited TMPDIR before a Super oracle launch."""

import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

from test_cli import (HISTORICAL_04395_ORACLE as ORACLE,
                      HISTORICAL_04395_ORACLE_SHA256 as ORACLE_SHA256)


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SCRATCH_HELPER = ROOT / "scripts/ci/private-scratch.sh"
DRIVER = r'''
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

private_root = Path(os.environ["MODEX_CI_PRIVATE_ROOT"])
assert stat.S_IMODE(private_root.stat().st_mode) == 0o700
for name in ("HOME", "TMPDIR", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
    directory = Path(os.environ[name])
    assert directory.is_relative_to(private_root), (name, directory, private_root)
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700, (name, oct(directory.stat().st_mode))
assert Path(os.environ["TMPDIR"]) != Path(os.environ["MODEX_INHERITED_TMPDIR"])

sys.path.insert(0, os.environ["MODEX_TESTS_DIR"])
from test_cli import (HISTORICAL_04395_ORACLE as ORACLE,
                      HISTORICAL_04395_ORACLE_SHA256 as ORACLE_SHA256)
from test_deepseek_continuation import buffered_reply, observe_turns

assert hashlib.sha256(ORACLE.read_bytes()).hexdigest() == ORACLE_SHA256
upstream, responses = observe_turns(
    ORACLE,
    [{"model": "deepseek-chat", "input": "synthetic private scratch regression"}],
    [buffered_reply(created=42)],
)
assert len(upstream) == 1, upstream
assert [row["status"] for row in responses] == [200], responses
print("private scratch Super oracle request: PASS")
print(f"private scratch root: {private_root}")
'''


class PrivateTempSuperOracleTests(unittest.TestCase):
    def test_inherited_group_writable_tmpdir_is_replaced_for_real_oracle_request(self):
        with tempfile.TemporaryDirectory(prefix="modex-ci-private-tmp-", dir="/tmp") as temporary:
            root = Path(temporary)
            inherited_tmp = root / "inherited-tmp"
            previous_umask = os.umask(0)
            try:
                inherited_tmp.mkdir(mode=0o775)
            finally:
                os.umask(previous_umask)
            self.assertEqual(stat.S_IMODE(inherited_tmp.stat().st_mode), 0o775)

            driver = root / "request.py"
            driver.write_text(DRIVER, encoding="utf-8")
            environment = {
                "PATH": "/usr/bin:/bin",
                "HOME": str(inherited_tmp),
                "TMPDIR": str(inherited_tmp),
                "TMP": str(inherited_tmp),
                "TEMP": str(inherited_tmp),
                "XDG_CONFIG_HOME": str(inherited_tmp),
                "XDG_CACHE_HOME": str(inherited_tmp),
                "XDG_DATA_HOME": str(inherited_tmp),
                "XDG_STATE_HOME": str(inherited_tmp),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PYTHONPATH": os.pathsep.join((str(ROOT / "tests"), str(ROOT))),
                "PYTHON_BINARY": sys.executable,
                "MODEX_PRIVATE_SCRATCH_HELPER": str(PRIVATE_SCRATCH_HELPER),
                "MODEX_REGRESSION_DRIVER": str(driver),
                "MODEX_TESTS_DIR": str(ROOT / "tests"),
                "MODEX_INHERITED_TMPDIR": str(inherited_tmp),
                "PRODEX_ORACLE_04395": str(ORACLE),
            }
            if "MODEX_REFERENCE_CACHE" in os.environ:
                environment["MODEX_REFERENCE_CACHE"] = os.environ["MODEX_REFERENCE_CACHE"]

            result = subprocess.run(
                ["bash", "-euo", "pipefail", "-c",
                 'source "$MODEX_PRIVATE_SCRATCH_HELPER"; "$PYTHON_BINARY" "$MODEX_REGRESSION_DRIVER"'],
                cwd=ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=90,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("private scratch Super oracle request: PASS", result.stdout)
        roots = [line.removeprefix("private scratch root: ") for line in result.stdout.splitlines()
                 if line.startswith("private scratch root: ")]
        self.assertEqual(len(roots), 1)
        self.assertFalse(Path(roots[0]).exists(), "CI scratch must be removed after its final consumer exits")


if __name__ == "__main__":
    unittest.main()
