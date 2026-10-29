"""Compare post-positional concurrency diagnostics with both release processes."""

import hashlib
import unittest

from test_cli import MODEX, ORACLE as ORACLE_04392, ORACLE_SHA256 as SHA_04392
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as SHA_01651
from test_root_help import isolated_run


class SuperConcurrencySharedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for oracle, digest in ((ORACLE_01651, SHA_01651), (ORACLE_04392, SHA_04392)):
            if not oracle.is_file() or hashlib.sha256(oracle.read_bytes()).hexdigest() != digest:
                raise AssertionError(f"verified release oracle required: {oracle}")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def test_post_tail_concurrency_diagnostics_match_both_releases(self):
        syntax = "invalid maximum active sub-agents: expected default or an integer from 1 to 64"
        overflow = "invalid maximum active sub-agents: expected an integer from 1 to 64"
        bounds = "maximum active sub-agents must be between 1 and 64"
        for value, reason in ((" 0 ", bounds), ("　65　", bounds), (" 00000065 ", bounds),
                              (" 65535 ", bounds), (" 65536 ", overflow),
                              (" +1 ", syntax), (" -1 ", syntax), (" 999999 ", overflow),
                              (" 999999999999999999999x ", syntax)):
            with self.subTest(value=value):
                arguments = ["super", "exec", "--sub-agent", "--sub-agent-max-concurrency", value]
                for binary, argv0 in ((ORACLE_01651, "prodex"), (ORACLE_04392, "prodex"), (MODEX, "modex")):
                    result, created = isolated_run(binary, arguments, argv0, "concurrency-shared")
                    self.assertEqual((result.returncode, result.stdout, result.stderr),
                                     (1, b"", ("Error: " + reason + "\n").encode()))
                    if binary == MODEX:
                        self.assertEqual(created, [])
                    else:
                        self.assertTrue(created)

    def test_post_tail_valid_values_reach_release_dry_run_and_modex_guard(self):
        for value, line in ((" 00001 ", b"Maximum active sub-agents: 1 (custom)\n"),
                            ("　64　", b"Maximum active sub-agents: 64 (custom)\n"),
                            (" default ", b"Maximum active sub-agents: 4 (Prodex default)\n")):
            with self.subTest(value=value):
                arguments = ["super", "exec", "--dry-run", "--provider", "deepseek", "--api-key",
                             "synthetic-provider-key", "--base-url", "http://127.0.0.1:8131/v1",
                             "--model", "deepseek-chat", "--no-presidio", "--skip-quota-check",
                             "--sub-agent", "--sub-agent-max-concurrency", value]
                for binary, argv0 in ((ORACLE_01651, "prodex"), (ORACLE_04392, "prodex")):
                    result, created = isolated_run(binary, arguments, argv0, "concurrency-dry-run")
                    self.assertEqual((result.returncode, result.stderr, created), (0, b"", []))
                    self.assertIn(line, result.stdout)
                    self.assertNotIn(b"synthetic-provider-key", result.stdout)
                result, created = isolated_run(MODEX, arguments, "modex", "concurrency-dry-run")
                self.assertEqual((result.returncode, result.stdout, created), (1, b"", []))
                self.assertIn(b"Super startup is not implemented", result.stderr)
                self.assertNotIn(b"synthetic-provider-key", result.stderr)


if __name__ == "__main__":
    unittest.main()
