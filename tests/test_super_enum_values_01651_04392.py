"""Compare Super enum diagnostics with both pinned release processes."""

import hashlib
import os
from pathlib import Path
import unittest

from test_cli import MODEX
from test_root_help import isolated_run


ORACLES = (
    ("PRODEX_ORACLE_01651", "0.165.1", "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"),
    ("PRODEX_ORACLE_04392", "0.439.2", "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"),
)


class SuperEnumValueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binaries = []
        cache = Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
        for variable, version, checksum in ORACLES:
            binary = Path(os.environ.get(variable, cache / f"oracles/{version}/prodex-x86_64-unknown-linux-gnu"))
            if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != checksum:
                raise AssertionError(f"{variable} must identify pinned Prodex {version}")
            cls.binaries.append(binary)
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        cls.binaries.append(MODEX)

    def test_enum_value_diagnostics_and_positional_error(self):
        cases = (
            ("--cli", ("bad", "AGY", "ag", "")),
            ("--web-search", ("invalid", "LIVE", "liv", "cachd", "indexd", "")),
            ("--current-time-clock-source", ("bad", "systm", "externl", "")),
        )
        for option, values in cases:
            for value in values:
                for positional in (False, True):
                    if positional and option == "--web-search" and value == "LIVE":
                        continue
                    for attached in (False, True):
                        args = ["super"] + (["exec"] if positional else [])
                        args += [option + "=" + value] if attached else [option, value]
                        args.append("--help")
                        results = []
                        for binary in self.binaries:
                            result, created = isolated_run(binary, args, "modex" if binary == MODEX else "prodex", "super-enum")
                            results.append((result.returncode, result.stdout, result.stderr))
                            if not positional:
                                self.assertEqual(created, [])
                        with self.subTest(option=option, value=value, positional=positional, attached=attached):
                            self.assertEqual(results[1:], results[:1] * 2)
                            self.assertEqual(results[0][0], 1 if positional else 2)

    def test_valid_values_allow_help_without_state(self):
        for option, values in (("--cli", ("agy",)),
                               ("--web-search", ("disabled", "cached", "indexed", "live")),
                               ("--current-time-clock-source", ("system", "external"))):
            for value in values:
                for binary in self.binaries:
                    result, created = isolated_run(binary, ["super", option, value, "--help"],
                                                   "modex" if binary == MODEX else "prodex", "super-enum-valid-help")
                    self.assertEqual((result.returncode, result.stderr, created), (0, b"", []))
                    self.assertTrue(result.stdout.startswith(b"YOLO shortcut for the Super tool stack"))

    def test_uppercase_positional_values_reach_guarded_launch(self):
        for option, value in (("--web-search", "LIVE"), ("--current-time-clock-source", "SYSTEM")):
            args = ["super", "exec", option, value, "--help"]
            for binary in self.binaries:
                result, _ = isolated_run(binary, args, "modex" if binary == MODEX else "prodex", "super-enum-valid")
                self.assertEqual(result.returncode, 1)
                if binary == MODEX:
                    self.assertIn(b"Super startup is not implemented", result.stderr)
                else:
                    self.assertIn(b"no active profile selected", result.stderr)

    def test_help_before_invalid_value_short_circuits(self):
        for binary in self.binaries:
            result, created = isolated_run(binary, ["super", "--help", "--web-search=invalid"],
                                           "modex" if binary == MODEX else "prodex", "super-enum-help")
            self.assertEqual((result.returncode, result.stderr, created), (0, b"", []))
            self.assertTrue(result.stdout.startswith(b"YOLO shortcut for the Super tool stack"))


if __name__ == "__main__":
    unittest.main()
