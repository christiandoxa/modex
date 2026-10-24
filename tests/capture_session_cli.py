"""Capture argument diagnostics and help directly from the frozen release."""

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from session_oracle import sandbox_command
from test_cli import ORACLE, ORACLE_SHA256, ROOT


CASES = [
    ["session"], ["session", "--help"], ["session", "-h"], ["session", "help"],
    ["session", "help", "list"], ["session", "help", "current"], ["session", "help", "resume"],
    ["session", "list", "--help"], ["session", "list", "-h"], ["session", "current", "--help"],
    ["session", "resume", "--help"],
    ["session", "list", "--query", "--help"],
    ["session", "list", "--json", "--id-only", "--help"],
    ["session", "list", "--json", "--json", "--help"],
    ["session", "list", "--unknown", "--help"],
    ["session", "list", "--limit", "bad", "--help"],
    ["session", "list", "--json", "--id-only"],
    ["session", "list", "--resume-command", "--json"],
    ["session", "list", "--parent-only", "--include-subagents"],
    ["session", "list", "--include-subagents", "--parent-only"],
    ["session", "list", "--json", "--json"],
    ["session", "list", "--profile", "a", "--profile", "b"],
    ["session", "list", "--query"], ["session", "list", "--query=", "--json"],
    ["session", "list", "--limit"], ["session", "list", "--limit="],
    ["session", "list", "--limit", "bad"], ["session", "list", "--limit", "-1"],
    ["session", "list", "--limit=-1"], ["session", "list", "--limit", "18446744073709551616"],
    ["session", "list", "--json=true"], ["session", "list", "-j"],
    ["session", "list", "--unknown"], ["session", "list", "extra"],
    ["session", "list", "--cwd", "/tmp"], ["session", "current", "--cwd"],
    ["session", "current", "--json", "--json"],
    ["session", "resume"], ["session", "nonsense"],
]


def main():
    if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
        raise SystemExit("The oracle checksum does not match the frozen release")
    records = []
    with tempfile.TemporaryDirectory(prefix="modex-session-cli-") as directory:
        for index, arguments in enumerate(CASES):
            root = Path(directory) / str(index)
            root.mkdir()
            (root / "home").mkdir(mode=0o700)
            (root / "workspace").mkdir()
            result = subprocess.run(sandbox_command(ORACLE, root, arguments, argv0="prodex"),
                                    capture_output=True, timeout=10, check=False)
            records.append({"arguments": arguments, "exit_code": result.returncode,
                            "stdout": result.stdout.decode(), "stderr": result.stderr.decode(),
                            "new_paths": sorted(str(path.relative_to(root)) for path in root.rglob("*")
                                                if path not in (root / "home", root / "workspace"))})
    output = ROOT / "docs/evidence/baseline/session-cli.json"
    output.write_text(json.dumps({"schema_version": 1, "baseline_commit":
        "433aad44bb249d5c25a231a6b06c2fa522a39a1f", "oracle_sha256": ORACLE_SHA256,
        "reproduce": "python3 tests/capture_session_cli.py", "cases": records}, indent=2) + "\n")
    print(f"Captured {len(records)} baseline session CLI cases")


if __name__ == "__main__":
    main()
