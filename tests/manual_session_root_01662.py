"""Characterize Prodex 0.166.2 native worker resume with synthetic sessions.

Run after `make build` with PRODEX_ORACLE_01662 set to the verified 0.166.2
binary. This is a mismatch capture, not a parity assertion.
"""

import hashlib
import json
import os
import sqlite3
from pathlib import Path
import subprocess
import tempfile

from session_oracle import sandbox_command


ROOT = Path(__file__).resolve().parents[1]
ORACLE = Path(os.environ.get("PRODEX_ORACLE_01662", "/nonexistent/prodex-0.166.2"))
ORACLE_SHA256 = "e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00"
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE_SOURCE_COMMIT = "b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7"
ROOT_ID = "01900000-0000-7000-8000-000000000710"
CHILD_ID = "01900000-0000-7000-8000-000000000711"
MISSING_PARENT_ID = "01900000-0000-7000-8000-000000000799"
NO_PROFILE = (
    "Error: no active profile selected and no Codex-compatible profiles are available; "
    "use `prodex use --profile <name>` or pass --profile\n"
)
UNSUPPORTED = (
    "Error: Super startup is not implemented: secure temporary overlays, Smart Context "
    "initialization, and Codex launch supervision remain unavailable\n"
)


def snapshot(root):
    result = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        relative = str(path.relative_to(root))
        timestamps = (info.st_mtime_ns, info.st_ctime_ns)
        if path.is_symlink():
            value = ("symlink", info.st_mode & 0o777, timestamps, os.readlink(path))
        elif path.is_dir():
            value = ("directory", info.st_mode & 0o777, timestamps)
        else:
            value = ("file", info.st_mode & 0o777, timestamps, path.read_bytes())
        result[relative] = value
    return result


def make_fixture(
    base, *, child_version="v2", child_parent=ROOT_ID, session_subdirectory="sessions"
):
    home = base / "home"
    prodex_home = base / "prodex-home"
    shared = base / "codex-home"
    workspace = base / "workspace"
    for path in (home, prodex_home, shared, workspace):
        path.mkdir(mode=0o700 if path != workspace else 0o755)
    session_dir = shared / session_subdirectory / "2026/10/31"
    session_dir.mkdir(parents=True)

    def write_session(session_id, parent, version):
        payload = {
            "id": session_id,
            "session_id": ROOT_ID,
            "cwd": str(workspace),
            "multi_agent_version": version,
        }
        if parent:
            payload["parent_thread_id"] = parent
            payload["source"] = {
                "subagent": {"thread_spawn": {"parent_thread_id": parent, "depth": 1}}
            }
        path = session_dir / f"rollout-2026-10-31T01-00-00-{session_id}.jsonl"
        path.write_text(
            json.dumps({"type": "session_meta", "payload": payload}) + "\n",
            encoding="utf-8",
        )
        return path

    if child_parent != MISSING_PARENT_ID:
        write_session(ROOT_ID, None, "v2")
    child = write_session(CHILD_ID, child_parent, child_version)
    environment = {
        "HOME": str(home),
        "PRODEX_HOME": str(prodex_home),
        "PRODEX_SHARED_CODEX_HOME": str(shared),
        "CODEX_HOME": str(shared),
        "PRODEX_CODEX_BIN": str(base / "missing-codex"),
        "XDG_CONFIG_HOME": str(home / "config"),
        "XDG_CACHE_HOME": str(home / "cache"),
    }
    return environment, shared, child


def install_state_db_index(shared, root_file, child_file):
    database = sqlite3.connect(shared / "state_01662_fixture.sqlite")
    try:
        database.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT)")
        for session_id, path in ((ROOT_ID, root_file), (CHILD_ID, child_file)):
            database.execute(
                "INSERT INTO threads (id, rollout_path) VALUES (?, ?)",
                (session_id, path.relative_to(shared).as_posix()),
            )
        database.commit()
    finally:
        database.close()


