"""Check profileless Gateway config classification against Prodex 0.166.2."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command


ROOT = Path(__file__).resolve().parents[1]
MODEX = Path(os.environ.get("MODEX_BINARY", ROOT / "build/modex"))
ORACLE = Path(os.environ.get(
    "PRODEX_ORACLE_01662",
    os.environ.get(
        "PRODEX_ORACLE",
        Path(os.environ.get("MODEX_REFERENCE_CACHE", Path.home() / ".cache/modex"))
        / "oracles/0.166.2/prodex-x86_64-unknown-linux-gnu",
    ),
))
ORACLE_SHA256 = "e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00"
NO_PROFILE = (
    b"Error: no active profile selected and no Codex-compatible profiles are available; "
    b"use `prodex use --profile <name>` or pass --profile\n"
)
NO_OPENAI_PROXY = b"Error: gateway provider does not expose an OpenAI-compatible proxy\n"

CONFIG_CASES = {
    "lowercase_deepseek": ('model_provider = "prodex-deepseek"\n', NO_OPENAI_PROXY),
    "mixed_case_deepseek": ('model_provider = "Prodex-DeepSeek"\n', NO_OPENAI_PROXY),
    "uppercase_deepseek": ('model_provider = "PRODEX-DEEPSEEK"\n', NO_OPENAI_PROXY),
    "openai_provider": ('model_provider = "openai"\n', NO_PROFILE),
    "deepseek_provider": ('model_provider = "deepseek"\n', NO_PROFILE),
    "empty_provider": ('model_provider = ""\n', NO_PROFILE),
    "leading_space": ('model_provider = " prodex-deepseek"\n', NO_PROFILE),
    "trailing_space": ('model_provider = "prodex-deepseek "\n', NO_PROFILE),
    "integer_provider": ("model_provider = 42\n", NO_PROFILE),
    "array_provider": ('model_provider = ["prodex-deepseek"]\n', NO_PROFILE),
}


def observe(binary, executable, configuration):
    with tempfile.TemporaryDirectory(prefix="modex-gateway-config-01662-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir(mode=0o700)
        app_home = root / "prodex"
        shared_home = root / "shared-codex"
        shared_home.mkdir(mode=0o700)
        config = shared_home / "config.toml"
        config.write_text(configuration, encoding="utf-8")
        config.chmod(0o600)
        command = sandbox_command(
            binary,
            root,
            ["gateway", "--provider", "deepseek"],
            argv0=executable,
            environment={
                "PRODEX_HOME": str(app_home),
                "PRODEX_SHARED_CODEX_HOME": str(shared_home),
            },
        )
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        return result


class GatewayConfigClassification01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError(f"Build Modex first: {MODEX}")
        if not ORACLE.is_absolute() or not ORACLE.is_file():
            raise AssertionError(f"Use the pinned 0.166.2 binary: {ORACLE}")
        digest = hashlib.sha256(ORACLE.read_bytes()).hexdigest()
        if digest != ORACLE_SHA256:
            raise AssertionError(f"The 0.166.2 oracle checksum is wrong: {digest}")

    def test_root_provider_classification_matches_in_network_isolation(self):
        for name, (configuration, expected_stderr) in CONFIG_CASES.items():
            with self.subTest(case=name):
                baseline = observe(ORACLE, "prodex", configuration)
                actual = observe(MODEX, "modex", configuration)
                expected = (1, b"", expected_stderr)
                self.assertEqual(
                    (baseline.returncode, baseline.stdout, baseline.stderr), expected,
                )
                self.assertEqual(
                    (actual.returncode, actual.stdout, actual.stderr), expected,
                )
                self.assertNotIn(b"synthetic", actual.stdout + actual.stderr)


if __name__ == "__main__":
    unittest.main()
