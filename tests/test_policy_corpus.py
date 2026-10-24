"""Differential runtime-policy parsing over the pinned TOML 1.1 input corpus."""

import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_cli import ORACLE, ORACLE_SHA256, ROOT


MODEX = ROOT / "build/modex"
CORPUS = ROOT / "tests/fixtures/toml11"
MANIFEST = CORPUS / "files-toml-1.1.0"
RESULTS = ROOT / "test-results/policy-corpus"
POLICY_PREFIX = b'version=1\n[runtime]\nlog_dir="chosen"\n[future]\n'
TOKEN_EVENT = (
    b'{"timestamp":"2026-10-24T01:02:04Z","event":"token_usage",'
    b'"fields":{"input_tokens":"101","output_tokens":"4"}}\n'
)
TMP_EVENT = (
    b'{"timestamp":"2026-10-24T01:02:04Z","event":"token_usage",'
    b'"fields":{"input_tokens":"202","output_tokens":"4"}}\n'
)


def verify_checksums():
    for line in (CORPUS / "SHA256SUMS").read_text().splitlines():
        digest, relative = line.split("  ", 1)
        path = CORPUS / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise AssertionError(f"fixture checksum mismatch: {relative}")


def run(binary, policy, base, label):
    root = base / label
    home = root / "home"
    prodex = root / ".prodex"
    temporary = root / "tmp"
    workspace = root / "workspace"
    home.mkdir(parents=True, mode=0o700)
    prodex.mkdir(mode=0o700)
    temporary.mkdir()
    workspace.mkdir()
    (prodex / "policy.toml").write_bytes(policy)
    chosen = prodex / "chosen"
    chosen.mkdir()
    (chosen / "prodex-runtime-fixture.log").write_bytes(TOKEN_EVENT)
    (temporary / "prodex-runtime-fixture.log").write_bytes(TMP_EVENT)
    command = sandbox_command(
        binary,
        root,
        ["log", "last", "--json"],
        argv0="prodex" if binary == ORACLE else "modex",
        environment={"PRODEX_HOME": str(prodex), "TMPDIR": str(temporary)},
    )
    result = subprocess.run(
        command,
        capture_output=True,
        timeout=10,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


class PolicyCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file():
            raise AssertionError("Set PRODEX_ORACLE to the verified official 0.439.0 Linux binary")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("The Prodex oracle does not match the frozen release checksum")
        verify_checksums()
        cls.cases = [
            relative.strip()
            for relative in MANIFEST.read_text().splitlines()
            if relative.strip().endswith(".toml")
        ]
        if len(cls.cases) != 712:
            raise AssertionError(f"unexpected TOML 1.1 corpus size: {len(cls.cases)}")

    def test_all_toml_11_manifest_files_match_runtime_policy_load(self):
        mismatches = []
        selected_counts = {101: 0, 202: 0}
        RESULTS.mkdir(parents=True, exist_ok=True)
        for index, relative in enumerate(self.cases):
            fixture = CORPUS / relative
            if not fixture.is_file():
                self.fail(f"manifest fixture is missing: {relative}")
            policy = POLICY_PREFIX + fixture.read_bytes()
            with tempfile.TemporaryDirectory(prefix="policy-corpus-", dir=RESULTS) as temporary:
                base = Path(temporary)
                baseline = run(ORACLE, policy, base, "oracle")
                actual = run(MODEX, policy, base, "modex")
            self.assertEqual(baseline[0], 0, (relative, baseline[2]))
            self.assertEqual(baseline[2], b"", relative)
            self.assertTrue(baseline[1], f"oracle must observe a fixture log: {relative}")
            selected = json.loads(baseline[1])["input_tokens"]
            self.assertIn(selected, selected_counts, relative)
            selected_counts[selected] += 1
            if baseline != actual:
                mismatches.append((relative, policy, baseline, actual))

        if mismatches:
            mismatch_root = RESULTS / "mismatches"
            for relative, policy, baseline, actual in mismatches:
                case = mismatch_root / Path(relative).with_suffix("")
                case.mkdir(parents=True, exist_ok=True)
                (case / "policy.toml").write_bytes(policy)
                (case / "observations.json").write_text(json.dumps({
                    "fixture": relative,
                    "oracle": {
                        "exit_code": baseline[0],
                        "stdout_base64": base64.b64encode(baseline[1]).decode("ascii"),
                        "stderr_base64": base64.b64encode(baseline[2]).decode("ascii"),
                    },
                    "modex": {
                        "exit_code": actual[0],
                        "stdout_base64": base64.b64encode(actual[1]).decode("ascii"),
                        "stderr_base64": base64.b64encode(actual[2]).decode("ascii"),
                    },
                }, indent=2) + "\n")
            self.fail(
                f"{len(mismatches)} of {len(self.cases)} TOML corpus policies differ; "
                f"exact inputs and outputs saved under {mismatch_root}: "
                + ", ".join(relative for relative, *_ in mismatches[:20])
            )

        (RESULTS / "summary.json").write_text(json.dumps({
            "corpus": str(MANIFEST.relative_to(ROOT)),
            "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
            "oracle_sha256": ORACLE_SHA256,
            "policy_cases": len(self.cases),
            "mismatches": 0,
            "configured_log_directory_selected": selected_counts[101],
            "temporary_log_directory_selected": selected_counts[202],
        }, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
