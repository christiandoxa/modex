"""Retain complete reproducible baseline/Modex session mismatches outside PASS tests."""

import json
from pathlib import Path
import subprocess
import tempfile

from session_oracle import fixture, sandbox_command
from test_cli import MODEX, ORACLE, ROOT


def main():
    records = []
    with tempfile.TemporaryDirectory(prefix="modex-session-mismatch-") as directory:
        parent = Path(directory)
        for case in ("nonobject-followup", "startup-effects", "state-load", "text-output"):
            observations = {}
            for label, binary in (("baseline", ORACLE), ("modex", MODEX)):
                root = parent / f"{case}-{label}"
                root.mkdir()
                fixture(root)
                original = next((root / "home/.codex").rglob("*.jsonl"))
                if case == "nonobject-followup":
                    original.write_text(original.read_text() + "[]\nnull\n")
                if case == "state-load":
                    state = root / "home/.prodex"
                    state.mkdir(mode=0o700)
                    (state / "state.json").write_text('{"schema_version":1,"profiles":{}}\n')
                arguments = ["session", "list"]
                if case != "text-output":
                    arguments.append("--json")
                before = {str(path.relative_to(root)) for path in root.rglob("*")}
                result = subprocess.run(sandbox_command(binary, root, arguments),
                                        capture_output=True, timeout=10, check=False)
                after = {str(path.relative_to(root)) for path in root.rglob("*")}
                observations[label] = {
                    "exit_code": result.returncode,
                    "stdout": result.stdout.decode("utf-8", "replace").replace(str(root), "<FIXTURE_ROOT>"),
                    "stderr": result.stderr.decode("utf-8", "replace").replace(str(root), "<FIXTURE_ROOT>"),
                    "new_paths": sorted(after - before),
                }
            output_fields = ("exit_code", "stdout", "stderr")
            output_matches = all(observations["baseline"][field] == observations["modex"][field]
                                 for field in output_fields)
            records.append({"case": case, "arguments": arguments, "observations": observations,
                            "output_matches": output_matches,
                            "status": "UNAPPROVED_SAFE_DIFFERENCE" if case == "nonobject-followup" else "FAIL"})
    output = ROOT / "docs/evidence/session-mismatches.json"
    output.write_text(json.dumps({"schema_version": 1, "reproduce": "python3 tests/session_mismatches.py",
                                 "cases": records}, indent=2) + "\n")
    for record in records:
        suffix = " (output matches; side effects differ)" if record["output_matches"] else ""
        print(f"{record['case']}: {record['status']}{suffix}")


if __name__ == "__main__":
    main()
