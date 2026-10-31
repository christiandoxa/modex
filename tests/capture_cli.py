"""Capture version-specific official-release CLI help fixtures."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from session_oracle import sandbox_command
from test_active_baseline_01661 import ORACLE, ORACLE_SHA256, ROOT


ACTIVE_VERSION = "0.166.1"
ACTIVE_COMMIT = "4951b813ca308fb0ba7148dbc6d6aeb74b93cd32"
ACTIVE_EVIDENCE = "docs/evidence/baseline-0.166.1/reference-verification.json"
HIDDEN = ("__super-expose", "__runtime-broker", "__mcp-jsonl-bridge", "__sub-agent-exec")


def subcommands(text):
    command_section = False
    for line in text.splitlines():
        if line == "Commands:":
            command_section = True
        elif line and not line.startswith(" "):
            command_section = False
        elif command_section:
            match = re.match(r"  ([a-z_][a-z0-9_-]*)\s+", line)
            if match and match[1] != "help":
                yield match[1]


def main():
    baseline = json.loads((ROOT / "docs/baseline.json").read_text(encoding="utf-8"))["reference"]
    evidence = json.loads((ROOT / ACTIVE_EVIDENCE).read_text(encoding="utf-8"))
    if (baseline.get("tag"), baseline.get("commit"), baseline.get("evidence")) != (
        ACTIVE_VERSION, ACTIVE_COMMIT, ACTIVE_EVIDENCE,
    ):
        raise SystemExit("The active baseline is not the pinned Prodex 0.166.1 capture target")
    if (evidence.get("version"), evidence.get("commit"), evidence.get("linux_oracle_sha256")) != (
        ACTIVE_VERSION, ACTIVE_COMMIT, ORACLE_SHA256,
    ):
        raise SystemExit("The Prodex 0.166.1 reference evidence does not match the pinned capture identity")
    if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
        raise SystemExit("PRODEX_ORACLE must identify the checksum-verified Prodex 0.166.1 Linux release")

    output = ROOT / "docs/evidence/baseline-0.166.1/help"
    inventory_path = ROOT / "docs/cli-inventory-0.166.1.json"
    output.mkdir(parents=True, exist_ok=True)
    queue = [(), *((command,) for command in HIDDEN), ("super", "expose"), ("s",)]
    captured = set()
    records = []
    with tempfile.TemporaryDirectory(prefix="modex-help-oracle-") as directory:
        parent = Path(directory)
        while queue:
            command = queue.pop(0)
            if command in captured:
                continue
            captured.add(command)
            root = parent / f"case-{len(captured)}"
            root.mkdir()
            (root / "home").mkdir(mode=0o700)
            (root / "workspace").mkdir()
            arguments = [*command, "--help"]
            result = subprocess.run(sandbox_command(ORACLE, root, arguments, argv0="prodex"),
                                    capture_output=True, timeout=10, check=False)
            if result.returncode or result.stderr:
                raise SystemExit(f"Help capture failed for {command}: {result.returncode}: {result.stderr!r}")
            text = result.stdout.decode("utf-8")
            mutations = [str(path.relative_to(root)) for path in root.rglob("*")
                         if path not in (root / "home", root / "workspace")]
            if mutations:
                raise SystemExit(f"Help mutated fixture state: {command}: {mutations}")
            filename = "--".join(command) + ".txt" if command else "root.txt"
            (output / filename).write_bytes(result.stdout)
            options = sorted(set(re.findall(r"(?<![\w-])--[a-z][a-z0-9-]*", text)))
            children = list(subcommands(text))
            records.append({"command": list(command), "hidden": bool(command and command[0] in HIDDEN),
                            "options_mentioned": options, "subcommands": children,
                            "fixture": str((output / filename).relative_to(ROOT)),
                            "sha256": hashlib.sha256(result.stdout).hexdigest(),
                            "exit_code": result.returncode, "stderr": "", "file_mutations": []})
            if command not in (("super", "expose"), ("s",)):
                queue.extend((*command, child) for child in children)
    inventory = {"schema_version": 1, "baseline_version": ACTIVE_VERSION,
                 "baseline_commit": ACTIVE_COMMIT, "oracle_sha256": ORACLE_SHA256,
                 "reproduce": "python3 tests/capture_cli.py",
                 "evidence_policy": "Help output is release-specific discovery evidence; it does not establish source trace, runtime behavior, or parity.",
                 "coverage": "Visible command tree plus four hidden production helpers, super expose and s alias. Help mentions are discovery evidence; hidden flags, defaults, precedence, passthrough and runtime contracts still require source tracing.",
                 "commands": records}
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(
        f"Captured {len(records)} Prodex {ACTIVE_VERSION} help routes and "
        f"{sum(len(record['options_mentioned']) for record in records)} option mentions; "
        f"all exit 0 with no stderr or state mutation. Inventory: "
        f"{inventory_path.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
