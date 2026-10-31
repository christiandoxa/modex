#!/usr/bin/env python3
"""Run the historical 0.166.0 WebSocket fallback comparison in private namespaces."""

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
PRIVATE_TMP = Path("/tmp")
SCRATCH = PRIVATE_TMP / "modex-ci-websocket-fallback"


def python_runtime_paths():
    paths = [
        sys.executable,
        sys.prefix,
        sys.base_prefix,
        sys.exec_prefix,
        sys.base_exec_prefix,
        *sys.path,
    ]
    return [Path(path) for path in paths if path]


def private_tmp_bind_pairs(paths):
    """Return approved host sources and identical destinations beneath /tmp."""
    pairs = {}
    for path in paths:
        destination = Path(os.path.abspath(os.fspath(path)))
        if destination == PRIVATE_TMP or not destination.is_relative_to(PRIVATE_TMP):
            continue
        if not destination.exists():
            continue
        source = destination.resolve(strict=True)
        pairs[destination] = source

    roots = []
    for destination in sorted(pairs, key=lambda path: (len(path.parts), str(path))):
        if any(
            pairs[parent].is_dir() and destination.is_relative_to(parent)
            for parent in roots
        ):
            continue
        roots.append(destination)
    return [(pairs[path], path) for path in roots]


def bwrap_command(*, bwrap, root, command, environment, bind_paths):
    root = Path(root).resolve(strict=True)
    paths = [root, *bind_paths]
    for path in paths:
        target = Path(os.path.abspath(os.fspath(path)))
        if target == PRIVATE_TMP:
            raise ValueError("/tmp cannot be an imported or mounted input")
        if target == SCRATCH or target.is_relative_to(SCRATCH) or SCRATCH.is_relative_to(target):
            raise ValueError(f"input path overlaps writable private scratch: {target}")
    mounts = private_tmp_bind_pairs(paths)
    command_args = [
        str(bwrap),
        "--unshare-all",
        "--uid", "0",
        "--gid", "0",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--ro-bind", "/", "/",
        "--proc", "/proc",
        "--dev", "/dev",
        "--tmpfs", "/tmp",
        "--chmod", "1777", "/tmp",
    ]

    targets = [target for _, target in mounts]
    parent_directories = set()
    for target in targets:
        parent = target.parent
        while parent != PRIVATE_TMP:
            if not parent.is_relative_to(PRIVATE_TMP):
                raise ValueError(f"private input escaped /tmp: {target}")
            parent_directories.add(parent)
            parent = parent.parent
    for parent in sorted(parent_directories, key=lambda path: (len(path.parts), str(path))):
        command_args.extend(("--dir", str(parent)))
    for source, target in mounts:
        command_args.extend(("--ro-bind", str(source), str(target)))

    private_dirs = {
        SCRATCH: 0o700,
        SCRATCH / "home": 0o700,
        SCRATCH / "tmp": 0o700,
        SCRATCH / "config": 0o700,
        SCRATCH / "cache": 0o700,
        SCRATCH / "data": 0o700,
        SCRATCH / "state": 0o700,
    }
    for path in sorted(private_dirs, key=lambda item: (len(item.parts), str(item))):
        command_args.extend(("--dir", str(path), "--chmod", f"{private_dirs[path]:04o}", str(path)))

    env = {
        "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": str(SCRATCH / "home"),
        "TMPDIR": str(SCRATCH / "tmp"),
        "TMP": str(SCRATCH / "tmp"),
        "TEMP": str(SCRATCH / "tmp"),
        "XDG_CONFIG_HOME": str(SCRATCH / "config"),
        "XDG_CACHE_HOME": str(SCRATCH / "cache"),
        "XDG_DATA_HOME": str(SCRATCH / "data"),
        "XDG_STATE_HOME": str(SCRATCH / "state"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TERM": "dumb",
        "NO_COLOR": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        **environment,
    }
    for name, value in env.items():
        command_args.extend(("--setenv", name, str(value)))

    command_args.extend(("--chdir", str(root), "--", "/bin/sh", "-eu", "-c"))
    command_args.append('exec "$@"')
    command_args.append("modex-websocket-fallback")
    command_args.extend(str(item) for item in command)
    return command_args


def main():
    python = Path(sys.executable).resolve(strict=True)
    modex = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex")).resolve(strict=True)
    oracle_value = os.environ.get("PRODEX_ORACLE")
    if not oracle_value:
        raise SystemExit("PRODEX_ORACLE must identify the verified 0.166.0 oracle")
    oracle = Path(oracle_value).resolve(strict=True)
    toolchain_value = os.environ.get("MODEX_TOOLCHAIN_DIR")
    toolchain = Path(toolchain_value).resolve(strict=True) if toolchain_value else None

    bwrap_value = os.environ.get("BWRAP") or shutil.which("bwrap")
    if not bwrap_value:
        raise SystemExit("bubblewrap is required for the WebSocket fallback probe")
    bwrap = Path(bwrap_value).resolve(strict=True)
    if not bwrap.is_file() or not os.access(bwrap, os.X_OK):
        raise SystemExit(f"bubblewrap is not executable: {bwrap}")

    bind_paths = [modex, oracle, bwrap, *python_runtime_paths()]
    if toolchain is not None:
        bind_paths.append(toolchain)

    environment = {
        "MODEX_REAL_CODEX_NETNS": "1",
        "MODEX_BINARY": str(modex),
        "PRODEX_ORACLE": str(oracle),
        "PRODEX_ORACLE_01660": str(oracle),
        "PYTHONPATH": os.pathsep.join((str(ROOT / "tests"), str(ROOT))),
    }
    if toolchain is not None:
        environment["MODEX_TOOLCHAIN_DIR"] = str(toolchain)

    command = bwrap_command(
        bwrap=bwrap,
        root=ROOT,
        command=(python, ROOT / "scripts/ci/run-unittest.py",
                 "manual_local_rewrite_websocket_fallback_01660.py"),
        environment=environment,
        bind_paths=bind_paths,
    )
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
