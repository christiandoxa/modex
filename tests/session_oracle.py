"""Generate isolated session fixtures and inspect the official release behavior."""

import json
from pathlib import Path
import subprocess
import tempfile

from test_cli import ORACLE, ROOT


SESSION_ID = "019a1234-5678-7123-8123-0123456789ab"


def fixture(root):
    (root / "home").mkdir(mode=0o700)
    work = root / "workspace"
    work.mkdir()
    shared = root / "home/.codex/sessions/2026/10/24"
    shared.mkdir(parents=True)
    content = [
        {"timestamp": "2026-10-24T00:00:00Z", "type": "session_meta", "payload": {
            "id": SESSION_ID, "timestamp": "2026-10-24T00:00:00Z",
            "cwd": str(work), "originator": "test-harness", "cli_version": "0.162.0",
            "thread_name": "Session fixture", "model_provider": "openai",
        }},
        {"timestamp": "2026-10-24T01:00:00Z", "type": "turn_context", "payload": {
            "model": "fixture-model", "effort": "high",
        }},
    ]
    (shared / f"rollout-{SESSION_ID}.jsonl").write_text(
        "\n".join(json.dumps(line) for line in content) + "\n")
    return work


def sandbox_command(binary, root, arguments, *, timezone="UTC"):
    linked = subprocess.run(["ldd", str(binary)], capture_output=True, text=True,
                            timeout=10, check=True)
    libraries = set()
    for line in linked.stdout.splitlines():
        for word in line.split():
            if word.startswith("/"):
                libraries.add(word)
    command = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
               "--clearenv", "--tmpfs", "/", "--proc", "/proc", "--dev", "/dev",
               "--tmpfs", "/tmp", "--bind", str(root), str(root),
               "--ro-bind", str(binary), "/app", "--setenv", "HOME", str(root / "home"),
               "--setenv", "PATH", "", "--setenv", "TERM", "dumb", "--setenv", "TZ", timezone,
               "--setenv", "NO_COLOR", "1", "--chdir", str(root / "workspace")]
    for library in sorted(libraries):
        command.extend(["--ro-bind", library, library])
    zoneinfo = Path("/usr/share/zoneinfo")
    if zoneinfo.exists():
        command.extend(["--ro-bind", str(zoneinfo), str(zoneinfo)])
    command.extend(["--", "/app", *arguments])
    return command


def main():
    with tempfile.TemporaryDirectory(prefix="modex-session-oracle-") as directory:
        root = Path(directory)
        fixture(root)
        command = sandbox_command(ORACLE, root, ["session", "list", "--json"])
        result = subprocess.run(command, capture_output=True, timeout=10, check=False)
        print("exit:", result.returncode)
        print("stdout:", result.stdout.decode())
        print("stderr:", result.stderr.decode())
        for path in sorted(root.rglob("*")):
            print(oct(path.lstat().st_mode & 0o777), str(path.relative_to(root)))


if __name__ == "__main__":
    main()
