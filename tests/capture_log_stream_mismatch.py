"""Capture the unapproved stream_payload redaction difference as JSON evidence."""

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_log_stream_redaction import RECORDS, SECRETS, VISIBLE_MARKERS, capture_trace


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/evidence/log-stream-mismatch.json"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode_output(trace):
    return {
        "returncode": trace["returncode"],
        "termination": {
            "signal": "SIGTERM",
            "method": "harness cleanup after startup and append outputs were collected",
            "natural_completion": False,
        },
        "stdout_utf8": trace["stdout"].decode("utf-8"),
        "stdout_base64": base64.b64encode(trace["stdout"]).decode("ascii"),
        "stderr_utf8": trace["stderr"].decode("utf-8"),
        "stderr_base64": base64.b64encode(trace["stderr"]).decode("ascii"),
    }


def main():
    if sha256(ORACLE) != ORACLE_SHA256:
        raise SystemExit("Pinned Prodex oracle checksum mismatch")
    oracle_sha256 = sha256(ORACLE)
    modex_sha256 = sha256(MODEX)
    modes = {}
    for mode in ("json", "plain"):
        baseline = capture_trace(ORACLE, mode)
        actual = capture_trace(MODEX, mode)
        baseline_bytes = baseline["stdout"] + baseline["stderr"]
        actual_bytes = actual["stdout"] + actual["stderr"]
        if baseline["stdout"] == actual["stdout"]:
            raise SystemExit(f"Expected an unapproved {mode} stream difference")
        if any(marker.encode() not in baseline_bytes or marker.encode() not in actual_bytes
               for marker in VISIBLE_MARKERS):
            raise SystemExit(f"Missing visible marker in {mode} stream output")
        if any(secret.encode() not in baseline_bytes or secret.encode() in actual_bytes
               for secret in SECRETS):
            raise SystemExit(f"Synthetic secret masking mismatch in {mode} stream output")
        modes[mode] = {"oracle": encode_output(baseline), "modex": encode_output(actual)}

    evidence = {
        "classification": "UNAPPROVED_SAFE_DIFFERENCE",
        "parity_pass": False,
        "approval": "not approved",
        "scope": "log stream stream_payload source and text fields",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "oracle": {
            "release": "Prodex 0.439.0",
            "path": str(ORACLE),
            "sha256": oracle_sha256,
        },
        "baseline_reference_commit": "433aad44bb249d5c25a231a6b06c2fa522a39a1f",
        "modex": {
            "binary": str(MODEX.relative_to(ROOT)),
            "sha256": modex_sha256,
        },
        "fixture": {
            "credentials_are_synthetic": True,
            "runtime_records": list(RECORDS),
            "secret_sentinels": list(SECRETS),
            "preserved_markers": list(VISIBLE_MARKERS),
            "delivery": "one stream_payload record at startup and one appended to the tracked runtime log",
        },
        "modes": modes,
        "decision": "Oracle output exposes synthetic Authorization bearer and API key values. Modex redacts them in source and text. Keep this mismatch visible; do not count it as parity until separately approved.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(OUTPUT.relative_to(ROOT))
    print(f"oracle sha256: {oracle_sha256}")
    print(f"modex sha256: {modex_sha256}")


if __name__ == "__main__":
    main()
