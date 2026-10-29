"""Compare the guarded Super dry-run slice with pinned release processes."""

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

from session_oracle import sandbox_command
from test_cli import MODEX, ORACLE as DEFAULT_ORACLE, ORACLE_SHA256
from test_cli_01651 import ORACLE as ORACLE_01651, ORACLE_SHA256 as ORACLE_SHA256_01651

ORACLE = Path(os.environ.get("PRODEX_ORACLE_04392", DEFAULT_ORACLE))
NODE_FIXTURE = MODEX.parent / "tests/node_version_fixture"


DRY_RUN_ARGS = (
    "super", "--dry-run", "--provider", "deepseek", "--api-key",
    "synthetic-dry-run-key", "--base-url", "http://127.0.0.1:8131/v1",
    "--no-presidio", "--no-sub-agent", "--skip-quota-check",
    "exec", "Bearer synthetic-prompt-secret-42",
)


def snapshot(root):
    result = {}
    for path in root.rglob("*"):
        info = path.lstat()
        mode = info.st_mode
        relative = path.relative_to(root).as_posix()
        if stat.S_ISDIR(mode):
            result[relative] = ("directory", mode & 0o777)
        elif stat.S_ISREG(mode):
            result[relative] = ("file", mode & 0o777, path.read_bytes())
        elif stat.S_ISLNK(mode):
            result[relative] = ("symlink", os.readlink(path))
        else:
            result[relative] = ("other", mode & 0o777)
    return result


def write_tool(path, marker):
    path.write_text(f'#!/bin/sh\nprintf called > "{marker}"\n')
    path.chmod(0o700)


def write_node(path):
    path.write_bytes(NODE_FIXTURE.read_bytes())
    path.chmod(0o700)


