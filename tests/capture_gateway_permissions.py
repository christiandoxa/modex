"""Retain the stricter Modex guard for group-writable synthetic Codex config."""

import hashlib
import json

from capture_gateway import ORACLE, run_case as oracle_case
from test_gateway import BASELINE_COMMIT, GATEWAY_FIXTURE, MODEX, ORACLE_SHA256, ROOT, run_case


def main():
    if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
        raise SystemExit("Pinned gateway oracle checksum mismatch")
    fixture = json.loads(GATEWAY_FIXTURE.read_text(encoding="utf-8"))
    case = next(item for item in fixture["cases"] if item["name"] == "deepseek_profileless_codex_config")
    baseline = oracle_case(
        "deepseek_group_writable_config", case["argv"][1:],
        shared_config=case["synthetic_shared_config"], loopback=True, config_mode=0o664,
    )
    actual = run_case(case, config_mode=0o664)
    if baseline["returncode"] != 1 or actual["returncode"] != 1 or baseline["upstream_requests"] or actual["upstream_requests"]:
        raise RuntimeError("gateway permission probe behavior changed")
    if "gateway provider does not expose an OpenAI-compatible proxy" not in baseline["stderr"] or "gateway Codex config requires an owned file without shared write access" not in actual["stderr"]:
        raise RuntimeError("gateway permission difference needs a new observation")
    report = {
        "classification": "UNAPPROVED_SAFE_DIFFERENCE",
        "status": "FAIL", "parity_pass": False,
        "baseline_commit": BASELINE_COMMIT, "oracle_sha256": ORACLE_SHA256,
        "modex_sha256": hashlib.sha256(MODEX.read_bytes()).hexdigest(),
        "reproduce": "python3 tests/capture_gateway_permissions.py",
        "input_config_mode": "0664",
        "baseline": baseline, "modex": actual,
        "finding": "The release reaches its no-compatible-proxy failure with group-writable synthetic config. Modex rejects that file before reading it. This stricter guard is retained as a difference, not counted as parity.",
    }
    path = ROOT / "docs/evidence/gateway-permissions-mismatch.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Gateway group-writable config difference retained: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
