"""Exercise shared Codex config through the pinned and Modex Super processes."""

import hashlib
import json
import unittest

from test_cli import MODEX, ORACLE, ORACLE_SHA256
from test_deepseek_web_search_mode_01651_04392 import ORACLE_01651, ORACLE_01651_SHA256
import test_super_launch


class SuperSharedConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary, checksum in ((ORACLE_01651, ORACLE_01651_SHA256), (ORACLE, ORACLE_SHA256)):
            if hashlib.sha256(binary.read_bytes()).hexdigest() != checksum:
                raise AssertionError("The Prodex oracle does not match its pinned release")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")

    def test_shared_config_is_preserved_and_catalog_matches(self):
        cases = (
            ("", (), 1048576, 900000),
            ('model = "shared-default"\nmodel_provider = "openai"\n', (), 1048576, 900000),
            ('developer_instructions = "synthetic guidance"\n[features]\napps = true\n', (), 1048576, 900000),
            ('[deepseek]\nweb_search_mode = "off"\nunknown_setting = "preserve"\n[features]\napps = true\n', (), 1048576, 900000),
            ('model_context_window = 8192\nmodel_auto_compact_token_limit = 4096\n', (), 1048576, 900000),
            ('model_context_window = "8192"\nmodel_auto_compact_token_limit = "4096"\n', (), 8192, 4096),
            ('model_context_window = "128"\nmodel_auto_compact_token_limit = "999"\n', (), 128, 127),
            ('model_context_window = "8192"\nmodel_auto_compact_token_limit = "4096"\n',
             ("--context-window", "32768", "--auto-compact-token-limit", "12000"), 8192, 4096),
        )
        for config, arguments, context, compact in cases:
            catalogs = []
            upstream_bodies = []
            for binary in (ORACLE_01651, ORACLE, MODEX):
                with self.subTest(config=config, arguments=arguments, binary=str(binary)):
                    result, records, upstream, state = test_super_launch.SuperLaunchTests().run_launch(
                        binary=binary, scenario="buffered", shared_config=config,
                        super_arguments=arguments,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(len(upstream), 1)
                    self.assertEqual(upstream[0]["path"], "/v1/chat/completions")
                    headers = {key.lower(): value for key, value in upstream[0]["headers"].items()}
                    self.assertEqual(headers["authorization"], "Bearer synthetic-provider-key")
                    upstream_bodies.append(json.loads(bytes.fromhex(upstream[0]["body"])))
                    self.assertEqual(state["config"], config)
                    self.assertEqual(state["leftovers"], [])
                    launch = next(row for row in records if row["kind"] == "launch")
                    self.assertEqual(launch["runtime_config"], config)
                    self.assertEqual(launch["config"]["model_provider"], "prodex-deepseek")
                    self.assertEqual(launch["config"]["model"], "deepseek-chat")
                    for row in launch["catalog"]["models"]:
                        self.assertEqual((row["context_window"], row["max_context_window"],
                                          row["auto_compact_token_limit"]), (context, context, compact))
                    catalogs.append(launch["catalog"])
            # Catalog entries differ across releases; the configuration values
            # above are compared for both, and full contents against 0.439.2.
            self.assertEqual(catalogs[1], catalogs[2])
            self.assertEqual(upstream_bodies[0], upstream_bodies[1])
            self.assertEqual(upstream_bodies[1], upstream_bodies[2])

    def test_invalid_string_catalog_limits_fail_before_child_or_provider(self):
        cases = (('""', "cannot be empty"), ('"1"', "must be greater than 1"),
                 ('"2 3"', "must not contain whitespace"),
                 ('"bad"', "must be an unsigned integer: invalid digit found in string"),
                 ('"18446744073709551616"', "must be an unsigned integer: number too large to fit in target type"))
        for key in ("model_context_window", "model_auto_compact_token_limit"):
            for value, message in cases:
                config = f"{key} = {value}\n"
                for binary in (ORACLE_01651, ORACLE, MODEX):
                    with self.subTest(key=key, value=value, binary=str(binary)):
                        result, records, upstream, state = test_super_launch.SuperLaunchTests().run_launch(
                            binary=binary, scenario="buffered", shared_config=config,
                        )
                        self.assertEqual(result.returncode, 1)
                        self.assertIn((f"DeepSeek {key} {message}").encode(), result.stderr)
                        self.assertEqual((records, upstream, state["leftovers"], state["config"]),
                                         ([], [], [], config))

    def test_missing_profile_is_reported_before_config_validation(self):
        for config in ('model_context_window = "bad"\n', '[deepseek]\nstrict_tools = 4\n'):
            for binary in (ORACLE_01651, ORACLE, MODEX):
                with self.subTest(config=config, binary=str(binary)):
                    result, records, upstream, state = test_super_launch.SuperLaunchTests().run_launch(
                        binary=binary, scenario="buffered", shared_config=config,
                        super_arguments=("--profile", "missing-synthetic"),
                        environment_overrides={"PRODEX_DEEPSEEK_WEB_SEARCH_MODE": "invalid"},
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(b"profile 'missing-synthetic' does not exist", result.stderr)
                    self.assertEqual((records, upstream, state["leftovers"], state["config"]),
                                     ([], [], [], config))

        config = "[broken\n"
        for binary in (ORACLE_01651, ORACLE, MODEX):
            result, records, upstream, state = test_super_launch.SuperLaunchTests().run_launch(
                binary=binary, scenario="buffered", shared_config=config,
                super_arguments=("--profile", "missing-synthetic"),
            )
            self.assertEqual(result.returncode, 1)
            self.assertNotIn(b"profile 'missing-synthetic' does not exist", result.stderr)
            self.assertEqual((records, upstream, state["leftovers"], state["config"]),
                             ([], [], [], config))
