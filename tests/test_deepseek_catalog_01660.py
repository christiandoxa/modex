"""Compare the production DeepSeek launch catalog with Prodex 0.166.0."""

import hashlib
from pathlib import Path
import unittest

from test_active_baseline_01660 import MODEX, ORACLE, ORACLE_SHA256
from test_super_launch import run_private_launch


class DeepSeekCatalog01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")
        if not ORACLE.is_absolute() or not ORACLE.is_file():
            raise AssertionError(f"Use an absolute pinned 0.166.0 binary: {ORACLE}")
        if hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError(f"The 0.166.0 oracle checksum is wrong: {ORACLE}")

    def test_catalog_matches_active_launch_selection_and_retirement_rules(self):
        cases = (
            "deepseek-v4-pro",
            "deepseek-flash",
            "deepseek-v4-flash",
            "auto",
            "pro",
            "flash",
            "FLASH",
            "deepseek-chat",
            "deepseek-reasoner",
            "DEEPSEEK-CHAT",
            "deepsee\u212a-chat",
            'synthetic-model-"quoted"',
            "synthetic\\model",
        )
        for model in cases:
            with self.subTest(model=model):
                catalogs = []
                for binary in (ORACLE, MODEX):
                    result, records, upstream, state = run_private_launch(
                        binary=binary, scenario="exit-seven", model=model,
                    )
                    self.assertEqual(result.returncode, 7, result.stderr)
                    self.assertEqual((upstream, state["leftovers"]), ([], []))
                    launch = next(record for record in records if record["kind"] == "launch")
                    catalogs.append(launch["catalog"])

                self.assertEqual(catalogs[1], catalogs[0])
                slugs = [row["slug"] for row in catalogs[0]["models"]]
                if model == "deepseek-v4-pro":
                    models = {row["slug"]: row for row in catalogs[0]["models"]}
                    self.assertEqual(slugs, [
                        "deepseek-v4-pro", "auto", "pro", "flash",
                        "deepseek-v4-flash", "deepseek-flash",
                    ])
                    self.assertEqual(models["flash"]["description"],
                                     "Prodex DeepSeek Flash alias routed through current DeepSeek Flash.")
                    self.assertEqual(models["deepseek-flash"]["description"],
                                     "Current DeepSeek Flash routed through the Prodex Responses adapter.")
                    self.assertEqual(models["deepseek-flash"]["display_name"], "DeepSeek V4.1 Flash")
                    self.assertEqual(
                        models["deepseek-flash"]["priority"],
                        8,
                    )
                    self.assertEqual(
                        [level["effort"] for level in catalogs[0]["models"][0]["supported_reasoning_levels"]],
                        ["none", "low", "high", "max"],
                    )
                elif model in ("deepseek-chat", "deepseek-reasoner", "DEEPSEEK-CHAT"):
                    self.assertNotIn(model.lower(), [slug.lower() for slug in slugs])
                elif model == "deepsee\u212a-chat":
                    self.assertIn(model, slugs)


if __name__ == "__main__":
    unittest.main()
