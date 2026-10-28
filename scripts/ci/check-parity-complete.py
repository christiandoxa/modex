#!/usr/bin/env python3
"""Make a separate, strict verdict from the full parity inventory."""

import json
from collections import Counter
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
PARITY = ROOT / "docs/parity.json"
BASELINE = ROOT / "docs/baseline.json"
REQUIRED_TARGETS = {
    "x86_64-unknown-linux-gnu",
    "aarch64-unknown-linux-gnu",
    "x86_64-apple-darwin",
    "aarch64-apple-darwin",
    "x86_64-pc-windows-msvc",
    "aarch64-pc-windows-msvc",
}


def evidence_exists(value: object) -> bool:
    if not isinstance(value, str):
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts and (ROOT / path).is_file()


def main() -> int:
    parity = json.loads(PARITY.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    targets = set(baseline["reference"]["release_targets"])
    failures = []
    reference_commit = baseline["reference"]["commit"]
    if parity.get("baseline_commit") != reference_commit:
        failures.append("parity inventory does not match the active baseline commit")
    if targets != REQUIRED_TARGETS:
        failures.append("baseline target denominator does not contain the six required release targets")
        targets = REQUIRED_TARGETS
    contracts = parity.get("contracts", [])
    if not parity.get("inventory_complete"):
        failures.append("the contract inventory is marked incomplete")
    if not contracts:
        failures.append("the contract inventory is empty")
    contract_statuses = Counter()
    platform_failures = Counter()
    malformed_platforms = []
    for contract in contracts:
        contract_id = contract.get("id", "<missing id>")
        contract_status = contract.get("status")
        if contract_status != "PASS":
            contract_statuses[contract_status or "MISSING"] += 1
        statuses = contract.get("platform_status", {})
        if contract_status == "PASS" or "PASS" in statuses.values():
            trace = contract.get("baseline", {})
            if trace.get("source_commit") != reference_commit or trace.get("target_trace_verified") is not True:
                failures.append(f"{contract_id}: PASS requires a verified trace against the active baseline")
        if contract_status == "PASS":
            evidence = contract.get("evidence", [])
            if not evidence or any(not evidence_exists(path) for path in evidence):
                failures.append(f"{contract_id}: PASS requires existing evidence files")
        if set(contract.get("platforms", [])) != targets:
            malformed_platforms.append(contract_id)
        for target in sorted(targets):
            status = statuses.get(target)
            if status != "PASS":
                platform_failures[f"{target}={status or 'MISSING'}"] += 1
    if contract_statuses:
        summary = ", ".join(f"{status}: {count}" for status, count in sorted(contract_statuses.items()))
        failures.append(f"{sum(contract_statuses.values())}/{len(contracts)} contracts are not PASS ({summary})")
    total_platforms = len(contracts) * len(targets)
    if platform_failures:
        summary = ", ".join(f"{item}: {count}" for item, count in sorted(platform_failures.items()))
        failures.append(f"{sum(platform_failures.values())}/{total_platforms} platform obligations are not PASS ({summary})")
    if malformed_platforms:
        failures.append(f"{len(malformed_platforms)} contracts do not retain exactly the six required release targets")
    qualification = parity.get("release_qualification", {})
    qualification_failures = []
    for target in sorted(targets):
        item = qualification.get(target, {})
        status = item.get("status")
        if status != "PASS":
            qualification_failures.append(f"{target}={status or 'MISSING'}")
        elif not item.get("evidence") or any(not evidence_exists(path) for path in item["evidence"]):
            qualification_failures.append(f"{target}=PASS_WITHOUT_EVIDENCE")
    if qualification_failures:
        failures.append("release qualification is not PASS: " + ", ".join(qualification_failures))
    if failures:
        print("Parity completeness: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Parity completeness: PASS ({len(contracts)} contracts, {len(targets)} targets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
