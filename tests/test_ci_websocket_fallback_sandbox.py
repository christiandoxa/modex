"""Exercise bwrap isolation and the historical 0.166.0 WebSocket comparison."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import run_websocket_fallback_01660 as sandbox


class WebSocketFallbackSandboxTests(unittest.TestCase):
    def setUp(self):
        bwrap = os.environ.get("BWRAP") or shutil.which("bwrap")
        if not bwrap:
            raise AssertionError("bubblewrap is required for the WebSocket fallback checks")
        self.bwrap = Path(bwrap).resolve(strict=True)

    def test_explicit_tmp_inputs_and_venv_are_read_only_and_isolated(self):
        with tempfile.TemporaryDirectory(prefix="modex-ci-websocket-sources-", dir="/tmp") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir(mode=0o700)
            (workspace / "workspace-sentinel").write_text("synthetic workspace\n", encoding="utf-8")
            modex = workspace / "modex"
            modex.write_text("synthetic Modex marker\n", encoding="utf-8")
            oracle = root / "oracle"
            oracle.write_text("synthetic oracle marker\n", encoding="utf-8")

            toolchain = root / "toolchain"
            mojo = toolchain / "bin/mojo"
            mojo.parent.mkdir(parents=True, mode=0o700)
            mojo.write_text("synthetic toolchain marker\n", encoding="utf-8")
            mojo.chmod(0o700)

            python_root = root / "python-venv"
            venv.EnvBuilder(with_pip=False, system_site_packages=True).create(python_root)
            python = python_root / "bin/python"
            self.assertTrue(python.exists(), f"virtual environment lacks its interpreter: {python}")

            probe = workspace / "probe.py"
            probe.write_text(
                """import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.environ["MODEX_TESTS_DIR"])
import manual_local_rewrite_websocket_fallback_01660 as manual

manual.require_isolated_environment()
entries = manual._mount_entries()
paths = (
    ("workspace", Path(os.environ["PROBE_WORKSPACE"])),
    ("Modex", Path(os.environ["MODEX_BINARY"])),
    ("Prodex oracle", Path(os.environ["PRODEX_ORACLE"])),
    ("Python", Path(sys.executable)),
    ("Python prefix", Path(sys.prefix)),
    ("Mojo toolchain", Path(os.environ["MODEX_TOOLCHAIN_DIR"])),
)
for label, path in paths:
    manual._require_readonly_input(label, path, entries)
try:
    manual._require_readonly_input("unbound scratch", Path(os.environ["TMPDIR"]), entries)
except AssertionError:
    pass
else:
    raise AssertionError("the preflight accepted an unbound path from private /tmp")
try:
    manual._require_readonly_input("Python import root", Path("/tmp"), entries)
except AssertionError:
    pass
else:
    raise AssertionError("the preflight accepted writable /tmp as a Python import path")

assert Path(sys.prefix) == Path(os.environ["PROBE_PYTHON_PREFIX"])
assert Path(os.environ["PROBE_WORKSPACE"], "workspace-sentinel").read_text() == "synthetic workspace\\n"
assert Path(os.environ["PRODEX_ORACLE"]).read_text() == "synthetic oracle marker\\n"
assert Path(os.environ["MODEX_TOOLCHAIN_DIR"], "bin/mojo").read_text() == "synthetic toolchain marker\\n"
assert "MODEX_CI_HOST_SENTINEL" not in os.environ
for path in (Path(os.environ["PROBE_WORKSPACE"], "workspace-sentinel"),
             Path(os.environ["PRODEX_ORACLE"]),
             Path(os.environ["MODEX_TOOLCHAIN_DIR"], "bin/mojo")):
    try:
        path.write_text("must remain read-only", encoding="utf-8")
    except OSError:
        pass
    else:
        raise AssertionError(f"host input unexpectedly writable: {path}")

links = subprocess.run(
    ["ip", "-o", "link", "show"], check=True, text=True, capture_output=True,
).stdout.splitlines()
assert len(links) == 1 and "lo" in links[0] and "UP" in links[0], links
for args in (["ip", "route", "show", "default"], ["ip", "-6", "route", "show", "default"]):
    assert not subprocess.run(
        args, check=True, text=True, capture_output=True,
    ).stdout.strip()
