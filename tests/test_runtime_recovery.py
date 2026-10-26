"""Deterministic native policy checks; no services, credentials or account state."""
import copy
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "build/tests/runtime_recovery_driver"
REFERENCE = Path("/home/doxa/.cache/modex/references/prodex-81c1a01933bc33f536a24452c3fd72c3f8d0b1f3")
SESSION = "00000000-0000-0000-0000-000000000001"


class RuntimeRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DRIVER.exists():
            raise RuntimeError("build tests/runtime_recovery_driver.mojo before running recovery tests")
        cls.isolation = tempfile.TemporaryDirectory(dir=ROOT / "build/tests")
        cls.addClassCleanup(cls.isolation.cleanup)
        cls.env = {"PATH": os.environ.get("PATH", ""), "HOME": cls.isolation.name,
                   "XDG_CONFIG_HOME": cls.isolation.name, "XDG_CACHE_HOME": cls.isolation.name,
                   "XDG_DATA_HOME": cls.isolation.name, "TMPDIR": cls.isolation.name,
                   "LANG": "C.UTF-8"}

    def wire(self, thread, goal, flags, budget=100, used=10, driver=DRIVER):
        return int(subprocess.check_output([str(driver), "wire", thread, goal, str(flags), str(budget), str(used)], text=True, env=self.env))

    def plan(self, thread=None, goal=None, init=None, expected=False, session=SESSION, home="/synthetic/codex", workspace="/synthetic/work"):
        if thread is None:
            thread = dict(id=SESSION, sessionId=SESSION, ephemeral=False,
                          canAcceptDirectInput=True, cwd="/synthetic/work", status={"type": "idle"})
        if goal is None:
            goal = {"goal": None}
        if init is None:
            init = {"codexHome": "/synthetic/codex"}
        args = [str(DRIVER), "plan", json.dumps(init), json.dumps({"thread": thread}),
                json.dumps(goal), home, workspace, session, str(int(expected))]
        return int(subprocess.check_output(args, text=True, env=self.env))

    def test_identity_and_quiescence(self):
        base = dict(id=SESSION, sessionId=SESSION, ephemeral=False,
                    canAcceptDirectInput=True, cwd="/synthetic/work", status={"type": "idle"})
        self.assertEqual(self.plan(), 3)
        self.assertEqual(self.plan(expected=True), 1)
        self.assertEqual(self.plan(goal={}), 0)
        for key, bad in [("id", "other"), ("sessionId", "other"), ("ephemeral", True),
                         ("ephemeral", 0), ("canAcceptDirectInput", False), ("canAcceptDirectInput", 1),
                         ("cwd", "/other"), ("cwd", "/synthetic/work\x00")]:
            thread = copy.deepcopy(base)
            thread[key] = bad
            with self.subTest(key=key, bad=bad):
                self.assertEqual(self.plan(thread=thread), 1)
        for status in ["active", "notLoaded", "Idle", "", "unknown"]:
            thread = copy.deepcopy(base)
            thread["status"] = {"type": status}
            self.assertEqual(self.plan(thread=thread), 0)
        self.assertEqual(self.plan(init={}), 1)
        self.assertEqual(self.plan(session="not-a-uuid"), 1)
        self.assertEqual(self.plan(goal={"goal": {"threadId": "other", "status": "active"}}), 1)

    def test_path_identity_with_missing_children_and_symlinks(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build/tests") as temporary:
            root = Path(temporary)
            (root / "actual").mkdir()
            (root / "link").symlink_to(root / "actual", target_is_directory=True)
            home = str(root / "actual/missing/home")
            observed = str(root / "link/missing/unused/../home")
            self.assertEqual(self.plan(init={"codexHome": observed}, home=home), 3)
            self.assertEqual(self.plan(init={"codexHome": observed + "/other"}, home=home), 1)

    def test_negative_zero_is_not_a_serde_signed_integer(self):
        goal = '{"goal":{"threadId":"' + SESSION + '","status":"blocked","tokenBudget":100,"tokensUsed":-0}}'
        thread = dict(id=SESSION, sessionId=SESSION, ephemeral=False,
                      canAcceptDirectInput=True, cwd="/synthetic/work", status={"type": "idle"})
        result = subprocess.check_output([str(DRIVER), "plan", '{"codexHome":"/synthetic/codex"}',
                                          json.dumps({"thread": thread}), goal, "/synthetic/codex",
                                          "/synthetic/work", SESSION, "0"], text=True, env=self.env)
        self.assertEqual(int(result), 1)

    def test_budget_types_and_boundaries(self):
        for budget, used, expected in [(100, 99, 2), (100, 100, 1), (0, 0, 1), (-1, 0, 1),
                                      (100, -1, 1), (100, None, 1), (100, True, 1),
                                      (100.0, 0, 1), ("100", 0, 1), (2**63, 0, 1),
                                      (2**63-1, 2**63-2, 2), (100, 2**63, 1), (None, -10, 2)]:
            goal = dict(threadId=SESSION, status="blocked", tokenBudget=budget, tokensUsed=used)
            with self.subTest(budget=budget, used=used):
                self.assertEqual(self.plan(goal={"goal": goal}), expected)
        for status in ["paused", "budgetLimited", "complete", "unknown", "Active"]:
            self.assertEqual(self.plan(goal={"goal": dict(threadId=SESSION, status=status)}), 1)
        self.assertEqual(self.plan(goal={"goal": dict(threadId=SESSION, status="usageLimited")}), 2)

    @unittest.skipUnless((REFERENCE / "mojo/prodex_core/launch_config.mojo").exists(), "pinned reference unavailable")
    def test_differential_pinned_mojo_policy(self):
        # Build a test-only adapter outside the read-only reference; product never links it.
        source = ROOT / "build/tests/runtime_recovery_oracle.mojo"
        source.write_text('''from std.sys import argv
from std.memory.alloc import alloc, dealloc, Layout
from launch_args_common import LaunchArgView
from launch_config import prodex_launch_native_recovery_wire_v1

def main() raises:
    var args = argv()
    var thread = String(args[2])
    var goal = String(args[3])
    var flags = Int64(Int(args[4]))
    var budget = Int64(Int(args[5]))
    var used = Int64(Int(args[6]))
    var storage = alloc(Layout[LaunchArgView](count=2))
    var statuses = storage.unsafe_ptr()
    statuses[unsafe_offset=0] = LaunchArgView(UInt64(Int(thread.unsafe_ptr())), UInt64(thread.byte_length()), 1)
    statuses[unsafe_offset=1] = LaunchArgView(UInt64(Int(goal.unsafe_ptr())), UInt64(goal.byte_length()), 1)
    print(prodex_launch_native_recovery_wire_v1(1, UInt64(Int(statuses)), 2, flags, budget, used))
    dealloc(storage^)
''')
        oracle = source.with_suffix("")
        subprocess.run([os.environ.get("MOJO", "mojo"), "build", "-O3", "--target-cpu=x86-64-v3",
                        "-I", str(REFERENCE / "mojo/prodex_core"), str(source), "-o", str(oracle)], check=True)
        for thread, goal, flags in itertools.product(
                ["idle", "systemError", "active", "notLoaded", "unknown"],
                ["", "active", "blocked", "usageLimited", "paused", "budgetLimited", "complete", "unknown"],
                [0, 1, 3, 7, 27, 31, 32, 33, 59, 63]):
            with self.subTest(thread=thread, goal=goal, flags=flags):
                self.assertEqual(self.wire(thread, goal, flags), self.wire(thread, goal, flags, driver=oracle))
        for budget, used in [(0, 0), (-1, 0), (100, -1), (100, 100), (100, 101), (2**63-1, 2**63-2), (-2**63, -2**63)]:
            self.assertEqual(self.wire("idle", "blocked", 59, budget, used),
                             self.wire("idle", "blocked", 59, budget, used, oracle))


if __name__ == "__main__":
    unittest.main()
