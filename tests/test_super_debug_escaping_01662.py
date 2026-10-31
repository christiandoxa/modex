"""Compare selected Super debug-string escaping with Prodex 0.166.2."""

import hashlib
import unittest

from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from test_root_help import isolated_run


class SuperDebugEscaping01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified Prodex 0.166.2 release")

    def test_selected_debug_escapes_match_both_super_diagnostics(self):
        characters = (
            (0x00A0, br"\u{a0}"),
            (0x202F, br"\u{202f}"),
            (0x0378, br"\u{378}"),
            (0x2063, br"\u{2063}"),
            (0xFE0F, br"\u{fe0f}"),
            (0xE000, br"\u{e000}"),
            (0xFFF9, br"\u{fff9}"),
            (0x200E, br"\u{200e}"),
            (0x00E9, "é".encode()),
        )
        for option in ("--sub-agent-provider", "--sub-agent-model-reasoning-effort"):
            for codepoint, rendered in characters:
                value = "synthetic" + chr(codepoint) + "invalid"
                arguments = ["super", option, value, "--help"]
                with self.subTest(option=option, codepoint=f"U+{codepoint:04X}"):
                    baseline, baseline_created = isolated_run(
                        ORACLE, arguments, "prodex", "01662-super-debug-oracle"
                    )
                    modex, modex_created = isolated_run(
                        MODEX, arguments, "modex", "01662-super-debug-modex"
                    )
                    expected_debug = b'got "synthetic' + rendered + b'invalid"'
                    self.assertEqual((baseline.returncode, baseline.stdout), (2, b""))
                    self.assertIn(expected_debug, baseline.stderr)
                    self.assertEqual(
                        (modex.returncode, modex.stdout, modex.stderr),
                        (baseline.returncode, baseline.stdout, baseline.stderr),
                    )
                    self.assertEqual((baseline_created, modex_created), ([], []))


if __name__ == "__main__":
    unittest.main()
