"""Exercise session resume selection in isolated real processes."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from session_oracle import SESSION_ID, fixture, sandbox_command
from test_cli import MODEX, ORACLE as ORACLE_04392
from test_cli_01651 import ORACLE as ORACLE_01651
from test_session_profile_04392 import profile_state, write_state


ORACLE_SHA256 = {
    "0.165.1": "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51",
    "0.439.2": "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e",
}


def write_session(root, session_id, *, archived=False):
    area = "archived_sessions" if archived else "sessions"
    session_dir = root / f"home/.codex/{area}/2026/10/24"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / f"rollout-{session_id}.jsonl").write_text(
        json.dumps({
            "timestamp": "2026-10-24T00:00:00Z",
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "cwd": str(root / "workspace"),
                "thread_name": "Synthetic resume session",
                "model_provider": "openai",
            },
        }) + "\n"
    )


def run_resume(
    binary, selector, *, duplicate=False, prefix_collision=False,
    locked=False, invalid_state=False,
):
    with tempfile.TemporaryDirectory(prefix="modex-session-resume-") as directory:
        root = Path(directory)
        fixture(root)
        if duplicate:
            write_session(root, SESSION_ID, archived=True)
        elif prefix_collision:
            write_session(root, SESSION_ID + "-long")
        if locked or invalid_state:
            state = root / "home/.prodex"
            state.mkdir(mode=0o700)
            if locked:
                (state / "state.json.lock").write_text("")
            if invalid_state:
                state_file = state / "state.json"
                state_file.write_text("{")
                state_file.chmod(0o600)
        result = subprocess.run(
            sandbox_command(binary, root, ["session", "resume", selector]),
            capture_output=True,
            timeout=15,
            check=False,
        )
        return (
            result.returncode,
            result.stdout.replace(str(root).encode(), b"<ROOT>"),
            result.stderr.replace(str(root).encode(), b"<ROOT>"),
        )


def run_unconfigured_resume(binary, selector, *, prefix_collision=False):
    with tempfile.TemporaryDirectory(prefix="modex-session-empty-resume-") as directory:
        root = Path(directory)
        fixture(root)
        if prefix_collision:
            write_session(root, SESSION_ID + "-long")
        before = {str(path.relative_to(root)) for path in root.rglob("*")}
        label = "modex" if binary == MODEX else "prodex"
        result = subprocess.run(
            sandbox_command(
                binary, root, ["session", "resume", selector], argv0=label
            ),
            capture_output=True,
            timeout=15,
            check=False,
        )
        after = {str(path.relative_to(root)) for path in root.rglob("*")}
        return (
            result.returncode,
            result.stdout.replace(str(root).encode(), b"<ROOT>"),
            result.stderr.replace(str(root).encode(), b"<ROOT>"),
            sorted(after - before),
        )


def run_bound_resume(binary, *, prodex_home_override=False):
    with tempfile.TemporaryDirectory(prefix="modex-session-bound-resume-") as directory:
        root = Path(directory)
        fixture(root)
        app_root = root / "home/.prodex"
        environment = None
        if prodex_home_override:
            app_root = root / "alternate-prodex-home"
            app_root.mkdir(mode=0o700)
            environment = {"PRODEX_HOME": str(app_root)}
            state_file = app_root / "state.json"
            state_file.write_text(json.dumps(profile_state(root)))
            state_file.chmod(0o600)
        else:
            state_file = write_state(root, profile_state(root))
        original_state = state_file.read_bytes()
        label = "modex" if binary == MODEX else "prodex"
        result = subprocess.run(
            sandbox_command(
                binary, root, ["session", "resume", SESSION_ID],
                argv0=label, environment=environment,
            ),
            capture_output=True,
            timeout=15,
            check=False,
        )
        codex_root = root / "home/.codex"
        app_entries = sorted(path.name for path in app_root.iterdir())
        session_locks = sorted(
            str(path.relative_to(codex_root))
            for path in codex_root.rglob("*")
            if path.is_file() and path.name.endswith(".lock")
        )
        return (
            result.returncode,
            result.stdout.replace(str(root).encode(), b"<ROOT>"),
            result.stderr.replace(str(root).encode(), b"<ROOT>"),
            state_file.read_bytes() == original_state,
            app_entries,
            session_locks,
        )


def run_shared_config_resume(binary, shared_mode):
    with tempfile.TemporaryDirectory(prefix="modex-session-config-resume-") as directory:
        root = Path(directory)
        fixture(root)
        default_shared_root = root / "home/.codex"
        if shared_mode == "default":
            shared_root = default_shared_root
            environment = None
        elif shared_mode == "absolute":
            shared_root = root / "alternate-codex-home"
            shutil.copytree(default_shared_root, shared_root)
            environment = {"PRODEX_SHARED_CODEX_HOME": str(shared_root)}
        else:
            app_root = root / "home/.prodex"
            app_root.mkdir(mode=0o700)
            shared_root = app_root / "alternate-codex-home"
            shutil.copytree(default_shared_root, shared_root)
            environment = {"PRODEX_SHARED_CODEX_HOME": "alternate-codex-home"}
        (shared_root / "config.toml").write_text(
            'model_provider = "prodex-deepseek"\n\n'
            "[model_providers.prodex-deepseek]\n"
            'name = "DeepSeek"\n'
            'base_url = "http://127.0.0.1:1"\n'
            'wire_api = "responses"\n'
            "requires_openai_auth = true\n"
        )
        before = {str(path.relative_to(root)) for path in root.rglob("*")}
        label = "modex" if binary == MODEX else "prodex"
        result = subprocess.run(
            sandbox_command(
                binary,
                root,
                ["session", "resume", SESSION_ID],
                argv0=label,
                environment=environment,
            ),
            capture_output=True,
            timeout=15,
            check=False,
        )
        after = {str(path.relative_to(root)) for path in root.rglob("*")}
        return (
            result.returncode,
            result.stdout.replace(str(root).encode(), b"<ROOT>"),
            result.stderr.replace(str(root).encode(), b"<ROOT>"),
            sorted(after - before),
            str(shared_root.relative_to(root)),
        )


class SessionResumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first with make build")
        for label, binary in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            digest = hashlib.sha256(binary.read_bytes()).hexdigest() if binary.is_file() else ""
            if digest != ORACLE_SHA256[label]:
                raise AssertionError(f"Pinned Prodex {label} Linux oracle is missing or changed")

    def test_missing_and_ambiguous_errors_match_both_releases(self):
        for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            for selector, duplicate, error in (
                ("missing-session", False, b"Error: session could not be resolved\n"),
                (" \t \u2000", False, b"Error: session could not be resolved\n"),
                ("019a1234", True, b"Error: session selector is ambiguous\n"),
            ):
                with self.subTest(release=label, selector=selector):
                    baseline = run_resume(oracle, selector, duplicate=duplicate)
                    modex = run_resume(MODEX, selector, duplicate=duplicate)
                    self.assertEqual(baseline, (1, b"", error))
                    self.assertEqual(modex, baseline)

    def test_valid_selection_stops_before_unmanaged_launch(self):
        expected = (
            1,
            b"",
            b"Prodex launch: preparing runtime launch...\n"
            b"Error: no active profile selected and no Codex-compatible profiles are available; use `prodex use --profile <name>` or pass --profile\n",
        )
        baseline_runs = []
        for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            for selector in (
                " \t" + SESSION_ID.upper() + " \t",
                "\u2000" + SESSION_ID.upper() + "\u00a0",
            ):
                with self.subTest(release=label, selector=repr(selector)):
                    baseline = run_unconfigured_resume(oracle, selector, prefix_collision=True)
                    self.assertEqual(baseline[:3], expected)
                    self.assertIn("home/.codex/.prodex-session-repair.lock", baseline[3])
                    self.assertIn("home/.codex/sessions/.prodex-maintenance.lock", baseline[3])
                    baseline_runs.append(baseline)
                    modex = run_unconfigured_resume(MODEX, selector, prefix_collision=True)
                    self.assertEqual(modex[:3], expected)
                    self.assertEqual(modex[3], ["home/.prodex"])
        self.assertEqual(baseline_runs[0], baseline_runs[2])
        self.assertEqual(baseline_runs[1], baseline_runs[3])

    def test_duplicate_exact_ids_are_not_deduplicated(self):
        for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            with self.subTest(release=label):
                expected = (1, b"", b"Error: session selector is ambiguous\n")
                self.assertEqual(run_resume(oracle, SESSION_ID, duplicate=True), expected)
                self.assertEqual(run_resume(MODEX, SESSION_ID, duplicate=True), expected)

    def test_state_load_failures_precede_session_selection(self):
        for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            for selector in ("missing-session", SESSION_ID):
                with self.subTest(release=label, selector=selector):
                    baseline = run_resume(oracle, selector, invalid_state=True)
                    self.assertEqual(baseline, (
                        1,
                        b"",
                        b"Error: failed to read <ROOT>/home/.prodex/state.json.last-good after primary load error: "
                        b"failed to parse <ROOT>/home/.prodex/state.json: EOF while parsing an object at line 1 "
                        b"column 1: No such file or directory (os error 2)\n",
                    ))
                    self.assertEqual(run_resume(MODEX, selector, invalid_state=True), (
                        1,
                        b"",
                        b"Error: locked state loading and recovery are not implemented\n",
                    ))

    def test_session_resume_keeps_state_lock_guard(self):
        lock_only = run_resume(MODEX, "missing-session", locked=True)
        self.assertEqual(lock_only, (
            1,
            b"",
            b"Error: locked state loading and recovery are not implemented\n",
        ))
        for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            with self.subTest(release=label):
                self.assertEqual(run_resume(oracle, "missing-session", locked=True), (
                    1, b"", b"Error: session could not be resolved\n"
                ))

    def test_bound_session_resume_requires_managed_launch(self):
        baseline_runs = []
        for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            with self.subTest(release=label):
                baseline = run_bound_resume(oracle)
                baseline_runs.append(baseline[:3])
                self.assertEqual(baseline[0:2], (1, b""))
                self.assertIn(b"Codex CLI is unavailable.", baseline[2])
                self.assertNotIn(b"SYNTHETIC_API_KEY_SENTINEL", baseline[2])
                self.assertFalse(baseline[3])
                self.assertIn("state.json.lock", baseline[4])
                self.assertIn("sessions/.prodex-maintenance.lock", baseline[5])
        self.assertEqual(baseline_runs[0], baseline_runs[1])

        modex = run_bound_resume(MODEX)
        self.assertEqual(modex[:3], (
            1,
            b"",
            b"Error: session resume requires managed profile authorization and launch, "
            b"which are not implemented\n",
        ))
        self.assertTrue(modex[3])
        self.assertEqual(modex[4], ["state.json"])
        self.assertEqual(modex[5], [])

    def test_explicit_prodex_home_state_blocks_empty_state_fallback(self):
        baseline_runs = []
        for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
            with self.subTest(release=label):
                baseline = run_bound_resume(oracle, prodex_home_override=True)
                baseline_runs.append(baseline[:3])
                self.assertIn(b"Codex CLI is unavailable.", baseline[2])
                self.assertFalse(baseline[3])
                modex = run_bound_resume(MODEX, prodex_home_override=True)
                self.assertEqual(modex[:3], (
                    1,
                    b"",
                    b"Error: session resume requires managed profile authorization and launch, "
                    b"which are not implemented\n",
                ))
                self.assertTrue(modex[3])
        self.assertEqual(baseline_runs[0], baseline_runs[1])

    def test_shared_home_config_blocks_empty_profile_fallback(self):
        for shared_mode in ("default", "absolute", "relative"):
            baseline_runs = []
            for label, oracle in (("0.165.1", ORACLE_01651), ("0.439.2", ORACLE_04392)):
                with self.subTest(shared_mode=shared_mode, release=label):
                    baseline = run_shared_config_resume(oracle, shared_mode)
                    baseline_runs.append(baseline[:3])
                    self.assertEqual(baseline[0:2], (1, b""))
                    self.assertIn(b"Detected model_provider 'prodex-deepseek' from config.toml.", baseline[2])
                    self.assertIn(b"Codex CLI is unavailable.", baseline[2])
                    self.assertIn(
                        f"{baseline[4]}/sessions/.prodex-maintenance.lock", baseline[3]
                    )
                    self.assertNotIn(b"SYNTHETIC_API_KEY_SENTINEL", baseline[2])
                    modex = run_shared_config_resume(MODEX, shared_mode)
                    self.assertEqual(modex[:3], (
                        1,
                        b"",
                        b"Error: session resume requires managed profile authorization and launch, "
                        b"which are not implemented\n",
                    ))
                    self.assertEqual(
                        modex[3], [] if shared_mode == "relative" else ["home/.prodex"]
                    )
            self.assertEqual(baseline_runs[0], baseline_runs[1])


if __name__ == "__main__":
    unittest.main()
