#!/usr/bin/env python3
"""Run the active local WebSocket fallback comparison in an isolated namespace."""

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ci"))
import run_websocket_fallback_01660 as sandbox


def main():
    python = Path(sys.executable).resolve(strict=True)
    modex = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex")).resolve(strict=True)
    oracle_value = os.environ.get("PRODEX_ORACLE_01662") or os.environ.get("PRODEX_ORACLE")
    if not oracle_value:
        raise SystemExit("PRODEX_ORACLE_01662 must identify the verified Prodex 0.166.2 oracle")
    oracle = Path(oracle_value).resolve(strict=True)
    bwrap_value = os.environ.get("BWRAP") or shutil.which("bwrap")
    if not bwrap_value:
        raise SystemExit("bubblewrap is required for the local WebSocket fallback comparison")
    bwrap = Path(bwrap_value).resolve(strict=True)
    if not bwrap.is_file() or not os.access(bwrap, os.X_OK):
        raise SystemExit(f"bubblewrap is not executable: {bwrap}")

    # Let the preflighted Bubblewrap binary create the rootless, loopback-only
    # namespace. The active test preflight verifies loopback and no default
    # routes; direct `unshare -U` map creation is denied on the hosted runner.
    driver = r'''import os, shutil, subprocess, sys
raise SystemExit(subprocess.run(
    [sys.executable, "scripts/ci/run-unittest.py",
     "test_local_relay_websocket_fallback_01662.py"], check=False,
).returncode)
'''
    environment = {
        "MODEX_REAL_CODEX_NETNS": "1",
        "MODEX_BINARY": str(modex),
        "PRODEX_ORACLE": str(oracle),
        "PRODEX_ORACLE_01662": str(oracle),
        "PYTHONPATH": os.pathsep.join((str(ROOT / "tests"), str(ROOT))),
    }
    command = sandbox.bwrap_command(
        bwrap=bwrap,
        root=ROOT,
        command=(python, "-c", driver),
        environment=environment,
        bind_paths=[modex, oracle, bwrap, *sandbox.python_runtime_paths()],
    )
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
