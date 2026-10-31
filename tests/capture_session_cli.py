"""Capture argument diagnostics and help directly from the frozen release."""

import hashlib
import itertools
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

CASES += [["help", "session", *tail] for tail in ([], ["list"], ["current"], ["resume"], ["help"], ["list", "extra"])]
CASES += [["session", value] for value in ("listr", "currnt", "resum", "hel", "rest", "-", "list=extra")]
CASES += [["session", *tail] for tail in (["--json", "list"], ["--profil", "current"],
    ["--halp", "list"], ["resume", "--halp"], ["resume", "--foo=bar"])]
CASES += [["session", *tail] for tail in (
    ["--"], ["--", "list"], ["--json"], ["-x"], ["-hh"], ["--help=true"],
    ["list", "--", "--json"], ["list", "--json", "--"], ["list", "--"],
    ["help", "help"], ["help", "--help"], ["help", "list", "extra"],
    ["help", "list", "--help"], ["help", "nonsense"], ["help", "current", "list"],
    ["list", "--help=bad"], ["list", "-h=bad"], ["list", "-hh"],
    ["list", "-hx"], ["list", "-xh"], ["list", "-"], ["list", "--version"],
    ["resume", "--unknown"], ["resume", "-x"], ["resume", "extra", "extra"],
    ["resume", "extra", "--help"], ["resume", "--help", "extra"],
    ["resume", "-hh"], ["resume", "--help=bad"], ["resume", "extra", "--unknown"],
)]
for command in ("list", "current"):
    for typo in ("--jso", "--jsn", "--JSON", "--id", "--id_only", "--resume", "--resume-comman",
                 "--profil", "--queryy", "--limi", "--include-subagent", "--parent", "--cwdx", "--halp"):
        CASES.append(["session", command, typo])
    for name in ("--json", "--id-only", "--resume-command", "--include-subagents", "--parent-only"):
        CASES += [["session", command, name + "="], ["session", command, name, name],
                  ["session", command, name, name + "=true"], ["session", command, name, "--help=bad"]]
    for name in ("--profile", "--query", "--limit") + (("--cwd",) if command == "current" else ()):
        for value in ("-", "--", "-x", "-hh", "--unknown", "--help", "+"):
            CASES.append(["session", command, name, value])
        CASES += [["session", command, name + "=", "--json"],
                  ["session", command, name + "=a", name + "=b", "--help"]]
    for values in itertools.permutations(("--json", "--id-only", "--resume-command")):
        CASES.append(["session", command, *values])
    for flags in (("--json", "--id-only", "--parent-only"),
                  ("--parent-only", "--include-subagents", "--json"),
                  ("--json", "--id-only", "--profile", "main"),
                  ("--query", "value", "--json", "--resume-command"),
                  ("--json", "--parent-only", "--id-only", "--include-subagents")):
        CASES.append(["session", command, *flags])
    for flags in (("--json", "--parent-only", "--include-subagents", "--id-only"),
                  ("--json", "--unknown"), ("--json", "extra=foo"),
                  ("--profile", "a", "--limi"), ("--limit", "1", "--limit", "bad"),
                  ("--profile", "a", "--profile"), ("--query", "--json=true"),
                  ("--query", "--help=bad"), ("--query", "--profil"),
                  ("--json", "--query", "--unknown"), ("--", "--query=value"),
                  ("--parent-only", "-xh"), ("--profile", "--", "--cwd=."),
                  ("--profile", "--", "-h")):
        CASES.append(["session", command, *flags])
for value in ("+", " 1", "1 ", "1_0", "0xff", "\u0661", "prodex session"):
    CASES.append(["session", "list", "--limit=" + value])
CASES = list(dict.fromkeys(tuple(case) for case in CASES))


def map_executable(text):
    lines = []
    for line in text.splitlines(keepends=True):
        if line.startswith("Usage: prodex "):
            line = "Usage: modex " + line[len("Usage: prodex "):]
        lines.append(line)
    return "".join(lines)


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
                            "stdout": result.stdout.decode().replace(str(root), "<FIXTURE_ROOT>"),
                            "stderr": result.stderr.decode().replace(str(root), "<FIXTURE_ROOT>"),
                            "new_paths": sorted(str(path.relative_to(root)) for path in root.rglob("*")
                                                if path not in (root / "home", root / "workspace"))})
    output = ROOT / "docs/evidence/baseline/session-cli.json"
    output.write_text(json.dumps({"schema_version": 1, "baseline_commit":
        "81c1a01933bc33f536a24452c3fd72c3f8d0b1f3", "oracle_sha256": ORACLE_SHA256,
        "reproduce": "python3 tests/capture_session_cli.py", "cases": records}, indent=2) + "\n")
    print(f"Captured {len(records)} baseline session CLI cases")


if __name__ == "__main__":
    main()
