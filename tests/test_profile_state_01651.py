"""Populated profile listing against pinned Prodex releases."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_cli
from session_oracle import sandbox_command


ORACLE_01651 = Path(os.environ.get(
    "PRODEX_ORACLE_01651",
    Path.home() / ".cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu",
))
SHA256_01651 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
SHA256_04392 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
SYNTHETIC_SECRET = "synthetic-profile-secret-not-for-network-use"
RELEASE_LOCK_FILES = {
    "home/.prodex/profile-lifecycle.json.lock",
    "home/.prodex/runtime-housekeeping.last-run",
    "home/.prodex/runtime-housekeeping.lock",
    "home/.prodex/state.json.lock",
    "home/.prodex/update-check.lock",
}


def profile_fixture(root, active_profile="main"):
    home = root / "home"
    home.mkdir(mode=0o700)
    (root / "workspace").mkdir(mode=0o700)
    app = home / ".prodex"
    app.mkdir(mode=0o700)
    profile_home = app / "profiles/main"
    profile_home.mkdir(parents=True, mode=0o700)
    auth = profile_home / "auth.json"
    auth.write_text(json.dumps({"OPENAI_API_KEY": SYNTHETIC_SECRET}) + "\n")
    auth.chmod(0o600)
    state = {
        "schema_version": 1,
        "active_profile": active_profile,
        "profiles": {
            "main": {
                "codex_home": str(profile_home),
                "managed": True,
                "email": None,
                "provider": {"provider_kind": "openai"},
            },
        },
        "last_run_selected_at": {},
        "response_profile_bindings": {},
        "session_profile_bindings": {},
    }
    state_path = app / "state.json"
    state_path.write_text(json.dumps(state) + "\n")
    state_path.chmod(0o600)
    return state_path, auth


def files_under(root):
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def run_profile(binary, root, arguments, argv0):
    return subprocess.run(
        sandbox_command(binary, root, arguments, argv0=argv0),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )


class ProfileState01651Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not test_cli.MODEX.is_file():
            raise AssertionError("Build the actual Modex CLI first")
        for oracle, checksum in (
            (ORACLE_01651, SHA256_01651),
            (test_cli.ORACLE, SHA256_04392),
        ):
            if not oracle.is_file() or hashlib.sha256(oracle.read_bytes()).hexdigest() != checksum:
                raise AssertionError(f"Oracle checksum mismatch: {oracle}")

    def test_stateless_profile_help_and_parser_match_01651_without_mutation(self):
        for arguments, status in (
            (["profile", "--help"], 0),
            (["profile", "list", "--help"], 0),
            (["help", "profile"], 0),
            (["profile", "use", "--help"], 0),
            (["profile", "wat"], 2),
            (["profile", "list", "extra"], 2),
        ):
            with self.subTest(arguments=arguments):
                results = []
                for binary, argv0 in ((ORACLE_01651, "prodex"), (test_cli.MODEX, "modex")):
                    with tempfile.TemporaryDirectory(prefix="modex-profile-cli-01651-") as directory:
                        root = Path(directory)
                        (root / "home").mkdir(mode=0o700)
                        (root / "workspace").mkdir(mode=0o700)
                        result = run_profile(binary, root, arguments, argv0)
                        results.append((result, files_under(root)))

                baseline, baseline_files = results[0]
                modex, modex_files = results[1]
                self.assertEqual(baseline.returncode, status)
                self.assertEqual(modex.returncode, status)
                self.assertEqual(baseline_files, set())
                self.assertEqual(modex_files, set())
                self.assertEqual(
                    (modex.stdout, modex.stderr),
                    (baseline.stdout.replace(b"Usage: prodex ", b"Usage: modex "),
                     baseline.stderr.replace(b"Usage: prodex ", b"Usage: modex ")),
                )

    def test_populated_profile_listing_remains_fail_closed_without_release_locks(self):
        for oracle, argv0 in ((ORACLE_01651, "prodex"), (test_cli.ORACLE, "prodex")):
            with self.subTest(oracle=oracle):
                with tempfile.TemporaryDirectory(prefix="modex-profile-state-01651-") as directory:
                    baseline_root = Path(directory) / "baseline"
                    baseline_root.mkdir()
                    state_path, auth_path = profile_fixture(baseline_root)
                    baseline_files = files_under(baseline_root)
                    state_bytes = state_path.read_bytes()
                    auth_bytes = auth_path.read_bytes()

                    baseline = run_profile(oracle, baseline_root, ["profile", "list"], argv0)

                    self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                    self.assertIn(b"main", baseline.stdout)
                    self.assertNotIn(SYNTHETIC_SECRET.encode(), baseline.stdout)
                    self.assertEqual(state_path.read_bytes(), state_bytes)
                    self.assertEqual(auth_path.read_bytes(), auth_bytes)
                    self.assertEqual(files_under(baseline_root) - baseline_files, RELEASE_LOCK_FILES)

                    modex_root = Path(directory) / "modex"
                    modex_root.mkdir()
                    modex_state, modex_auth = profile_fixture(modex_root)
                    modex_files = files_under(modex_root)

                    modex = run_profile(test_cli.MODEX, modex_root, ["profile", "list"], "modex")

                    self.assertEqual(modex.returncode, 1)
                    self.assertEqual(modex.stdout, b"")
                    self.assertIn(b"has not implemented the requested command", modex.stderr)
                    self.assertNotIn(SYNTHETIC_SECRET.encode(), modex.stdout + modex.stderr)
                    self.assertEqual(modex_state.read_bytes(), state_bytes.replace(
                        str(baseline_root).encode(), str(modex_root).encode()
                    ))
                    self.assertEqual(modex_auth.read_bytes(), auth_bytes)
                    self.assertEqual(files_under(modex_root), modex_files)

    def test_releases_repair_missing_active_profile_while_modex_preserves_it(self):
        for oracle in (ORACLE_01651, test_cli.ORACLE):
            with self.subTest(oracle=oracle):
                with tempfile.TemporaryDirectory(prefix="modex-profile-repair-01651-") as directory:
                    baseline_root = Path(directory) / "baseline"
                    baseline_root.mkdir()
                    baseline_state, baseline_auth = profile_fixture(
                        baseline_root, active_profile=None
                    )
                    before_state = baseline_state.read_bytes()
                    before_auth = baseline_auth.read_bytes()

                    baseline = run_profile(oracle, baseline_root, ["profile", "list"], "prodex")

                    self.assertEqual((baseline.returncode, baseline.stderr), (0, b""))
                    self.assertIn(b"main", baseline.stdout)
                    self.assertNotIn(SYNTHETIC_SECRET.encode(), baseline.stdout)
                    self.assertNotEqual(baseline_state.read_bytes(), before_state)
                    self.assertEqual(json.loads(baseline_state.read_bytes())["active_profile"], "main")
                    self.assertEqual(baseline_auth.read_bytes(), before_auth)
                    self.assertTrue(RELEASE_LOCK_FILES.issubset(files_under(baseline_root)))

                    modex_root = Path(directory) / "modex"
                    modex_root.mkdir()
                    modex_state, modex_auth = profile_fixture(
                        modex_root, active_profile=None
                    )
                    modex_before_files = files_under(modex_root)
                    modex_before_state = modex_state.read_bytes()

                    modex = run_profile(
                        test_cli.MODEX, modex_root, ["profile", "list"], "modex"
                    )

                    self.assertEqual(modex.returncode, 1)
                    self.assertEqual(modex.stdout, b"")
                    self.assertNotIn(SYNTHETIC_SECRET.encode(), modex.stdout + modex.stderr)
                    self.assertEqual(modex_state.read_bytes(), modex_before_state)
                    self.assertEqual(modex_auth.read_bytes(), before_auth)
                    self.assertEqual(files_under(modex_root), modex_before_files)


if __name__ == "__main__":
    unittest.main()
