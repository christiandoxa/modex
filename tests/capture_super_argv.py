#!/usr/bin/env python3
"""Capture frozen Super URL validation using isolated synthetic arguments."""

import hashlib
import json
from pathlib import Path

from test_cli import ORACLE, ORACLE_SHA256, ROOT
from test_super_cli import isolated_super


BASELINE_COMMIT = "81c1a01933bc33f536a24452c3fd72c3f8d0b1f3"
OUTPUT = ROOT / "tests/fixtures/super-argv/cases.json"
CASES = [
    ("url_credentials", ["super", "exec", "--url", "http://synthetic-user:synthetic-secret@127.0.0.1:8131"]),
    ("url_query", ["super", "exec", "--url", "http://127.0.0.1:8131/v1?api_key=synthetic-secret"]),
    ("url_fragment", ["super", "exec", "--url", "https://127.0.0.1:8131/v1#token=synthetic-secret"]),
    ("url_non_http", ["super", "exec", "--url", "ftp://127.0.0.1:8131"]),
    ("url_missing_host", ["super", "exec", "--url", "http:///missing-host"]),
    ("base_url_credentials", ["super", "exec", "--base-url", "https://synthetic-user:synthetic-secret@example.test/v1"]),
    ("sub_agent_url_credentials", ["super", "exec", "--sub-agent", "--sub-agent-provider", "local", "--sub-agent-url", "https://synthetic-user:synthetic-secret@127.0.0.1:8131"]),
    ("sub_agent_concurrency_zero", ["super", "exec", "--sub-agent", "--sub-agent-max-concurrency", "0"]),
    ("sub_agent_concurrency_above_limit", ["super", "exec", "--sub-agent", "--sub-agent-max-concurrency", "65"]),
    ("sub_agent_concurrency_syntax", ["super", "exec", "--sub-agent", "--sub-agent-max-concurrency", "unknown"]),
    ("sub_agent_concurrency_overflow", ["super", "exec", "--sub-agent", "--sub-agent-max-concurrency", "99999999999999999999"]),
]


def main():
    if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
        raise SystemExit("The oracle checksum does not match the frozen official release")
    cases = []
    for name, arguments in CASES:
        result, _ = isolated_super(ORACLE, arguments)
        cases.append({"name": name, "argv": arguments, "returncode": result.returncode,
                      "stdout": result.stdout.decode("utf-8"),
                      "stderr": result.stderr.decode("utf-8")})
    capture = {
        "schema_version": 1,
        "baseline_commit": BASELINE_COMMIT,
        "oracle_version": "0.439.1",
        "oracle_sha256": ORACLE_SHA256,
        "capture_harness": "tests/capture_super_argv.py",
        "scope": "Super URL validation, non-disclosure for synthetic credential/query inputs, and sub-agent concurrency parsing.",
        "isolation": "Each case uses an isolated HOME, workspace and PRODEX_HOME in a temporary root; bubblewrap unshares the network namespace.",
        "network_isolated": True,
        "cases": cases,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(capture, indent=2, ensure_ascii=False) + "\n")
    print(f"Captured {len(cases)} isolated Super URL validation cases from Prodex 0.439.1")


if __name__ == "__main__":
    main()
