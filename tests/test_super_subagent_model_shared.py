"""Compare sub-agent model argument validation with both release processes."""

import hashlib
import unittest

from test_cli import MODEX, ORACLE as ORACLE_04392, ORACLE_SHA256 as SHA_04392
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as SHA_01651
from test_root_help import isolated_run


class SuperSubagentModelSharedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for oracle, digest in ((ORACLE_01651, SHA_01651), (ORACLE_04392, SHA_04392)):
            if not oracle.is_file() or hashlib.sha256(oracle.read_bytes()).hexdigest() != digest:
                raise AssertionError(f"verified release oracle required: {oracle}")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")

    def test_empty_model_diagnostics_before_and_after_exec(self):
        for value in ("", "   ", "\t\n", "\u3000\u00a0"):
            for tail in (False, True):
                with self.subTest(value=value, tail=tail):
                    args = ["super"] + (["exec"] if tail else []) + [
                        "--sub-agent", "--sub-agent-model", value,
                    ] + ([] if tail else ["--help"])
                    reason = "--sub-agent-model must be nonempty"
                    expected = ("Error: " + reason + "\n" if tail else
                                "error: invalid value '" + value + "' for '--sub-agent-model <MODEL>': "
                                + reason + "\n\nFor more information, try '--help'.\n").encode()
                    for binary, argv0 in ((ORACLE_01651, "prodex"), (ORACLE_04392, "prodex"), (MODEX, "modex")):
                        result, created = isolated_run(binary, args, argv0, "subagent-model")
                        self.assertEqual((result.returncode, result.stdout, result.stderr),
                                         (1 if tail else 2, b"", expected))
                        if binary == MODEX or not tail:
                            self.assertEqual(created, [])
                        else:
                            self.assertTrue(created)

    def test_valid_model_values_keep_help_order_and_original_value(self):
        binaries = ((ORACLE_01651, "prodex"), (ORACLE_04392, "prodex"), (MODEX, "modex"))
        help_outputs = {}
        for binary, argv0 in binaries:
            result, created = isolated_run(binary, ["super", "--help"], argv0, "subagent-model-help")
            self.assertEqual((result.returncode, result.stderr, created), (0, b"", []))
            help_outputs[binary] = result.stdout
        for value in ("synthetic-model", "  雪 model  ", "0"):
            with self.subTest(value=value):
                args = ["super", "--sub-agent", "--sub-agent-model", value, "--help"]
                for binary, argv0 in binaries:
                    result, created = isolated_run(binary, args, argv0, "subagent-model-valid")
                    self.assertEqual((result.returncode, result.stderr, created), (0, b"", []))
                    self.assertEqual(result.stdout, help_outputs[binary])


if __name__ == "__main__":
    unittest.main()
