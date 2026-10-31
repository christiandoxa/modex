"""Synthetic process differential checks for Caveman retirement in 0.166.1."""

import hashlib
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE",
    Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
    / "oracles/0.166.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_SHA256 = "d9c3232ca504548c473ad06e4be001bb307256e00d35f888676e9512c62e4c3a"


def _tree_snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            result[relative] = ("symlink", mode, os.readlink(path))
        elif stat.S_ISDIR(info.st_mode):
            result[relative] = ("directory", mode)
        else:
            result[relative] = ("file", mode, path.read_bytes())
    return result


def _fixture(root):
    home = root / "home"
    workspace = root / "workspace"
    prodex = root / "prodex"
    codex_home = home / ".codex"
    caveman = home / ".local/share/prodex-optimizers/caveman/4.0.1"
    binary_dir = root / "bin"
    for directory in (home, workspace, prodex, codex_home, caveman, binary_dir):
        directory.mkdir(parents=True, mode=0o700)
    codex = binary_dir / "codex"
    codex.write_text("#!/bin/sh\nexit 1\n")
    codex.chmod(0o700)
    (codex_home / "config.toml").write_text(
        "# synthetic user-owned configuration\n"
        "[features]\napps = false\n"
    )
    (codex_home / "config.toml").chmod(0o600)
    reference = caveman / "AGENTS.md"
    reference.write_text("Synthetic managed plugin instructions.\n")
    (codex_home / "AGENTS.md").write_text(
        "User-authored instruction; keep it.\n"
        f"@{reference}\n"
    )
    (codex_home / "AGENTS.override.md").write_text(
        "User override; keep it.\n"
    )
    return home, workspace, prodex, codex_home


def _run(binary, argv0, arguments, *, retired_tree=True):
    with tempfile.TemporaryDirectory(prefix="modex-caveman-01661-") as raw:
        root = Path(raw)
        home, workspace, prodex, codex_home = _fixture(root)
        if not retired_tree:
            import shutil

            shutil.rmtree(home / ".local/share/prodex-optimizers/caveman")
        before = _tree_snapshot(root)
        command = sandbox_command(
            binary,
            root,
            list(arguments),
            argv0=argv0,
            environment={
                "PRODEX_HOME": str(prodex),
                "PRODEX_SHARED_CODEX_HOME": str(codex_home),
                "PATH": str(root / "bin"),
            },
        )
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
            check=False,
        )
        after = _tree_snapshot(root)
        return result, before, after


class CavemanRetirement01661Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.1 release")

    def test_retired_tool_selection_is_rejected_before_startup(self):
        cases = (
            ("super", "--tool"),
            ("super", "--require-tool"),
            ("s", "--tool"),
            ("s", "--require-tool"),
        )
        for command, flag in cases:
            arguments = (command, flag, "caveman")
            with self.subTest(arguments=arguments):
                baseline, baseline_before, baseline_after = _run(
                    ORACLE, "prodex", arguments
                )
                modex, modex_before, modex_after = _run(
                    MODEX, "modex", arguments
                )
                self.assertEqual(baseline.returncode, 2, baseline.stderr)
                self.assertEqual((modex.returncode, modex.stdout, modex.stderr),
                                 (baseline.returncode, baseline.stdout, baseline.stderr))
                self.assertEqual(baseline_before, baseline_after)
                self.assertEqual(modex_before, modex_after)

    def test_managed_caveman_is_ignored_by_dry_run_without_touching_user_home(self):
        arguments = (
            "super", "--dry-run", "--provider", "deepseek", "--api-key", "synthetic-key",
            "--base-url", "http://127.0.0.1:8131/v1", "--no-presidio", "--no-sub-agent",
            "--skip-quota-check", "exec", "synthetic prompt",
        )
        baseline, baseline_before, baseline_after = _run(
            ORACLE, "prodex", arguments
        )
        modex, modex_before, modex_after = _run(MODEX, "modex", arguments)

        self.assertEqual((baseline.returncode, baseline.stderr), (0, b""), baseline.stderr)
        self.assertEqual((modex.returncode, modex.stderr), (baseline.returncode, baseline.stderr))
        self.assertEqual(baseline.stdout, modex.stdout)
        self.assertNotIn(b"caveman", modex.stdout.lower())
        self.assertEqual(baseline_before, baseline_after)
        self.assertEqual(modex_before, modex_after)

        without_caveman, _, _ = _run(MODEX, "modex", arguments, retired_tree=False)
        self.assertEqual((without_caveman.returncode, without_caveman.stdout, without_caveman.stderr),
                         (modex.returncode, modex.stdout, modex.stderr))


if __name__ == "__main__":
    unittest.main()
