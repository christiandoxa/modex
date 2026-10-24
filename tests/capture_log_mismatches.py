"""Retain actual log observations without counting known differences as parity."""

import json
from pathlib import Path
import subprocess
import tempfile

from log_mismatches import UNAPPROVED_SAFE_DIFFERENCE
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
    payload = {"type": "function_call_output", "output": "\U00010400" * 8}
    baseline = transcript_snapshot("response_item", payload, ORACLE)
    modex = transcript_snapshot("response_item", payload, MODEX)
    assert baseline and not modex
    cases.append({"status": "FAIL", "input": {"type": "response_item", "payload": payload},
                  "baseline_events": baseline, "modex_events": modex,
                  "reason": "Binary-text classification lacks complete Unicode alphanumeric data."})
    baseline = policy_snapshot(ORACLE)
    modex = policy_snapshot(MODEX)
    assert baseline[0] == 0 and b'"input_tokens":1' in baseline[1]
    assert modex == (1, b"", b"Error: runtime log policy loading is not implemented\n")
    cases.append({"status": "FAIL", "input": 'version = 1\n[runtime]\nlog_dir = "logs"\n',
                  "baseline": observe(baseline), "modex": observe(modex),
                  "reason": "Policy-backed runtime log directory resolution is unfinished."})
    report = {"baseline_commit": "433aad44bb249d5c25a231a6b06c2fa522a39a1f",
              "oracle_sha256": test_cli.ORACLE_SHA256, "cases": cases}
    path = ROOT / "docs/evidence/log-mismatches.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("Retained 2 FAIL cases and 4 unapproved safe differences:", path)


if __name__ == "__main__":
    main()
