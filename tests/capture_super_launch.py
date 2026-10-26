"""Record live pinned-release observations of the guarded native Super data plane."""
import hashlib
import json
from pathlib import Path

from test_super_launch import SuperLaunchTests, event_names
from test_cli import MODEX, ORACLE, ORACLE_SHA256, ROOT


def main():
    assert hashlib.sha256(ORACLE.read_bytes()).hexdigest() == ORACLE_SHA256
    suite = SuperLaunchTests()
    cases = []
    for scenario in ("stream", "buffered", "passthrough"):
        observations = {}
        for label, binary in (("baseline", ORACLE), ("native", MODEX)):
            result, records, upstream, state = suite.run_launch(binary, scenario)
            response = next(record for record in records if record["kind"] == "response")
            launch = next(record for record in records if record["kind"] == "launch")
            assert result.returncode == 0, (label, scenario, result.stderr)
            observations[label] = {"returncode": result.returncode, "stdout": result.stdout.decode(),
                                   "response": response, "upstream": upstream, "config": launch["config"],
                                   "catalog": launch["catalog"], "private_directory_mode": launch["mode"], "overlay_leftovers": len(state["leftovers"])}
        baseline, native = observations["baseline"], observations["native"]
        checks = {"exit_and_stdout": (native["returncode"], native["stdout"]) == (baseline["returncode"], baseline["stdout"]),
                  "http_status": native["response"]["status"] == baseline["response"]["status"],
                  "upstream_target": native["upstream"][0]["path"] == baseline["upstream"][0]["path"],
                  "upstream_body": native["upstream"][0]["body"] == baseline["upstream"][0]["body"],
                  "model_catalog": native["catalog"] == baseline["catalog"],
                  "generated_config_keys": native["config"].keys() == baseline["config"].keys(),
                  "generated_config_values": all(value == baseline["config"][key] for key, value in native["config"].items()
                                                  if key not in ("projects", "model_catalog_json") and not key.endswith(".base_url"))}
        if scenario == "stream":
            checks["event_names"] = event_names(native["response"]["body"]) == event_names(baseline["response"]["body"])
        if scenario == "passthrough":
            checks["binary_body"] = native["response"]["body"] == baseline["response"]["body"]
        assert all(checks.values()), (scenario, checks)
        cases.append({"scenario": scenario, "checked_observations_match": checks,
                      "baseline_config_keys_not_yet_implemented": sorted(set(baseline["config"]) - set(native["config"])),
                      "observations": observations})
    result = {"baseline_commit": "81c1a01933bc33f536a24452c3fd72c3f8d0b1f3", "oracle_sha256": ORACLE_SHA256,
              "native_sha256": hashlib.sha256(MODEX.read_bytes()).hexdigest(),
              "command": "python3 tests/capture_super_launch.py", "whole_command_parity": "BLOCKED",
              "scope": "Compiled production Modex, synthetic external Codex/provider peers, isolated HOME/env/config/storage/ephemeral loopback ports. Host PID/network namespace; no real credentials, account login or paid provider traffic.",
              "limitations": ["Compared named data-plane observations only; dynamic IDs/times and complete envelopes are not normalized into a PASS.",
                              "Baseline launch output/config/catalog/defaults/storage/locks/companions remain incomplete; real Codex distributions are unverified.",
                              "All six full release platform qualifications remain BLOCKED."], "cases": cases}
    output = ROOT / "docs/evidence/native-super-data-plane.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print("Recorded three live data-plane comparisons; whole-command parity BLOCKED.")


if __name__ == "__main__":
    main()
