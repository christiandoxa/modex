"""Pinned-source policy comparisons; no account pool or live recovery claim."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_COMMIT = "72b77478a5198fc5da6b4d2253137f9cdbf43be9"
BUILD_ROOT = Path(os.environ.get("BUILD_DIR", ROOT / "build"))
REFERENCE_CACHE = Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
REFERENCE = Path(os.environ.get(
    "MODEX_REFERENCE_04392_DIR",
    REFERENCE_CACHE / "references" / f"prodex-{REFERENCE_COMMIT}",
))
SOURCE_HASHES = {
    'mojo/prodex_core/candidate_decision.mojo': 'bd3a8176425a29c8937e8c63dd8aae3cf585bed9be8827dd6558247d3a1a6fe0',
    'mojo/prodex_core/runtime_responses_attempt.mojo': 'b07576c76cc518f1df38a222f5895bb0a5729ed55d04d7425fadc56a691c5861',
    'crates/prodex-app/src/runtime_proxy/quota/gate.rs': '72f2066eaf0814738905506932cfdd36ad2fe91f6eea51eadd56f47ac7180be1',
    'crates/prodex-app/src/runtime_proxy/responses.rs': 'e3f24a9d208550fdabbfc1d68abcb6d8c9c4844f0bb7dc32e72eee0017b3c740',
    'crates/prodex-app/src/runtime_proxy/websocket_message/setup.rs': '95552430285f88ff71a61613f7b492b29d680a932fb9cd821d384d9d2f2fd5dc',
}

# Test-only adapter: the immutable Rust gate combines these Mojo decisions.
ORACLE_SOURCE = '''from std.memory import Pointer
from candidate_decision import prodex_runtime_quota_selection_policy_v1, prodex_runtime_waitable_candidate_eligible_v1
from runtime_responses_attempt import prodex_runtime_responses_attempt_retry_signal_v1

def exhausted(status: Int) raises -> Bool:
    var output: Int64 = -1
    assert prodex_runtime_quota_selection_policy_v1(2, 0, Int64(status), 0, 0, 0, 1, Pointer(to=output)) == 0
    return output == 1

def main() raises:
    for mask in range(32):
        var context = Int64((mask >> 4) & 1)
        var auth = Int64((mask >> 3) & 1)
        var runtime = Int64((mask >> 2) & 1)
        var auth_failure = Int64((mask >> 1) & 1)
        var quarantined = Int64(mask & 1)
        for five in range(5):
            for weekly in range(5):
                var blocked = quarantined == 1 or exhausted(five) or exhausted(weekly)
                var eligible = prodex_runtime_waitable_candidate_eligible_v1(3, context, auth, runtime, 0, 0, 0, auth_failure, 0, 0, 0, Int64(blocked))
                assert eligible >= 0
                print("A", context, auth, runtime, auth_failure, quarantined, five, weekly, eligible)
    for mask in range(32):
        var hard = Int64((mask >> 4) & 1)
        var owner = Int64((mask >> 3) & 1)
        var history = Int64((mask >> 2) & 1)
        var retry = Int64((mask >> 1) & 1)
        var alternate = Int64(mask & 1)
        for five in range(5):
            for weekly in range(5):
                var signal = prodex_runtime_responses_attempt_retry_signal_v1(1, history, owner, alternate)
                assert signal >= 0
                var decision = hard == 1 and retry == 1 and signal == 1 and (exhausted(five) or exhausted(weekly))
                print("D", hard, owner, history, retry, alternate, five, weekly, Int(decision))
    for busy in range(2):
        for cooling in range(2):
            print("B", busy, cooling, prodex_runtime_waitable_candidate_eligible_v1(3, 1, 1, 1, 0, Int64(busy), Int64(cooling), 0, 0, 0, 0, 0))
'''


class QuotaHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for relative, expected in SOURCE_HASHES.items():
            path = REFERENCE / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise AssertionError(f'0.439.2 source checksum mismatch: {relative}')
        build_dir = BUILD_ROOT / "tests"
        build_dir.mkdir(parents=True, exist_ok=True)
        cls.isolation = tempfile.TemporaryDirectory(dir=build_dir)
        cls.addClassCleanup(cls.isolation.cleanup)
        cls.env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": cls.isolation.name,
            "XDG_CONFIG_HOME": cls.isolation.name,
            "XDG_CACHE_HOME": cls.isolation.name,
            "XDG_DATA_HOME": cls.isolation.name,
            "TMPDIR": cls.isolation.name,
            "LANG": "C.UTF-8",
        }
        cls.driver = build_dir / "test_quota_handoff_04392"
        if not cls.driver.is_file():
            raise AssertionError('Run make unit before quota policy comparisons')
        source = Path(cls.isolation.name) / "oracle.mojo"
        source.write_text(ORACLE_SOURCE)
        oracle = source.with_suffix('')
        subprocess.run(
            [
                os.environ.get("MOJO", "mojo"), "build", "-O3",
                "--target-cpu=x86-64-v3", "-I", str(REFERENCE / "mojo/prodex_core"),
                str(source), "-o", str(oracle),
            ],
            cwd=ROOT,
            env=cls.env,
            check=True,
        )
        output = subprocess.check_output([str(cls.driver), "vectors"], text=True, env=cls.env)
        cls.vectors = [line.split() for line in output.splitlines()]
        output = subprocess.check_output([str(oracle)], text=True, env=cls.env)
        cls.reference_vectors = [line.split() for line in output.splitlines()]

    def test_1600_vectors_match_current_pinned_mojo_decisions(self):
        self.assertEqual(len(self.vectors), 1601)
        self.assertEqual(len(self.reference_vectors), 1604)
        self.assertEqual(self.vectors[:-1], self.reference_vectors[:1600])
        self.assertEqual(self.vectors[-1], ["INVALID", "1"])

    def test_weekly_only_unknown_quota_and_exhaustion_are_distinct(self):
        rows = {tuple(map(int, row[1:-1])): int(row[-1])
                for row in self.vectors if row[0] == "A"}
        for five, weekly, expected in ((0, 0, 1), (0, 1, 1), (0, 3, 0), (3, 1, 0)):
            self.assertEqual(rows[(1, 1, 1, 0, 0, five, weekly)], expected)

    def test_recoverability_with_busy_cooling_and_expired_holds(self):
        # These are signal-eligibility fixtures, never a production admission test.
        for row in self.reference_vectors[1600:]:
            self.assertEqual(row[0], 'B')
            self.assertEqual(row[-1], '1')
        rows = {tuple(map(int, row[1:-1])): int(row[-1])
                for row in self.vectors if row[0] == "A"}
        now = 100
        for hold_until in (None, 99, 100, 101):
            active = hold_until is not None and hold_until > now
            self.assertEqual(rows[(1, 1, 1, 0, int(active), 0, 1)], int(not active))


if __name__ == "__main__":
    unittest.main()