print("temporary input isolation: PASS")
""",
                encoding="utf-8",
            )

            environment = {
                "MODEX_REAL_CODEX_NETNS": "1",
                "MODEX_BINARY": str(modex),
                "PRODEX_ORACLE": str(oracle),
                "MODEX_TOOLCHAIN_DIR": str(toolchain),
                "MODEX_TESTS_DIR": str(ROOT / "tests"),
                "PROBE_WORKSPACE": str(workspace),
                "PROBE_PYTHON_PREFIX": str(python_root),
                "PYTHONPATH": os.pathsep.join((str(ROOT / "tests"), str(ROOT))),
            }
            paths = [ROOT, workspace, modex, oracle, toolchain, python_root, python,
                     *sandbox.python_runtime_paths()]
            for path in (Path("/tmp"), sandbox.SCRATCH / "cache" / "hidden-input"):
                with self.subTest(overlap=path), self.assertRaises(ValueError):
                    sandbox.bwrap_command(
                        bwrap=self.bwrap,
                        root=workspace,
                        command=(python, probe),
                        environment=environment,
                        bind_paths=[path],
                    )
            command = sandbox.bwrap_command(
                bwrap=self.bwrap,
                root=workspace,
                command=(python, probe),
                environment=environment,
                bind_paths=paths,
            )
            with patch.dict(os.environ, {"MODEX_CI_HOST_SENTINEL": "must-not-cross-bwrap"}):
                result = subprocess.run(
                    command,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                    check=False,
                )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("temporary input isolation: PASS", result.stdout)

    def test_historical_01660_manual_websocket_comparison_runs_in_bwrap(self):
        oracle = os.environ.get("PRODEX_ORACLE")
        if not oracle:
            raise AssertionError("CI must route the verified historical 0.166.0 oracle before this check")
        environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "BWRAP": str(self.bwrap),
            "MODEX_BINARY": os.environ.get("MODEX_BINARY", str(ROOT / "build/modex")),
            "PRODEX_ORACLE": oracle,
        }
        if os.environ.get("MODEX_TOOLCHAIN_DIR"):
            environment["MODEX_TOOLCHAIN_DIR"] = os.environ["MODEX_TOOLCHAIN_DIR"]
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/ci/run_websocket_fallback_01660.py")],
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Ran 1 test", result.stderr)
        self.assertIn("OK", result.stderr)

    def test_default_host_paths_are_read_only_without_tmp_rebinds(self):
        candidates = [
            Path(os.environ.get("RUNNER_TEMP", "/var/tmp")).resolve(),
            Path("/var/tmp").resolve(),
        ]
        parent = next(
            (path for path in candidates
             if path.is_dir() and not path.is_relative_to(Path("/tmp")) and os.access(path, os.W_OK)),
            None,
        )
        if parent is None:
            raise AssertionError("a writable host temp directory outside /tmp is required")

        with tempfile.TemporaryDirectory(prefix="modex-ci-websocket-host-", dir=parent) as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir(mode=0o700)
            marker = workspace / "workspace-sentinel"
            marker.write_text("synthetic external workspace\n", encoding="utf-8")
            modex = workspace / "modex"
            modex.write_text("synthetic external Modex marker\n", encoding="utf-8")
            oracle = root / "oracle"
            oracle.write_text("synthetic external oracle\n", encoding="utf-8")
            toolchain = root / "toolchain"
            toolchain.mkdir(mode=0o700)
            toolchain_marker = toolchain / "mojo"
            toolchain_marker.write_text("synthetic external toolchain\n", encoding="utf-8")

            probe = workspace / "probe.py"
            probe.write_text(
                """import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["MODEX_TESTS_DIR"])
import manual_local_rewrite_websocket_fallback_01660 as manual

manual.require_isolated_environment()
entries = manual._mount_entries()
for label, name in (("workspace", "PROBE_WORKSPACE"),
                     ("Modex", "MODEX_BINARY"),
                     ("Prodex oracle", "PRODEX_ORACLE"),
                     ("Mojo toolchain", "MODEX_TOOLCHAIN_DIR")):
    manual._require_readonly_input(label, Path(os.environ[name]), entries)
readonly_files = (
    Path(os.environ["PROBE_WORKSPACE"], "workspace-sentinel"),
    Path(os.environ["MODEX_BINARY"]),
    Path(os.environ["PRODEX_ORACLE"]),
    Path(os.environ["MODEX_TOOLCHAIN_DIR"], "mojo"),
)
for path in readonly_files:
    assert path.is_file(), path
    try:
        path.write_text("changed", encoding="utf-8")
    except OSError:
        pass
    else:
        raise AssertionError(f"external input was writable: {path}")
print("default host paths: PASS")
""",
                encoding="utf-8",
            )
            environment = {
                "MODEX_REAL_CODEX_NETNS": "1",
                "MODEX_BINARY": str(modex),
                "PRODEX_ORACLE": str(oracle),
                "MODEX_TOOLCHAIN_DIR": str(toolchain),
                "MODEX_TESTS_DIR": str(ROOT / "tests"),
                "PROBE_WORKSPACE": str(workspace),
                "PYTHONPATH": os.pathsep.join((str(ROOT / "tests"), str(ROOT))),
            }
            command = sandbox.bwrap_command(
                bwrap=self.bwrap,
                root=workspace,
                command=(sys.executable, probe),
                environment=environment,
                bind_paths=[ROOT, workspace, modex, oracle, toolchain,
                            *sandbox.python_runtime_paths()],
            )
            result = subprocess.run(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("default host paths: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
