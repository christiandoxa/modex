"""Active Prodex 0.166.2 session-list checks for compound and archived files."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from compression import zstd

from capture_session_zstd import install_case, observe
from test_active_baseline_01662 import MODEX, ORACLE, ORACLE_SHA256
from session_oracle import SESSION_ID, fixture
from test_sessions import compare_outputs


PARENT_ID = "019a1234-5678-7123-8123-012345678901"
CHILD_ID = "019a1234-5678-7123-8123-012345678902"
COMPOUND_ID = "019a1234-5678-7123-8123-012345678903"


def install_fixture(root):
    for path in (root / "home/.codex/sessions", root / "home/.codex/archived_sessions"):
        path.mkdir(parents=True, exist_ok=True)
    for path in (root / "home/.codex/sessions").rglob("*.jsonl"):
        path.unlink()

    def record(session_id, title, timestamp, parent=None):
        payload = {
            "id": session_id,
            "cwd": str(root / "workspace"),
            "thread_name": title,
            "model_provider": "openai",
        }
        if parent:
            payload["source"] = {
                "subagent": {"thread_spawn": {"parent_thread_id": parent}}
            }
        return {
            "timestamp": timestamp,
            "type": "session_meta",
            "payload": payload,
        }

    archived_parent = root / f"home/.codex/archived_sessions/rollout-{PARENT_ID}.jsonl.zst"
    archived_parent.write_bytes(zstd.compress(
        (json.dumps(record(PARENT_ID, "Archived parent", "2026-10-24T01:00:00Z")) + "\n").encode(),
        level=1,
    ))

    compressed_child = root / f"home/.codex/sessions/rollout-{CHILD_ID}.jsonl.zst"
    compressed_child.write_bytes(zstd.compress(
        (json.dumps(record(CHILD_ID, "Compressed child", "2026-10-24T03:00:00Z", PARENT_ID)) + "\n").encode(),
        level=1,
    ))

    # The final .json suffix wins; the preceding text remains part of the filename.
    compound_json = root / "home/.codex/sessions/rollout-compound.jsonl.zst.json"
    compound_json.write_text(
        json.dumps(record(COMPOUND_ID, "Compound suffix", "2026-10-24T02:00:00Z")),
        encoding="utf-8",
    )


def install_typed_metadata_conflict(root):
    path = next((root / "home/.codex/sessions").rglob("*.jsonl"))
    record = {
        "timestamp": "2026-10-24T00:00:00Z",
        "type": "session_meta",
        "id": "root-id",
        "payload": {
            "id": 7,
            "session_id": "metadata-fallback",
            "thread_name": False,
            "title": "Fallback thread",
            "cwd": None,
            "metadata": {
                "cwd": str(root / "workspace"),
                "model_provider": "fallback-provider",
            },
            "model_provider": [],
            "source": {"subagent": {"thread_spawn": {"parent_thread_id": 23}}},
            "parent_thread_id": "fallback-parent",
        },
    }
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")


def install_tied_duplicate_ids(root):
    sessions = root / "home/.codex/sessions"
    for path in sessions.rglob("*"):
        if path.is_file():
            path.unlink()
    for name, title in (("a.jsonl", "First path"), ("z.json", "Second path")):
        record = {
            "timestamp": "2026-10-24T01:00:00Z",
            "type": "session_meta",
            "payload": {"id": "duplicate-id", "thread_name": title},
        }
        (sessions / name).write_text(json.dumps(record) + "\n", encoding="utf-8")


class SessionInspection01662Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEX.is_file():
            raise AssertionError("Build Modex first")
        if not ORACLE.is_file() or hashlib.sha256(ORACLE.read_bytes()).hexdigest() != ORACLE_SHA256:
            raise AssertionError("PRODEX_ORACLE must identify the verified 0.166.2 release")

    def test_compressed_archived_parent_and_compound_suffix_filters(self):
        cases = (
            (["session", "list", "--json"], [CHILD_ID, COMPOUND_ID, PARENT_ID]),
            (["session", "list", "--json", "--parent-only"], [COMPOUND_ID, PARENT_ID]),
            (["session", "current", "--json", "--parent-only"], [COMPOUND_ID, PARENT_ID]),
        )
        for arguments, expected_ids in cases:
            with self.subTest(arguments=arguments):
                baseline, modex = compare_outputs(
                    arguments,
                    install_fixture,
                    reference=ORACLE,
                )
                self.assertEqual(modex, baseline)
                self.assertEqual([report["id"] for report in baseline], expected_ids)
                child = next((report for report in baseline if report["id"] == CHILD_ID), None)
                if child:
                    self.assertEqual(child["parent_thread_id"], PARENT_ID)
                    self.assertTrue(child["path"].endswith(f"/rollout-{CHILD_ID}.jsonl.zst"))
                parent = next(report for report in baseline if report["id"] == PARENT_ID)
                self.assertIn("/archived_sessions/", parent["path"])
                self.assertTrue(parent["path"].endswith(f"/rollout-{PARENT_ID}.jsonl.zst"))
                compound = next((report for report in baseline if report["id"] == COMPOUND_ID), None)
                if compound:
                    self.assertTrue(compound["path"].endswith("/rollout-compound.jsonl.zst.json"))

    def test_compressed_session_ids_feed_resume_command_output(self):
        baseline, modex = compare_outputs(
            ["session", "list", "--resume-command"],
            install_fixture,
            reference=ORACLE,
        )
        self.assertEqual(modex, baseline)
        self.assertEqual(
            baseline,
            (f"prodex run {CHILD_ID}\nprodex run {COMPOUND_ID}\nprodex run {PARENT_ID}\n").encode(),
        )

    def test_wrong_type_metadata_values_fall_through_to_string_fields(self):
        baseline, modex = compare_outputs(
            ["session", "list", "--json"],
            install_typed_metadata_conflict,
            reference=ORACLE,
        )
        self.assertEqual(modex, baseline)
        self.assertEqual(len(baseline), 1)
        self.assertEqual(baseline[0]["id"], "metadata-fallback")
        self.assertEqual(baseline[0]["thread_name"], "Fallback thread")
        self.assertEqual(baseline[0]["cwd"], "<FIXTURE_ROOT>/workspace")
        self.assertEqual(baseline[0]["model_provider"], "fallback-provider")
        self.assertEqual(baseline[0]["parent_thread_id"], "fallback-parent")

        baseline, modex = compare_outputs(
            ["session", "current", "--json"],
            install_typed_metadata_conflict,
            reference=ORACLE,
        )
        self.assertEqual(modex, baseline)
        self.assertEqual([report["id"] for report in baseline], ["metadata-fallback"])

        baseline, modex = compare_outputs(
            ["session", "list", "--json", "--parent-only"],
            install_typed_metadata_conflict,
            reference=ORACLE,
        )
        self.assertEqual(modex, baseline)
        self.assertEqual(baseline, [])

    def test_compressed_path_queries_and_current_projection(self):
        for arguments in (
            ["session", "list", "--json", "--query", f"rollout-{CHILD_ID}.jsonl.zst"],
            ["session", "current", "--json", "--query", f"rollout-{CHILD_ID}.jsonl.zst"],
        ):
            with self.subTest(arguments=arguments):
                baseline, modex = compare_outputs(arguments, install_fixture, reference=ORACLE)
                self.assertEqual(modex, baseline)
                self.assertEqual([report["id"] for report in baseline], [CHILD_ID])

    def test_duplicate_ids_keep_path_order_for_equal_timestamps(self):
        baseline, modex = compare_outputs(
            ["session", "list", "--json"],
            install_tied_duplicate_ids,
            reference=ORACLE,
        )
        self.assertEqual(modex, baseline)
        self.assertEqual(
            [(report["id"], report["thread_name"], report["path"].rsplit("/", 1)[-1]) for report in baseline],
            [("duplicate-id", "First path", "a.jsonl"), ("duplicate-id", "Second path", "z.json")],
        )

    def test_compressed_checksum_matches_at_8k_read_boundary(self):
        checksum_error = (
            "Error: failed to read session <FIXTURE_ROOT>/home/.codex/sessions/2026/10/24/"
            f"rollout-{SESSION_ID}.jsonl.zst: Restored data doesn't match checksum\n"
        )
        cases = (
            ("invalid-first-line-8191-checksum", {
                "exit_code": 1, "stdout": "", "stderr": checksum_error,
            }),
            ("invalid-first-line-8192-checksum", {
                "exit_code": 1, "stdout": "", "stderr": checksum_error,
            }),
            ("invalid-first-line-8193-checksum", {
                "exit_code": 0, "stdout": "[]\n", "stderr": "",
            }),
        )
        with tempfile.TemporaryDirectory(prefix="modex-01662-zstd-boundary-") as directory:
            parent = Path(directory)
            for case, expected in cases:
                observations = {}
                for name, binary in (("prodex01662", ORACLE), ("modex", MODEX)):
                    root = parent / f"{case}-{name}"
                    root.mkdir()
                    fixture(root)
                    install_case(root, case)
                    observations[name] = observe(binary, root)
                with self.subTest(case=case):
                    self.assertEqual(observations["prodex01662"], expected)
                    self.assertEqual(observations["modex"], observations["prodex01662"])


if __name__ == "__main__":
    unittest.main()
