"""Profile-bound session listing against both pinned release binaries."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest

import test_cli
from session_oracle import SESSION_ID, fixture, sandbox_command
from test_session_report_01651 import ORACLE as ORACLE_01651, SHA256 as SHA256_01651


ORACLE_04392_SHA256 = "a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e"
RETENTION_SECONDS = 30 * 24 * 60 * 60
CONFLICT_PROFILE = "__prodex_hard_binding_conflict__"


def profile_state(root, profile_name="main", bound_at=None, *, identity=None, profiles=None):
    if bound_at is None:
        bound_at = int(time.time())
    if profiles is None:
        profiles = {
            "main": {"codex_home": str(root / "home/.codex"), "managed": False},
        }
    binding = {"profile_name": profile_name, "bound_at": bound_at}
    if identity is not None:
        binding["binding_identity"] = identity
    return {
        "schema_version": 1,
        "active_profile": "main",
        "profiles": profiles,
        "last_run_selected_at": {},
        "response_profile_bindings": {},
        "session_profile_bindings": {SESSION_ID: binding},
    }


def write_state(root, value):
    return write_state_text(root, json.dumps(value))


def write_state_text(root, contents):
    app_root = root / "home/.prodex"
    app_root.mkdir(mode=0o700, exist_ok=True)
    path = app_root / "state.json"
    path.write_text(contents)
    path.chmod(0o600)
    return path


def command_output(binary, root, arguments, timeout=15):
    argv0 = "modex" if binary == test_cli.MODEX else "prodex"
    return subprocess.run(
        sandbox_command(binary, root, arguments, argv0=argv0),
        capture_output=True, timeout=timeout, check=False,
    )


def normalize_root(stdout, root):
    return stdout.replace(str(root).encode(), b"<ROOT>")


class SessionProfile04392Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        for binary, expected in (
            (ORACLE_01651, SHA256_01651),
            (test_cli.ORACLE, ORACLE_04392_SHA256),
        ):
            if not binary.is_file() or hashlib.sha256(binary.read_bytes()).hexdigest() != expected:
                raise AssertionError(f"Oracle checksum mismatch: {binary}")

    def test_profile_output_filters_and_query_match_both_releases(self):
        arguments = (
            ["session", "list", "--json"],
            ["session", "list", "--json", "--profile", "main"],
            ["session", "list", "--json", "--profile", "missing"],
            ["session", "list", "--id-only", "--query", "main"],
        )
        for reference in (ORACLE_01651, test_cli.ORACLE):
            outputs = {}
            for label, binary in (("reference", reference), ("modex", test_cli.MODEX)):
                with tempfile.TemporaryDirectory(prefix="modex-session-profile-04392-") as directory:
                    root = Path(directory)
                    fixture(root)
                    state_path = write_state(root, profile_state(root))
                    state_bytes = state_path.read_bytes()
                    app_root = root / "home/.prodex"
                    backup = app_root / "state.json.last-good"
                    backup.write_bytes(b"invalid backup ignored with valid primary\n")
                    backup.chmod(0o600)
                    lock = app_root / "state.json.lock"
                    lock.write_bytes(b"synthetic lock marker\n")
                    lock.chmod(0o600)
                    rows = []
                    for argv in arguments:
                        result = command_output(binary, root, argv)
                        self.assertEqual(result.returncode, 0, result.stderr.decode())
                        self.assertEqual(result.stderr, b"")
                        rows.append(normalize_root(result.stdout, root))
                        self.assertEqual(state_path.read_bytes(), state_bytes)
                        self.assertEqual(backup.read_bytes(), b"invalid backup ignored with valid primary\n")
                        self.assertEqual(lock.read_bytes(), b"synthetic lock marker\n")
                    outputs[label] = rows

            self.assertEqual(outputs["modex"], outputs["reference"])
            report = json.loads(outputs["modex"][0])
            self.assertEqual((report[0]["id"], report[0]["profile"]), (SESSION_ID, "main"))
            self.assertEqual([item["id"] for item in json.loads(outputs["modex"][1])], [SESSION_ID])
            self.assertEqual(json.loads(outputs["modex"][2]), [])
            self.assertEqual(outputs["modex"][3], f"{SESSION_ID}\n".encode())

    def test_empty_profile_and_session_identifiers_preserve_presence(self):
        bound_at = int(time.time())
        cases = (("bound-empty-profile", "", ""), ("empty-session-id", "main", None))
        arguments = (
            ["session", "list", "--json"],
            ["session", "list", "--json", "--profile", ""],
            ["session", "list", "--json", "--profile", "main"],
        )
        for reference in (ORACLE_01651, test_cli.ORACLE):
            for label, profile_name, expected_profile in cases:
                with tempfile.TemporaryDirectory(prefix="modex-session-empty-id-04392-") as directory:
                    root = Path(directory)
                    fixture(root)
                    profiles = {
                        profile_name: {"codex_home": str(root / "home/.codex"), "managed": False},
                    }
                    state = profile_state(root, profile_name=profile_name, bound_at=bound_at, profiles=profiles)
                    if not profile_name:
                        state["active_profile"] = ""
                    if label == "empty-session-id":
                        state["session_profile_bindings"] = {
                            "": {"profile_name": profile_name, "bound_at": bound_at},
                        }
                    write_state(root, state)
                    outputs = {}
                    for name, binary in (("reference", reference), ("modex", test_cli.MODEX)):
                        rows = []
                        for argv in arguments:
                            result = command_output(binary, root, argv)
                            self.assertEqual(result.returncode, 0, result.stderr.decode())
                            rows.append(normalize_root(result.stdout, root))
                        outputs[name] = rows
                self.assertEqual(outputs["modex"], outputs["reference"], label)
                self.assertEqual(json.loads(outputs["modex"][0])[0]["profile"], expected_profile)
                self.assertEqual(json.loads(outputs["modex"][1]), json.loads(outputs["modex"][0]) if expected_profile == "" else [])
                self.assertEqual(json.loads(outputs["modex"][2]), [])

    def test_binding_retention_identity_and_conflict_match_both_releases(self):
        now = int(time.time())
        identity = {
            "provider": "openai",
            "credential_identity": "sha256:" + "a" * 64,
            "endpoint_identity": "sha256:" + "b" * 64,
        }
        cases = (
            ("expired", profile_state(
                root=Path("/fixture"), bound_at=now - RETENTION_SECONDS - 60,
            ), None),
            ("identity-keeps-binding", profile_state(
                root=Path("/fixture"), profile_name="orphan", bound_at=now,
                identity=identity, profiles={},
            ), "orphan"),
            ("conflict-keeps-binding", profile_state(
                root=Path("/fixture"), profile_name=CONFLICT_PROFILE, bound_at=1,
                profiles={},
            ), CONFLICT_PROFILE),
        )
        for reference in (ORACLE_01651, test_cli.ORACLE):
            for label, state, expected_profile in cases:
                outputs = []
                for binary in (reference, test_cli.MODEX):
                    with tempfile.TemporaryDirectory(prefix="modex-session-binding-04392-") as directory:
                        root = Path(directory)
                        fixture(root)
                        # The values above only depend on profile membership and binding metadata.
                        write_state(root, state)
                        result = command_output(binary, root, ["session", "list", "--json"])
                        self.assertEqual(result.returncode, 0, result.stderr.decode())
                        outputs.append(normalize_root(result.stdout, root))
                self.assertEqual(outputs[1], outputs[0], label)
                report = json.loads(outputs[1])[0]
                self.assertEqual(report["profile"], expected_profile, label)

    def test_binding_cap_ties_keep_last_2048_session_ids(self):
        bound_at = int(time.time())
        for larger_ids, expected_profile in ((2047, "main"), (2048, None)):
            for reference in (ORACLE_01651, test_cli.ORACLE):
                outputs = []
                with tempfile.TemporaryDirectory(prefix="modex-session-binding-cap-04392-") as directory:
                    root = Path(directory)
                    fixture(root)
                    state = profile_state(root, bound_at=bound_at)
                    bindings = {
                        SESSION_ID: {"profile_name": "main", "bound_at": bound_at},
                    }
                    for index in range(larger_ids):
                        bindings[f"z-unused-{index:05d}"] = {
                            "profile_name": "main", "bound_at": bound_at,
                        }
                    state["session_profile_bindings"] = bindings
                    write_state(root, state)
                    for binary in (reference, test_cli.MODEX):
                        result = command_output(binary, root, ["session", "list", "--json"])
                        self.assertEqual(result.returncode, 0, result.stderr.decode())
                        outputs.append(normalize_root(result.stdout, root))
                self.assertEqual(outputs[1], outputs[0])
                reports = json.loads(outputs[1])
                self.assertEqual(reports[0]["profile"] if reports else None, expected_profile)

    def test_duplicate_binding_keys_use_the_final_value(self):
        bound_at = int(time.time())
        for reference in (ORACLE_01651, test_cli.ORACLE):
            outputs = []
            with tempfile.TemporaryDirectory(prefix="modex-session-binding-duplicate-04392-") as directory:
                root = Path(directory)
                fixture(root)
                state = profile_state(
                    root, bound_at=bound_at,
                    profiles={
                        "main": {"codex_home": str(root / "home/.codex"), "managed": False},
                        "other": {"codex_home": str(root / "home/.codex"), "managed": False},
                    },
                )
                state["session_profile_bindings"] = {}
                prefix = json.dumps(state)
                duplicate_map = (
                    '"session_profile_bindings": {'
                    + json.dumps(SESSION_ID) + ': {"profile_name":"main","bound_at":' + str(bound_at) + '},'
                    + json.dumps(SESSION_ID) + ': {"profile_name":"other","bound_at":' + str(bound_at) + '}'
                    + '}'
                )
                contents = prefix.replace('"session_profile_bindings": {}', duplicate_map)
                self.assertNotEqual(contents, prefix)
                write_state_text(root, contents)
                for binary in (reference, test_cli.MODEX):
                    result = command_output(binary, root, ["session", "list", "--json"])
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    outputs.append(normalize_root(result.stdout, root))
            self.assertEqual(outputs[1], outputs[0])
            self.assertEqual(json.loads(outputs[1])[0]["profile"], "other")

    def test_16384_binding_maps_and_profiles_complete_through_production_cli(self):
        count = 16_384
        bound_at = int(time.time())
        for reference in (ORACLE_01651, test_cli.ORACLE):
            with tempfile.TemporaryDirectory(prefix="modex-session-binding-stress-04392-") as directory:
                root = Path(directory)
                fixture(root)
                final_profile = f"profile-{count - 1:05d}"
                state = profile_state(root, profile_name=final_profile, bound_at=bound_at)
                state["active_profile"] = final_profile
                state["profiles"] = {
                    f"profile-{index:05d}": {
                        "codex_home": str(root / "home/.codex"), "managed": False,
                    }
                    for index in range(count)
                }
                state["response_profile_bindings"] = {
                    f"response-{index:05d}": {
                        "profile_name": final_profile, "bound_at": bound_at,
                    }
                    for index in range(count)
                }
                session_count = 2048
                state["session_profile_bindings"] = {
                    SESSION_ID: {"profile_name": final_profile, "bound_at": bound_at + count},
                    **{
                        f"z-unused-{index:05d}": {
                            "profile_name": final_profile, "bound_at": bound_at,
                        }
                        for index in range(session_count - 1)
                    },
                }
                write_state(root, state)
                started = time.monotonic()
                reference_result = command_output(reference, root, ["session", "list", "--json"], timeout=30)
                reference_elapsed = time.monotonic() - started
                started = time.monotonic()
                modex = command_output(test_cli.MODEX, root, ["session", "list", "--json"], timeout=30)
                modex_elapsed = time.monotonic() - started
                self.assertEqual(reference_result.returncode, 0, reference_result.stderr.decode())
                self.assertEqual(modex.returncode, 0, modex.stderr.decode())
                self.assertEqual(normalize_root(modex.stdout, root), normalize_root(reference_result.stdout, root))
                reports = json.loads(modex.stdout)
                self.assertEqual(len(reports), 1)
                self.assertEqual(reports[0]["profile"], final_profile)
                self.assertLess(modex_elapsed, 30)
                self.assertLess(reference_elapsed, 30)

    def test_2048_session_reports_use_the_retained_profile_index(self):
        count = 2048
        bound_at = int(time.time())
        for reference in (ORACLE_01651, test_cli.ORACLE):
            with tempfile.TemporaryDirectory(prefix="modex-session-profile-index-04392-") as directory:
                root = Path(directory)
                work = fixture(root)
                shared = root / "home/.codex/sessions/2026/10/24"
                session_ids = [SESSION_ID, *(f"session-{index:04d}" for index in range(count - 1))]
                bindings = {}
                timestamp = "2026-10-24T00:00:00Z"
                for session_id in session_ids:
                    bindings[session_id] = {"profile_name": "main", "bound_at": bound_at}
                    if session_id == SESSION_ID:
                        continue
                    (shared / f"rollout-{session_id}.jsonl").write_text(
                        json.dumps({
                            "timestamp": timestamp,
                            "type": "session_meta",
                            "payload": {"id": session_id, "timestamp": timestamp, "cwd": str(work)},
                        }) + "\n"
                    )
                state = profile_state(root, bound_at=bound_at)
                state["session_profile_bindings"] = bindings
                write_state(root, state)
                outputs = []
                for binary in (reference, test_cli.MODEX):
                    result = command_output(binary, root, ["session", "list", "--json"], timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    outputs.append(normalize_root(result.stdout, root))
                self.assertEqual(outputs[1], outputs[0])
                reports = json.loads(outputs[1])
                self.assertEqual(len(reports), count)
                self.assertEqual({report["id"] for report in reports}, set(session_ids))
                self.assertTrue(all(report["profile"] == "main" for report in reports))

    def test_invalid_primary_keeps_backup_recovery_fail_closed_without_modex_writes(self):
        for reference in (ORACLE_01651, test_cli.ORACLE):
            observations = {}
            for label, binary in (("reference", reference), ("modex", test_cli.MODEX)):
                with tempfile.TemporaryDirectory(prefix="modex-session-backup-04392-") as directory:
                    root = Path(directory)
                    fixture(root)
                    state = profile_state(root)
                    primary = root / "home/.prodex/state.json"
                    primary.parent.mkdir(mode=0o700)
                    backup = primary.with_name("state.json.last-good")
                    backup_bytes = json.dumps(state).encode()
                    primary.write_bytes(b"{invalid primary\n")
                    primary.chmod(0o600)
                    backup.write_bytes(backup_bytes)
                    backup.chmod(0o600)
                    before_primary = primary.read_bytes()
                    result = command_output(binary, root, ["session", "list", "--json", "--profile", "main"])
                    observations[label] = (
                        result.returncode,
                        result.stdout,
                        result.stderr,
                        primary.read_bytes(),
                        backup.read_bytes(),
                        before_primary,
                        backup_bytes,
                    )
            self.assertEqual(observations["reference"][0], 0, observations["reference"][2])
            self.assertEqual(json.loads(observations["reference"][1])[0]["profile"], "main")
            recovered = json.loads(observations["reference"][3])
            backup_state = json.loads(observations["reference"][6])
            self.assertEqual(recovered["active_profile"], backup_state["active_profile"])
            self.assertEqual(recovered["profiles"]["main"]["codex_home"], backup_state["profiles"]["main"]["codex_home"])
            self.assertEqual(recovered["profiles"]["main"]["managed"], backup_state["profiles"]["main"]["managed"])
            self.assertNotEqual(observations["reference"][3], observations["reference"][5])
            self.assertEqual(observations["modex"][:3], (
                1, b"", b"Error: locked state loading and recovery are not implemented\n",
            ))
            self.assertEqual(observations["modex"][3:5], (
                observations["modex"][5], observations["modex"][6],
            ))

    def test_unsafe_state_paths_fail_closed(self):
        for reference in (ORACLE_01651, test_cli.ORACLE):
            for link_target in ("live", "missing"):
                observations = {}
                with tempfile.TemporaryDirectory(prefix="modex-session-state-link-04392-") as directory:
                    root = Path(directory)
                    fixture(root)
                    app_root = root / "home/.prodex"
                    app_root.mkdir(mode=0o700)
                    outside = root / "outside-state.json"
                    outside_bytes = json.dumps(profile_state(root)).encode()
                    outside.write_bytes(outside_bytes)
                    outside.chmod(0o600)
                    target = outside if link_target == "live" else root / "missing-state.json"
                    state_link = app_root / "state.json"
                    state_link.symlink_to(target)
                    for label, binary in (("reference", reference), ("modex", test_cli.MODEX)):
                        result = command_output(binary, root, ["session", "list", "--json"])
                        observations[label] = result
                        self.assertEqual(outside.read_bytes(), outside_bytes)
                        self.assertTrue(state_link.is_symlink())
                        self.assertEqual(os.readlink(state_link), str(target))
                if link_target == "live":
                    self.assertNotEqual(observations["reference"].returncode, 0)
                    self.assertEqual(observations["reference"].stdout, b"")
                else:
                    # Frozen Prodex treats a dangling state symlink as absent; Modex rejects it without mutation.
                    self.assertEqual(observations["reference"].returncode, 0)
                    report = json.loads(observations["reference"].stdout)
                    self.assertIsNone(report[0]["profile"])
                self.assertNotEqual(observations["modex"].returncode, 0)
                self.assertEqual(observations["modex"].stdout, b"")

    def test_world_readable_state_is_rejected_without_exposing_profile_data(self):
        for reference in (ORACLE_01651, test_cli.ORACLE):
            with tempfile.TemporaryDirectory(prefix="modex-session-state-mode-04392-") as directory:
                root = Path(directory)
                fixture(root)
                state_path = write_state(root, profile_state(root))
                state_bytes = state_path.read_bytes()
                state_path.chmod(0o644)
                baseline = command_output(reference, root, ["session", "list", "--json", "--profile", "main"])
                modex = command_output(test_cli.MODEX, root, ["session", "list", "--json", "--profile", "main"])
                self.assertEqual(baseline.returncode, 0, baseline.stderr.decode())
                self.assertEqual(json.loads(baseline.stdout)[0]["profile"], "main")
                self.assertEqual(modex.returncode, 1)
                self.assertEqual(modex.stdout, b"")
                self.assertIn(b"locked state loading and recovery", modex.stderr)
                self.assertEqual(state_path.read_bytes(), state_bytes)

    def test_concurrent_atomic_state_replacements_never_yield_mixed_profile_data(self):
        with tempfile.TemporaryDirectory(prefix="modex-session-state-race-04392-") as directory:
            root = Path(directory)
            fixture(root)
            app_root = root / "home/.prodex"
            app_root.mkdir(mode=0o700)
            padding = "x" * (8 * 1024 * 1024)
            paths = []
            for profile in ("main", "other"):
                state = profile_state(root, profile_name=profile)
                state["padding"] = padding
                path = app_root / ("snapshot-" + profile)
                path.write_text(json.dumps(state))
                path.chmod(0o600)
                paths.append(path)
            state_path = app_root / "state.json"
            state_path.write_bytes(paths[0].read_bytes())
            state_path.chmod(0o600)
            stop = threading.Event()
            swaps = [0]

            def replace_state():
                index = 0
                temporary = app_root / "state-replacement"
                while not stop.is_set():
                    try:
                        os.link(paths[index], temporary)
                        os.replace(temporary, state_path)
                        swaps[0] += 1
                        index = 1 - index
                    except FileNotFoundError:
                        continue

            replacer = threading.Thread(target=replace_state, daemon=True)
            replacer.start()
            try:
                result = command_output(
                    test_cli.MODEX, root,
                    ["session", "list", "--json", "--profile", "main"],
                )
            finally:
                stop.set()
                replacer.join(timeout=2)
            self.assertGreater(swaps[0], 0)
            if result.returncode == 0:
                reports = json.loads(result.stdout)
                self.assertLessEqual(len(reports), 1)
                if reports:
                    self.assertEqual(reports[0]["profile"], "main")
            else:
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"locked state loading and recovery", result.stderr)


if __name__ == "__main__":
    unittest.main()