def run_dry_run(binary, argv0, prepare=None, *, arguments=DRY_RUN_ARGS,
                include_codex=True, environment=None, extra_binaries=()):
    with tempfile.TemporaryDirectory(prefix="modex-super-dry-run-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir(mode=0o700)
        binary_dir = root / "bin"
        binary_dir.mkdir(mode=0o700)
        if include_codex:
            codex = binary_dir / "codex"
            codex.write_text("#!/bin/sh\nprintf called > \"$CODEX_INVOKED_MARKER\"\n")
            codex.chmod(0o700)
        if prepare is not None:
            prepare(root)
        extra_environment = environment(root) if callable(environment) else (environment or {})
        before = snapshot(root)
        result = subprocess.run(
            sandbox_command(
                binary,
                root,
                list(arguments),
                argv0=argv0,
                environment={
                    "PATH": str(binary_dir) if include_codex else "",
                    "CODEX_INVOKED_MARKER": str(root / "codex-invoked"),
                    **extra_environment,
                },
                extra_binaries=extra_binaries,
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        return result, before, snapshot(root)


class SuperDryRun01651Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for binary, digest in ((ORACLE_01651, ORACLE_SHA256_01651),
                               (ORACLE, ORACLE_SHA256)):
            if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != digest:
                raise AssertionError(f"Prodex oracle checksum mismatch: {binary}")
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not NODE_FIXTURE.is_file() or NODE_FIXTURE.stat().st_mode & 0o111 == 0:
            raise AssertionError("Build the native Node version fixture with make unit-build")

    def test_dry_run_reads_shared_config_and_ignores_shared_history(self):
        def prepare(root):
            shared = root / "home/.codex"
            shared.mkdir(mode=0o700)
            config = shared / "config.toml"
            config.write_text('model = "synthetic-dry-run-model"\n')
            config.chmod(0o600)
            history = shared / "history.jsonl"
            history.write_text('{"synthetic":"preserve dry-run history"}\n')
            history.chmod(0o600)
            (shared / "sessions").mkdir(mode=0o700)

        outputs = {}
        for label, binary, argv0 in (("0.165.1", ORACLE_01651, "prodex"),
                                     ("0.439.2", ORACLE, "prodex"),
                                     ("Modex", MODEX, "modex")):
            with self.subTest(binary=label):
                result, before, after = run_dry_run(binary, argv0, prepare)
                self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
                output = result.stdout
                self.assertIn(b"synthetic-dry-run-model", output)
                self.assertIn(b"Bearer <redacted>", output)
                self.assertNotIn(b"synthetic-prompt-secret-42", output)
                self.assertNotIn(b"synthetic-dry-run-key", output)
                self.assertEqual(after, before)
                self.assertNotIn(b"called", output)
                outputs[label] = output
        self.assertEqual(outputs["0.165.1"], outputs["0.439.2"])
        self.assertEqual(outputs["0.165.1"], outputs["Modex"])

    def test_missing_codex_and_empty_path_still_match_release_report(self):
        outputs = []
        for label, binary, argv0 in (("0.165.1", ORACLE_01651, "prodex"),
                                     ("0.439.2", ORACLE, "prodex"),
                                     ("Modex", MODEX, "modex")):
            with self.subTest(binary=label):
                result, before, after = run_dry_run(binary, argv0, include_codex=False)
                self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
                self.assertIn(b"Binary: codex", result.stdout)
                self.assertIn(b"Codex/TUI not started because --dry-run was set.", result.stdout)
                self.assertEqual(after, before)
                outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])

    def test_configured_codex_and_model_overrides_take_precedence(self):
        arguments = list(DRY_RUN_ARGS)
        exec_index = arguments.index("exec")
        arguments[exec_index:exec_index] = ["--model", "synthetic-override-model"]
        outputs = []
        for label, binary, argv0 in (("0.165.1", ORACLE_01651, "prodex"),
                                     ("0.439.2", ORACLE, "prodex"),
                                     ("Modex", MODEX, "modex")):
            with self.subTest(binary=label):
                result, before, after = run_dry_run(
                    binary, argv0, arguments=arguments,
                    environment={"PRODEX_CODEX_BIN": "configured-codex"},
                )
                self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
                self.assertIn(b"Binary: configured-codex", result.stdout)
                self.assertIn(b"Model: synthetic-override-model", result.stdout)
                self.assertEqual(after, before)
                outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])

    def test_malformed_explicit_key_is_not_needed_or_exposed(self):
        arguments = list(DRY_RUN_ARGS)
        arguments[arguments.index("--api-key") + 1] = "synthetic malformed key with spaces"
        outputs = []
        for label, binary, argv0 in (("0.165.1", ORACLE_01651, "prodex"),
                                     ("0.439.2", ORACLE, "prodex"),
                                     ("Modex", MODEX, "modex")):
            with self.subTest(binary=label):
                result, before, after = run_dry_run(
                    binary, argv0, arguments=arguments,
                    environment={"DEEPSEEK_API_KEY": "synthetic-environment-key"},
                )
                self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
                self.assertNotIn(b"synthetic malformed key with spaces", result.stdout)
                self.assertNotIn(b"synthetic-environment-key", result.stdout)
                self.assertEqual(after, before)
                outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])

    def test_sensitive_codex_flag_values_are_redacted_in_separated_and_equals_forms(self):
        sensitive_flags = (
            "--authorization", "--api-key", "--x-api-key", "--auth-key", "--cookie",
            "--set-cookie", "--token", "--access-token", "--refresh-token", "--id-token",
            "--secret", "--password", "--credential", "--credentials", "--email",
            "--github-login", "--profile-arn", "--profile-name-upstream", "--start-url",
            "--account-id", "--chatgpt-account-id", "--proxy-authorization", "--custom-token",
            "--custom-api-key", "--private-key", "--custom-secret", "--custom-password",
            "--custom-cookie", "--custom-credential",
        )
        for form in ("separated", "equals"):
            arguments = list(DRY_RUN_ARGS)
            values = []
            codex_arguments = ["--"]
            for index, flag in enumerate(sensitive_flags):
                secret = f"synthetic-cli-secret-{form}-{index}"
                values.append(secret.encode())
                codex_arguments.append(flag if form == "separated" else flag + "=" + secret)
                if form == "separated":
                    codex_arguments.append(secret)
            insert_at = arguments.index("exec") + 1
            arguments[insert_at:insert_at] = codex_arguments
            outputs = []
            for label, binary, argv0 in (("0.165.1", ORACLE_01651, "prodex"),
                                         ("0.439.2", ORACLE, "prodex"),
                                         ("Modex", MODEX, "modex")):
                with self.subTest(form=form, binary=label):
                    result, before, after = run_dry_run(binary, argv0, arguments=arguments)
                    self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
                    for secret in values:
                        self.assertNotIn(secret, result.stdout)
                        self.assertNotIn(secret, result.stderr)
                    self.assertEqual(after, before)
                    outputs.append(result.stdout)
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(outputs[0], outputs[2])

    def test_chained_sensitive_flags_redact_more_strictly_than_releases(self):
        secret = b"synthetic-secret-42"
        arguments = list(DRY_RUN_ARGS)
        insert_at = arguments.index("exec") + 1
        arguments[insert_at:insert_at] = ["--", "--api-key", "--password", secret.decode()]
        outputs = {}
        for label, binary, argv0 in (("0.165.1", ORACLE_01651, "prodex"),
                                     ("0.439.2", ORACLE, "prodex"),
                                     ("Modex", MODEX, "modex")):
            with self.subTest(binary=label):
                result, before, after = run_dry_run(binary, argv0, arguments=arguments)
                self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
                self.assertEqual(after, before)
                if label == "Modex":
                    self.assertNotIn(
                        secret,
                        result.stdout + result.stderr,
                        "Modex exposed a synthetic sensitive value",
                    )
                else:
                    self.assertIn(secret, result.stdout, f"{label} baseline leak control changed")
                    self.assertNotIn(secret, result.stderr, f"{label} wrote the synthetic value to stderr")
                outputs[label] = result.stdout
        self.assertEqual(outputs["0.165.1"], outputs["0.439.2"])
        self.assertNotEqual(outputs["Modex"], outputs["0.165.1"])

    def test_node_without_npx_matches_release_optional_tool_status(self):
        def prepare(root):
            write_node(root / "bin/node")

        outputs = []
        for label, binary, argv0 in (("0.165.1", ORACLE_01651, "prodex"),
                                     ("0.439.2", ORACLE, "prodex"),
                                     ("Modex", MODEX, "modex")):
            with self.subTest(binary=label):
                result, before, after = run_dry_run(
                    binary, argv0, prepare, extra_binaries=(NODE_FIXTURE,)
                )
                self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
                self.assertIn(b"playwright-mcp: skipped (npx was not found on PATH)", result.stdout)
                self.assertIn(b"Ponytail 4.9.0+ was not found under a managed optional-tool root", result.stdout)
                self.assertEqual(after, before)
                outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])

    def test_proxy_environment_secret_and_path_controls_are_redacted(self):
        def environment(root):
            workspace = root / "workspace"
            return {
                "NO_PROXY": f"Bearer synthetic-proxy-secret,{workspace}/proxy\ncontrol",
                "no_proxy": "Authorization: Bearer synthetic-lower-proxy-secret",
            }

        outputs = []
        secrets = (b"synthetic-proxy-secret", b"synthetic-lower-proxy-secret")
        for label, binary, argv0 in (("0.165.1", ORACLE_01651, "prodex"),
                                     ("0.439.2", ORACLE, "prodex"),
                                     ("Modex", MODEX, "modex")):
            with self.subTest(binary=label):
                result, before, after = run_dry_run(binary, argv0, environment=environment)
                self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
                for secret in secrets:
                    self.assertNotIn(secret, result.stdout)
                    self.assertNotIn(secret, result.stderr)
                self.assertIn(b"<redacted-path>/proxy", result.stdout)
                self.assertEqual(after, before)
                outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0], outputs[2])

    def test_valid_profile_state_is_read_by_releases_but_modex_stays_fail_closed(self):
        def prepare(root):
            app = root / "home/.prodex"
            profile = app / "profiles/main"
            profile.mkdir(parents=True, mode=0o700)
            auth = profile / "auth.json"
            auth.write_text(json.dumps({"OPENAI_API_KEY": "synthetic-profile-secret-not-for-network-use"}) + "\n")
            auth.chmod(0o600)
            state = {
                "schema_version": 1,
                "active_profile": "main",
                "profiles": {"main": {
                    "codex_home": str(profile),
                    "managed": True,
                    "email": None,
                    "provider": {"provider_kind": "openai"},
                }},
                "last_run_selected_at": {},
                "response_profile_bindings": {},
                "session_profile_bindings": {},
            }
            state_path = app / "state.json"
            state_path.write_text(json.dumps(state) + "\n")
            state_path.chmod(0o600)

        outputs = []
        for label, binary, argv0 in (("0.165.1", ORACLE_01651, "prodex"),
                                     ("0.439.2", ORACLE, "prodex")):
            with self.subTest(binary=label):
                result, before, after = run_dry_run(binary, argv0, prepare)
                self.assertEqual((result.returncode, result.stderr), (0, b""), result.stderr)
                self.assertIn(b"Codex/TUI not started because --dry-run was set.", result.stdout)
                self.assertNotIn(b"synthetic-profile-secret-not-for-network-use", result.stdout)
                self.assertEqual(after, before)
                outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])

        result, before, after = run_dry_run(MODEX, "modex", prepare)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"requires an empty profiles directory", result.stderr)
        self.assertEqual(after, before)

    def test_installed_optional_tools_fail_closed_without_launching_them(self):
        cases = (
            ("path command", lambda root: write_tool(root / "bin/rtk", root / "rtk-invoked")),
            ("managed tool", lambda root: (root / "home/.local/share/prodex-optimizers/caveman/4.0.1").mkdir(parents=True)),
            ("node and npx", lambda root: (write_node(root / "bin/node"), write_tool(root / "bin/npx", root / "npx-invoked"))),
        )
        for label, prepare_tool in cases:
            with self.subTest(tool=label):
                def prepare(root):
                    prepare_tool(root)

                result, before, after = run_dry_run(MODEX, "modex", prepare)
                self.assertEqual(result.returncode, 1)
                self.assertIn(b"cannot report installed optional tools", result.stderr)
                self.assertEqual(after, before)
                self.assertNotIn("rtk-invoked", after)
                self.assertNotIn("npx-invoked", after)

    def test_invalid_state_recovery_lock_mismatch_stays_visible(self):
        def prepare(root):
            app = root / "home/.prodex"
            app.mkdir(mode=0o700)
            state = app / "state.json"
            state.write_text("{broken\n")
            state.chmod(0o600)

        for label, binary, argv0 in (("0.165.1", ORACLE_01651, "prodex"),
                                     ("0.439.2", ORACLE, "prodex")):
            with self.subTest(binary=label):
                result, before, after = run_dry_run(binary, argv0, prepare)
                self.assertEqual(result.returncode, 1)
                self.assertIn("home/.prodex/state.json.lock", after)
                self.assertNotIn("home/.prodex/state.json.lock", before)

        result, before, after = run_dry_run(MODEX, "modex", prepare)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"cannot reconcile existing application state", result.stderr)
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
