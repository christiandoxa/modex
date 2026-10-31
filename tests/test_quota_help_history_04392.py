"""Guard the historical quota help routes while changing its parser."""

import unittest

import test_cli
from test_root_help import isolated_run


class QuotaHelpHistory04392Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_quota_help_forms_remain_unchanged(self):
        for arguments in (["quota", "--help"], ["quota", "-h"], ["help", "quota"]):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_run(
                    test_cli.ORACLE, arguments, "prodex", "quota-help-history-oracle"
                )
                modex, modex_created = isolated_run(
                    test_cli.MODEX, arguments, "prodex", "quota-help-history-modex"
                )
                self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (baseline.returncode, baseline.stdout, baseline.stderr),
                )
                self.assertEqual((baseline_created, modex_created), ([], []))


if __name__ == "__main__":
    unittest.main()
