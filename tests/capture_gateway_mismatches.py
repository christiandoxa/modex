#!/usr/bin/env python3
"""Retain public gateway startup output and filesystem parity differences."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from test_gateway import (
    BASELINE_COMMIT,
    GATEWAY_FIXTURE,
    MODEX,
    ORACLE_SHA256,
    ROOT,
    filesystem_mismatches,
    mode_octal,
    run_case,
)

ORACLE = Path("/home/doxa/.cache/modex/oracles/0.439.0/prodex-x86_64-unknown-linux-gnu")
OUTPUT = ROOT / "docs/evidence/gateway-mismatch.json"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_text(text):
    return text.replace("Usage: prodex", "Usage: modex")


def artifact_summary(items):
    return [
        {
            "path": item["path"],
            "baseline_mode": mode_octal(item["baseline_after"]),
            "baseline_size": item["baseline_after"]["size"],
        }
        for item in items
        if item["actual_after"] is None
    ]


def observe(case, actual):
    return {
        "returncode": actual["returncode"],
        "stdout": actual["stdout"],
        "stderr": actual["stderr"],
        "upstream_requests": actual["upstream_requests"],
        "filesystem_delta": actual["filesystem_delta"],
    }


def main():
    if sha256(ORACLE) != ORACLE_SHA256:
        raise SystemExit("Pinned Prodex gateway oracle checksum mismatch")
    if not MODEX.is_file():
        raise SystemExit(f"Modex gateway binary is missing: {MODEX}")

    fixture = json.loads(GATEWAY_FIXTURE.read_text(encoding="utf-8"))
    if fixture["oracle_sha256"] != ORACLE_SHA256:
        raise SystemExit("Gateway fixture does not identify the pinned Prodex oracle")
    if fixture["baseline_commit"] != BASELINE_COMMIT:
        raise SystemExit("Gateway fixture does not identify the frozen baseline commit")

    cases = []
    for name in ("deepseek_empty_home", "deepseek_profileless_codex_config"):
        baseline = next(item for item in fixture["cases"] if item["name"] == name)
        actual = run_case(baseline)
        comparisons = {
            "exit_code": "PASS" if actual["returncode"] == baseline["returncode"] else "FAIL",
            "stdout": "PASS" if actual["stdout"] == expected_text(baseline["stdout"]) else "FAIL",
            "stderr": "PASS" if actual["stderr"] == expected_text(baseline["stderr"]) else "FAIL",
            "upstream_requests": "PASS" if actual["upstream_requests"] == baseline["upstream_requests"] else "FAIL",
        }
        mismatches = filesystem_mismatches(baseline["filesystem_delta"], actual["filesystem_delta"])
        comparisons["filesystem_delta"] = "FAIL" if mismatches else "PASS"
        status = "FAIL" if "FAIL" in comparisons.values() else "PASS"
        cases.append({
            "name": name,
            "status": status,
            "comparisons": comparisons,
            "baseline": {
                "returncode": baseline["returncode"],
                "stdout": baseline["stdout"],
                "stderr": baseline["stderr"],
                "upstream_requests": baseline["upstream_requests"],
                "filesystem_delta": baseline["filesystem_delta"],
            },
            "modex": observe(baseline, actual),
            "filesystem_mismatches": mismatches,
            "missing_artifacts": artifact_summary(mismatches),
        })

    overall_status = "FAIL" if any(case["status"] == "FAIL" for case in cases) else "PASS"
    evidence = {
        "schema_version": 1,
        "classification": "RETAINED_PARITY_MISMATCH" if overall_status == "FAIL" else "MATCHING_CAPTURED_STARTUP_SCOPE",
        "overall_status": overall_status,
        "parity_pass": overall_status == "PASS",
        "full_gateway_parity_claimed": False,
        "scope": "Public gateway startup output, upstream attempts, and filesystem deltas for two frozen DeepSeek failure cases.",
        "capture_command": "python3 tests/capture_gateway_mismatches.py",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "oracle": {
            "release": "Prodex 0.439.0",
            "path": str(ORACLE),
            "sha256": ORACLE_SHA256,
        },
        "baseline_reference_commit": BASELINE_COMMIT,
        "baseline_fixture": str(GATEWAY_FIXTURE.relative_to(ROOT)),
        "modex": {
            "binary": str(MODEX.relative_to(ROOT)),
            "sha256": sha256(MODEX),
        },
        "cases": cases,
        "decision": (
            "Startup exit codes, stdout, stderr, and zero upstream requests match. "
            "The frozen build creates four runtime lock/housekeeping files that "
            "Modex does not create. Retain this filesystem mismatch as FAIL evidence; "
            "this capture does not establish full gateway parity."
        ) if overall_status == "FAIL" else (
            "Captured startup cases match. This limited capture does not establish full gateway parity."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{overall_status}: {OUTPUT.relative_to(ROOT)}")
    for case in cases:
        print(f"{case['name']}: {case['status']} {case['comparisons']}")
        for item in case["missing_artifacts"]:
            print(f"missing {item['path']} mode={item['baseline_mode']} size={item['baseline_size']}")
    if overall_status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