def run(binary, base, environment, arguments):
    before = snapshot(base)
    command = sandbox_command(binary, base, arguments, timezone="UTC", environment=environment)
    result = subprocess.run(command, capture_output=True, timeout=20, check=False)
    after = snapshot(base)
    if after != before:
        raise AssertionError(f"{binary.name} changed the isolated fixture")
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout.decode("utf-8", errors="replace"),
        "stderr": result.stderr.decode("utf-8", errors="replace"),
        "fixture_unchanged": True,
    }


def main():
    if not ORACLE.is_file():
        raise SystemExit(f"set PRODEX_ORACLE_01662 to the verified Prodex 0.166.2 binary: {ORACLE}")
    if not MODEX.is_file():
        raise SystemExit(f"build Modex first with `make build`: {MODEX}")
    if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
        raise SystemExit("PRODEX_ORACLE_01662 must match the official 0.166.2 SHA-256")

    cases = (
        ("v2-child", "v2", ROOT_ID, CHILD_ID, "sessions"),
        ("root", "v2", None, ROOT_ID, "sessions"),
        ("v1-child", "v1", ROOT_ID, CHILD_ID, "sessions"),
        ("missing-parent", "v2", MISSING_PARENT_ID, CHILD_ID, "sessions"),
        ("db-indexed-v2-child", "v2", ROOT_ID, CHILD_ID, "indexed"),
    )
    expected_root_status = (
        f"Prodex launch: resuming parent-owned sub-agent through root session {ROOT_ID}...\n"
    )
    report = {
        "reference": {
            "version": "0.166.2",
            "source_commit": ORACLE_SOURCE_COMMIT,
            "binary_sha256": ORACLE_SHA256,
        },
        "modex_binary": {
            "description": "provided Modex binary",
            "sha256": hashlib.sha256(MODEX.read_bytes()).hexdigest(),
        },
        "isolation": "bubblewrap network namespace, synthetic HOME/Prodex/Codex roots, read-only fixture snapshots, no Codex binary or credentials",
        "cases": {},
    }
    for name, child_version, parent, target_id, session_subdirectory in cases:
        with tempfile.TemporaryDirectory(prefix="modex-session-root-01662-") as directory:
            base = Path(directory)
            environment, shared, child_file = make_fixture(
                base,
                child_version=child_version,
                child_parent=parent,
                session_subdirectory=session_subdirectory,
            )
            # The root case has no worker record; use the requested root as its target.
            if name == "root":
                child_file.unlink()
                root_payload = {
                    "id": ROOT_ID,
                    "session_id": ROOT_ID,
                    "cwd": str(base / "workspace"),
                    "multi_agent_version": "v2",
                }
                root_path = next(shared.rglob("*.jsonl"))
                root_path.write_text(
                    json.dumps({"type": "session_meta", "payload": root_payload}) + "\n",
                    encoding="utf-8",
                )
            if name == "db-indexed-v2-child":
                root_file = next(shared.rglob(f"*{ROOT_ID}.jsonl"))
                install_state_db_index(shared, root_file, child_file)
            arguments = ["s", "--dry-run", "--no-presidio", "--no-sub-agent", target_id]
            oracle = run(ORACLE, base, environment, arguments)
            modex = run(MODEX, base, environment, arguments)
            if name in ("v2-child", "db-indexed-v2-child"):
                if not oracle["stderr"].startswith(expected_root_status + NO_PROFILE):
                    raise AssertionError(f"unexpected Prodex V2 child behavior: {oracle}")
                if modex["stderr"] != UNSUPPORTED:
                    raise AssertionError(f"unexpected current Modex behavior: {modex}")
            elif name == "v1-child" or name == "root":
                if oracle["stderr"] != NO_PROFILE:
                    raise AssertionError(f"unexpected Prodex direct-resume behavior: {oracle}")
                if modex["stderr"] != UNSUPPORTED:
                    raise AssertionError(f"unexpected current Modex behavior: {modex}")
            else:
                if "session parent metadata is missing" not in oracle["stderr"]:
                    raise AssertionError(f"Prodex did not fail closed for missing ancestry: {oracle}")
                if modex["stderr"] != UNSUPPORTED:
                    raise AssertionError(f"unexpected current Modex behavior: {modex}")
            report["cases"][name] = {"prodex_0_166_2": oracle, "modex": modex}

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
