"""Compare Gateway's omitted-provider preflight with Prodex 0.166.0."""

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_active_baseline_01660 import (
    MODEX,
    ORACLE,
    ORACLE_SHA256,
    isolated_super_cli as isolated_cli,
    normalize_super_cli_executable as normalize_cli,
)
from test_runtime_broker_startup_01660_oracle import write_modex_profile_fixture


def isolated_gateway_config(binary, argv0, model_provider):
    with tempfile.TemporaryDirectory(prefix="modex-active-gateway-config-") as temporary:
        root = Path(temporary)
        home = root / "home"
        workspace = root / "workspace"
        shared = home / ".codex"
        home.mkdir(mode=0o700)
        workspace.mkdir()
        shared.mkdir(mode=0o700)
        config = shared / "config.toml"
        config.write_text(f'model_provider = "{model_provider}"\n', encoding="utf-8")
        config.chmod(0o600)
        return subprocess.run(
            sandbox_command(binary, root, ("gateway",), argv0=argv0),
            stdin=subprocess.DEVNULL, capture_output=True, timeout=10, check=False,
        )


def isolated_gateway_profile(binary, argv0):
    with tempfile.TemporaryDirectory(prefix="modex-active-gateway-profile-") as temporary:
        root = Path(temporary)
        home, app, logs = write_modex_profile_fixture(root)
        workspace = root / "workspace"
        profile = app / "profiles" / "synthetic"
        workspace.mkdir(mode=0o700)
        config = profile / "config.toml"
        config.write_text('model_provider = "openai"\n', encoding="utf-8")
        config.chmod(0o600)
        state = app / "state.json"
        auth = profile / "auth.json"
        state_before, auth_before = state.read_bytes(), auth.read_bytes()

        ca_bundle = Path("/etc/ssl/certs/ca-certificates.crt")
        if not ca_bundle.is_file():
            raise AssertionError(f"system CA bundle is missing: {ca_bundle}")
        command = sandbox_command(
            binary,
            root,
            ("gateway", "--listen", "127.0.0.1:0"),
            argv0=argv0,
            environment={
                "PRODEX_HOME": str(app),
                "PRODEX_RUNTIME_LOG_DIR": str(logs),
                "SSL_CERT_FILE": "/ca-certificates.pem",
            },
        )
        separator = command.index("--")
        command[separator:separator] = ["--ro-bind", str(ca_bundle.resolve()), "/ca-certificates.pem"]
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = process.communicate(timeout=10)
            was_running = False
        except subprocess.TimeoutExpired:
            was_running = True
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=5)

        created = sorted(
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path not in (home, workspace)
        )
        return {
            "was_running": was_running,
            "returncode": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "created": created,
            "state_unchanged": state.read_bytes() == state_before and auth.read_bytes() == auth_before,
        }


class GatewayDefault01660Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.0 release")

    def test_without_provider_matches_the_active_profile_preflight(self):
        baseline, _ = isolated_cli(ORACLE, ("gateway",), "prodex")
        modex, created = isolated_cli(MODEX, ("gateway",), "modex")
        self.assertEqual((baseline.returncode, baseline.stdout), (1, b""))
        self.assertIn(b"no active profile selected", baseline.stderr)
        self.assertEqual(
            (modex.returncode, modex.stdout, modex.stderr),
            (baseline.returncode, baseline.stdout, baseline.stderr),
        )
        self.assertEqual(created, ["home/.prodex"])

    def test_dry_run_and_config_flags_remain_parser_errors(self):
        for arguments in (
            ("gateway", "--dry-run"),
            ("gateway", "--config", "/synthetic/config.toml"),
        ):
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_cli(ORACLE, arguments, "prodex")
                modex, modex_created = isolated_cli(MODEX, arguments, "modex")
                self.assertEqual((baseline.returncode, modex.returncode), (2, 2))
                self.assertEqual(
                    (modex.stdout, modex.stderr),
                    (normalize_cli(baseline.stdout), normalize_cli(baseline.stderr)),
                )
                self.assertEqual((baseline_created, modex_created), ([], []))

    def test_gateway_parse_diagnostics_match_active_release(self):
        secret = b"synthetic-secret-sentinel"
        cases = (
            (("gateway", "--listen", "-1"), 2),
            (("gateway", "--provider", "deepseek", "--listen", "--unknown"), 2),
            (("gateway", "--listen=127.0.0.1:0", "--provder"), 2),
            (("gateway", "--api-key=synthetic-secret-sentinel", "-x"), 2),
            (("gateway", "--api-key=synthetic-secret-sentinel", "--unknown"), 2),
            (("gateway", "--api-key=synthetic-secret-sentinel", "argument"), 2),
            (("gateway", "--listen"), 2),
            (("gateway", "--listen", "--provider"), 2),
            (("gateway", "--listen", "--help=bad"), 2),
            (("gateway", "--help", "--unknown"), 0),
            (("gateway", "--unknown", "--help"), 2),
            (("gateway", "--listen=127.0.0.1:0", "--help"), 0),
            (("gateway", "--", "--help"), 2),
        )
        for arguments, expected_status in cases:
            with self.subTest(arguments=arguments):
                baseline, baseline_created = isolated_cli(ORACLE, arguments, "prodex")
                modex, modex_created = isolated_cli(MODEX, arguments, "modex")
                self.assertEqual(baseline.returncode, expected_status)
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (baseline.returncode,
                     baseline.stdout.replace(b"prodex gateway", b"modex gateway"),
                     baseline.stderr.replace(b"prodex gateway", b"modex gateway")),
                )
                self.assertEqual((baseline_created, modex_created), ([], []))
                self.assertNotIn(secret, baseline.stdout + baseline.stderr + modex.stdout + modex.stderr)

    def test_profileless_config_matches_the_active_preflight(self):
        for model_provider, diagnostic in (
            ("openai", b"no active profile selected"),
            ("prodex-deepseek", b"gateway provider does not expose an OpenAI-compatible proxy"),
        ):
            with self.subTest(model_provider=model_provider):
                baseline = isolated_gateway_config(ORACLE, "prodex", model_provider)
                modex = isolated_gateway_config(MODEX, "modex", model_provider)
                self.assertEqual((baseline.returncode, baseline.stdout), (1, b""))
                self.assertEqual(
                    (modex.returncode, modex.stdout, modex.stderr),
                    (baseline.returncode, baseline.stdout, baseline.stderr),
                )
                self.assertIn(diagnostic, modex.stderr)

    def test_valid_selected_profile_keeps_modex_fail_closed(self):
        baseline = isolated_gateway_profile(ORACLE, "prodex")
        modex = isolated_gateway_profile(MODEX, "modex")
        self.assertTrue(baseline["was_running"], baseline["stderr"].decode("utf-8", "replace"))
        self.assertIn(b"Prodex gateway listening on http://127.0.0.1:", baseline["stdout"])
        self.assertEqual(baseline["stderr"], b"")
        self.assertFalse(modex["was_running"])
        self.assertEqual((modex["returncode"], modex["stdout"]), (1, b""))
        self.assertIn(b"existing application state is not implemented", modex["stderr"])
        self.assertNotIn(b"no active profile selected", modex["stderr"])
        self.assertNotIn(b"synthetic-profile-token", modex["stdout"] + modex["stderr"])
        self.assertTrue(modex["state_unchanged"])
        self.assertFalse(any("runtime-broker-" in path for path in modex["created"]))


if __name__ == "__main__":
    unittest.main()
