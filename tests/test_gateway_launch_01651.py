"""Compare the Gateway profileless DeepSeek startup classification to pinned releases."""

import hashlib
import json
import os
from pathlib import Path
import unittest

import test_gateway as gateway


ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
ORACLE_04392 = Path(os.environ.get(
    "PRODEX_ORACLE_04392",
    os.environ.get(
        "PRODEX_ORACLE",
        Path.home() / ".cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu",
    ),
))
ORACLE_04392_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
ORACLE_04391_DEFAULT = Path.home() / ".cache/modex/oracles/0.439.1/prodex-x86_64-unknown-linux-gnu"
ORACLE_04391 = Path(os.environ.get("PRODEX_ORACLE_04391", ORACLE_04391_DEFAULT))
ORACLE_04391_SHA256 = "b4511d679dd6da53f706400dba5b368ffc5b5663f8764fa0c8f148b358b9255a"
EXPECTED_ERROR = "Error: gateway provider does not expose an OpenAI-compatible proxy\n"
NO_PROFILE_ERROR = (
    "Error: no active profile selected and no Codex-compatible profiles are available; "
    "use `prodex use --profile <name>` or pass --profile\n"
)
UNSUPPORTED_CONFIG_ERROR = (
    "Error: gateway startup for this Codex configuration is not implemented by this Modex build\n"
)
STATE_PRESENT_ERROR = (
    "Error: gateway startup for existing application state is not implemented by this Modex build\n"
)


class GatewayLaunchClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not gateway.MODEX.is_file():
            raise AssertionError(f"build the actual Modex CLI first: {gateway.MODEX}")
        cls.binaries = [
            ("0.165.1", ORACLE_01651, ORACLE_01651_SHA256),
            ("0.439.2", ORACLE_04392, ORACLE_04392_SHA256),
        ]
        if not ORACLE_01651.is_file() or not ORACLE_04392.is_file():
            raise AssertionError("verified 0.165.1 and 0.439.2 Linux oracles are required")
        for label, binary, expected in cls.binaries:
            digest = hashlib.sha256(binary.read_bytes()).hexdigest()
            if digest != expected:
                raise AssertionError(f"pinned {label} oracle checksum mismatch: {digest}")
        if ORACLE_04391.is_file():
            digest = hashlib.sha256(ORACLE_04391.read_bytes()).hexdigest()
            if digest != ORACLE_04391_SHA256:
                raise AssertionError(f"pinned 0.439.1 oracle checksum mismatch: {digest}")
            cls.binaries.append(("0.439.1", ORACLE_04391, ORACLE_04391_SHA256))

        fixture = json.loads(gateway.GATEWAY_FIXTURE.read_text(encoding="utf-8"))
        cls.case = next(
            case for case in fixture["cases"]
            if case["name"] == "deepseek_profileless_codex_config"
        )

    def test_deepseek_provider_classification_ignores_other_codex_settings(self):
        configurations = (
            (
                "additional_top_level_setting",
                'model_provider = "prodex-deepseek"\nmodel = "deepseek-chat"\n',
            ),
            (
                "nested_project_setting",
                'model_provider = "prodex-deepseek"\n'
                '[projects."/tmp/synthetic"]\ntrust_level = "trusted"\n',
            ),
        )
        for variant, configuration in configurations:
            case = {**self.case, "synthetic_shared_config": configuration}
            with self.subTest(variant=variant):
                for label, binary, _ in self.binaries:
                    result = gateway.run_case(case, binary=binary)
                    observation = (
                        result["returncode"], result["stdout"], result["stderr"],
                        result["upstream_requests"],
                    )
                    self.assertEqual(observation, (1, "", EXPECTED_ERROR, []), label)
                    self.assertNotIn("synthetic-provider-key", result["stdout"] + result["stderr"])

                actual = gateway.run_case(case, binary=gateway.MODEX)
                self.assertEqual(
                    (
                        actual["returncode"], actual["stdout"], actual["stderr"],
                        actual["upstream_requests"],
                    ),
                    (1, "", EXPECTED_ERROR, []),
                )
                self.assertNotIn("synthetic-provider-key", actual["stdout"] + actual["stderr"])

    def test_duplicate_and_malformed_toml_are_rejected_before_proxy_classification(self):
        configurations = (
            (
                "duplicate_root_provider",
                'model_provider = "prodex-deepseek"\n'
                'model_provider = "prodex-deepseek"\n',
                "duplicate",
            ),
            (
                "malformed_root_provider",
                'model_provider = "prodex-deepseek"\n[unfinished\n',
                "toml",
            ),
        )
        for variant, configuration, diagnostic in configurations:
            case = {**self.case, "synthetic_shared_config": configuration}
            with self.subTest(variant=variant):
                for label, binary, _ in self.binaries:
                    result = gateway.run_case(case, binary=binary)
                    self.assertEqual(result["returncode"], 1, label)
                    self.assertEqual(result["stdout"], "", label)
                    self.assertTrue(result["stderr"].strip(), label)
                    self.assertIn(diagnostic, result["stderr"].lower(), label)
                    self.assertNotIn(EXPECTED_ERROR.strip(), result["stderr"], label)
                    self.assertEqual(result["upstream_requests"], [], label)

                actual = gateway.run_case(case, binary=gateway.MODEX)
                self.assertEqual(actual["returncode"], 1)
                self.assertEqual(actual["stdout"], "")
                self.assertIn(diagnostic, actual["stderr"].lower())
                self.assertNotIn(EXPECTED_ERROR.strip(), actual["stderr"])
                self.assertEqual(actual["upstream_requests"], [])

    def test_nested_only_provider_remains_unclassified_and_fail_closed(self):
        case = {
            **self.case,
            "synthetic_shared_config": (
                '[projects."/tmp/synthetic"]\n'
                'model_provider = "prodex-deepseek"\n'
            ),
        }
        for label, binary, _ in self.binaries:
            result = gateway.run_case(case, binary=binary)
            self.assertEqual(
                (result["returncode"], result["stdout"], result["stderr"], result["upstream_requests"]),
                (1, "", NO_PROFILE_ERROR, []),
                label,
            )

        actual = gateway.run_case(case, binary=gateway.MODEX)
        self.assertEqual((actual["returncode"], actual["stdout"], actual["upstream_requests"]),
                         (1, "", []))
        self.assertIn(actual["stderr"], (UNSUPPORTED_CONFIG_ERROR, NO_PROFILE_ERROR))

    def test_group_writable_config_with_extra_settings_still_fails_closed(self):
        configurations = (
            'model_provider = "prodex-deepseek"\nmodel = "deepseek-chat"\n',
            'model_provider = "prodex-deepseek"\n'
            '[projects."/tmp/synthetic"]\ntrust_level = "trusted"\n',
        )
        for index, configuration in enumerate(configurations):
            case = {**self.case, "synthetic_shared_config": configuration}
            with self.subTest(extra_settings=index):
                for label, binary, _ in self.binaries:
                    result = gateway.run_case(case, config_mode=0o664, binary=binary)
                    self.assertEqual(result["returncode"], 1, label)
                    self.assertEqual(result["stdout"], "", label)
                    self.assertEqual(result["stderr"], EXPECTED_ERROR, label)
                    self.assertEqual(result["upstream_requests"], [], label)

                actual = gateway.run_case(case, config_mode=0o664, binary=gateway.MODEX)
                self.assertEqual(actual["returncode"], 1)
                self.assertEqual(actual["stdout"], "")
                self.assertEqual(
                    actual["stderr"],
                    "Error: gateway Codex config requires an owned file without shared write access\n",
                )
                self.assertEqual(actual["upstream_requests"], [])

    def test_existing_application_state_blocks_classification(self):
        state = '{"schema_version":1,"active_profile":"main","profiles":{}}\n'
        actual = gateway.run_case(
            self.case,
            binary=gateway.MODEX,
            app_state=state,
        )
        self.assertEqual(
            (actual["returncode"], actual["stdout"], actual["stderr"], actual["upstream_requests"]),
            (1, "", STATE_PRESENT_ERROR, []),
        )
        self.assertEqual(actual["filesystem_delta"], [])

    def test_empty_profile_state_matches_each_release_no_profile_error(self):
        case = {**self.case, "synthetic_shared_config": None}
        for label, binary, _ in self.binaries:
            result = gateway.run_case(case, binary=binary)
            self.assertEqual(
                (result["returncode"], result["stdout"], result["stderr"], result["upstream_requests"]),
                (1, "", NO_PROFILE_ERROR, []),
                label,
            )

        actual = gateway.run_case(case, binary=gateway.MODEX)
        self.assertEqual(
            (actual["returncode"], actual["stdout"], actual["stderr"], actual["upstream_requests"]),
            (1, "", NO_PROFILE_ERROR, []),
        )


if __name__ == "__main__":
    unittest.main()
