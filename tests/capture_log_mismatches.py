"""Retain actual log observations without counting known differences as parity."""

import json
from pathlib import Path
import subprocess
import tempfile

from log_mismatches import UNAPPROVED_SAFE_DIFFERENCE, UNICODE_WHITESPACE_MATCHING_CASE
from session_oracle import sandbox_command
import test_cli
from test_cli import MODEX, ORACLE, ROOT
from test_log_redaction import run_message
from test_log_transcript import oracle as transcript_snapshot


def observe(result):
    code, stdout, stderr = result
    return {"exit_code": code, "stdout": stdout.decode(), "stderr": stderr.decode()}


def policy_snapshot(binary):
    with tempfile.TemporaryDirectory(prefix="modex-log-policy-gap-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        app = root / "home/.prodex"
        app.mkdir(mode=0o700)
        (app / "policy.toml").write_text('version = 1\n[runtime]\nlog_dir = "logs"\n')
        logs = app / "logs"
        logs.mkdir()
        (logs / "prodex-runtime-fixture.log").write_text(json.dumps({
            "timestamp": "2026-10-24T01:02:04Z", "event": "token_usage",
            "fields": {"input_tokens": "1", "output_tokens": "2"},
        }) + "\n")
        result = subprocess.run(sandbox_command(
            binary, root, ["log", "last", "--json"],
            argv0="prodex" if binary == ORACLE else "modex", environment={"TZ": "UTC"}),
            capture_output=True, timeout=10, check=False)
        return result.returncode, result.stdout, result.stderr


def main():
    test_cli.CliTests.setUpClass()
    cases = []
    for fixture in UNAPPROVED_SAFE_DIFFERENCE:
        baseline = run_message(ORACLE, fixture["input"])
        modex = run_message(MODEX, fixture["input"])
        assert baseline == (0, fixture["baseline_stdout"], b"")
        assert modex == (0, fixture["modex_stdout"], b"")
        assert fixture["secret"].encode() not in modex[1]
        cases.append({"status": "UNAPPROVED_SAFE_DIFFERENCE", "input": fixture["input"],
                      "baseline": observe(baseline), "modex": observe(modex),
                      "proposal": "Keep complete credential masking and preserve Unicode whitespace; compatibility approval remains pending."})
    fixture = UNICODE_WHITESPACE_MATCHING_CASE
    baseline = run_message(ORACLE, fixture["input"])
    modex = run_message(MODEX, fixture["input"])
    assert baseline == (0, fixture["stdout"], b"")
    assert modex == baseline
    assert fixture["secret"].encode() not in modex[1]
    cases.append({"status": "MATCHING_OUTPUT", "input": fixture["input"],
                  "baseline": observe(baseline), "modex": observe(modex),
                  "reason": "Unicode whitespace before an unquoted sensitive value matches both pinned release outputs while keeping the value masked."})
    payload = {"type": "function_call_output", "output": "\U00010400" * 8}
    baseline = transcript_snapshot("response_item", payload, ORACLE)
    modex = transcript_snapshot("response_item", payload, MODEX)
    assert baseline and modex == baseline
    cases.append({"status": "MATCHING_OUTPUT", "input": {"type": "response_item", "payload": payload},
                  "baseline_events": baseline, "modex_events": modex,
                  "reason": "The retained Deseret regression now matches with complete Unicode 17 alphanumeric data."})
    baseline = policy_snapshot(ORACLE)
    modex = policy_snapshot(MODEX)
    assert baseline[0] == 0 and b'"input_tokens":1' in baseline[1]
    assert modex == baseline
    cases.append({"status": "MATCHING_OUTPUT", "input": 'version = 1\n[runtime]\nlog_dir = "logs"\n',
                  "baseline": observe(baseline), "modex": observe(modex),
                  "reason": "The retained relative-policy log-directory regression now matches through native TOML loading."})
    report = {"baseline_commit": "72b77478a5198fc5da6b4d2253137f9cdbf43be9",
              "oracle_sha256": test_cli.ORACLE_SHA256, "cases": cases}
    path = ROOT / "docs/evidence/log-mismatches.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    matching = sum(case["status"] == "MATCHING_OUTPUT" for case in cases)
    differences = sum(case["status"] == "UNAPPROVED_SAFE_DIFFERENCE" for case in cases)
    print(f"Retained {matching} matching outputs and {differences} unapproved safe differences:", path)


if __name__ == "__main__":
    main()
