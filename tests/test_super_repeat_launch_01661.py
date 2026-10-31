"""Active Prodex 0.166.1 characterization of repeated Super launches."""

import hashlib
import unittest

import test_active_baseline_01661 as active
import test_super_launch as launch


class SuperRepeatLaunch01661Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (
            not active.ORACLE.is_file()
            or hashlib.sha256(active.ORACLE.read_bytes()).hexdigest() != active.ORACLE_SHA256
        ):
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.1 Linux release")
        if not launch.MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def test_repeat_launch_preserves_state_and_records_modex_guard(self):
        for label, binary, expected_repeat, expected_launches in (
            ("Prodex 0.166.1", active.ORACLE, 7, 2),
            ("Modex", launch.MODEX, 1, 1),
        ):
            with self.subTest(binary=label):
                first, records, upstream, state = launch.run_private_launch(
                    binary, scenario="exit-seven", repeat_launch=True,
                )

                self.assertEqual((first.returncode, first.stdout), (7, b""), first.stderr)
                self.assertEqual(state["repeat"].returncode, expected_repeat, state["repeat"].stderr)
                self.assertNotIn(
                    b"synthetic-provider-key",
                    first.stdout + first.stderr + state["repeat"].stdout + state["repeat"].stderr,
                )
                self.assertEqual(sum(record["kind"] == "launch" for record in records), expected_launches)
                self.assertEqual(upstream, [])
                self.assertEqual(state["session"], '{"synthetic":true}\n')
                self.assertIn('{"synthetic":"preserve history"}\n', state["history"])
                self.assertEqual(state["leftovers"], [])
                if label == "Modex":
                    self.assertIn(b"cannot reconcile existing Codex data", state["repeat"].stderr)


if __name__ == "__main__":
    unittest.main()
