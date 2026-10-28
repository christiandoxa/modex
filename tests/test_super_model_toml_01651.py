"""Compare production Super model TOML arguments with Prodex 0.165.1."""

import hashlib
import tomllib
import unittest

from test_cli import MODEX
from test_cli_01651 import ORACLE, ORACLE_SHA256
import test_super_launch as launch_harness


class SuperModelToml01651Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE_01651 must identify the verified 0.165.1 Linux release")
        cls.harness = launch_harness.SuperLaunchTests()

    def test_model_app_server_toml_arguments_match_and_parse(self):
        for model in ("a\tb", 'a"b', "a\\tb", 'a\tb"c', "雪とé"):
            with self.subTest(model=model):
                baseline, before_records, before_upstream, before_state = self.harness.run_launch(
                    ORACLE, "exit-seven", model=model
                )
                native, after_records, after_upstream, after_state = self.harness.run_launch(
                    MODEX, "exit-seven", model=model
                )
                self.assertEqual((native.returncode, baseline.returncode), (7, 7))
                self.assertEqual((before_upstream, after_upstream), ([], []))
                self.assertEqual((before_state["leftovers"], after_state["leftovers"]), ([], []))
                before = next(record["args"] for record in before_records if record["kind"] == "preflight")
                after = next(record["args"] for record in after_records if record["kind"] == "preflight")
                self.assertEqual(
                    launch_harness.normalized_app_server_args(after),
                    launch_harness.normalized_app_server_args(before),
                )
                for arguments in (before, after):
                    config = tomllib.loads(launch_harness.app_server_config(arguments))
                    self.assertEqual(config["model"], model)
                    self.assertEqual(config["model_provider"], "prodex-deepseek")

    def test_model_newline_cannot_inject_app_server_config(self):
        model = 'safe\nmodel_provider="attacker"\nfeatures.apps=true'
        native, records, upstream, state = self.harness.run_launch(
            MODEX, "exit-seven", model=model
        )
        self.assertEqual(native.returncode, 7)
        self.assertEqual(upstream, [])
        self.assertEqual(state["leftovers"], [])
        arguments = next(record["args"] for record in records if record["kind"] == "preflight")
        config = tomllib.loads(launch_harness.app_server_config(arguments))
        self.assertEqual(config["model"], model)
        self.assertEqual(config["model_provider"], "prodex-deepseek")
        self.assertFalse(config["features"]["apps"])
