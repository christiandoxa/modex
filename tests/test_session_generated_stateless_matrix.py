"""Generated session-report comparisons against both pinned Prodex releases."""

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
ORACLE_01651_SHA256 = "dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51"
TARGETS = (
    ("prodex-01651", ORACLE_01651, "prodex"),
    ("prodex-04392", test_cli.ORACLE, "prodex"),
    ("modex", test_cli.MODEX, "modex"),
)


def make_root(root):
    (root / "home").mkdir(mode=0o700)
    (root / "workspace").mkdir()
    sessions = root / "home/.codex/sessions/2026/10/24"
    sessions.mkdir(parents=True)
    return sessions


def write_jsonl(sessions, filename, records, *, mtime=1_600_000_000):
    path = sessions / filename
    lines = [record if isinstance(record, str) else json.dumps(record, ensure_ascii=False)
             for record in records]
    path.write_text("\n".join(lines) + "\n")
    os.utime(path, (mtime, mtime))
    return path


def metadata_alias_fixtures(root):
    sessions = make_root(root)
    write_jsonl(sessions, "rollout-alias-fixture.jsonl", [{
        "type": "session_meta",
        "payload": {
            "id": "alias-report-id",
            "thread_name": " \t ",
            "title": "payload-title",
            "metadata": {
                "thread_name": "nested-payload-title",
                "cwd": "/synthetic/payload-metadata-cwd",
                "model_provider": "nested-payload-provider",
            },
            "cwd": " \t ",
            "workdir": "/synthetic/payload-workdir",
            "parent_thread_id": "payload-parent",
            "source": {"subagent": {"thread_spawn": {
                "parent_thread_id": "nested-parent",
            }}},
            "model_provider": "payload-provider",
        },
        "thread_name": "root-thread-name",
        "cwd": "/synthetic/root-cwd",
        "updated_at": "2026-10-24T03:30:00+00:00",
        "timestamp": "2026-10-24T01:30:00Z",
        "parent_thread_id": "root-parent",
        "model_provider": "root-provider",
    }])


def duplicate_key_fixtures(root):
    sessions = make_root(root)
    duplicate = (
        '{"type":"event_msg","type":"session_meta",'
        '"payload":{"id":"nested-first-id","id":"nested-last-id",'
        '"thread_name":"nested-first-title","thread_name":"nested-last-title"},'
        '"payload":{"id":"payload-first-id","id":"payload-last-id",'
        '"thread_name":"payload-first-title","thread_name":"payload-last-title",'
        '"cwd":"/synthetic/duplicate-cwd"},'
        '"updated_at":"2026-10-22T00:00:00Z",'
        '"updated_at":"2026-10-23T00:00:00Z",'
        '"model_provider":"first-provider",'
        '"model_provider":"last-provider"}'
    )
    write_jsonl(sessions, "rollout-duplicate-fixture.jsonl", [duplicate])
    duplicate_metadata = (
        '{"type":"session_meta","payload":{"id":"duplicate-root-metadata"},'
        '"metadata":{"thread_name":"root-metadata-first",'
        '"model_provider":"root-provider-first"},'
        '"metadata":{"thread_name":"root-metadata-last",'
        '"model_provider":"root-provider-last"}}'
    )
    write_jsonl(sessions, "rollout-duplicate-metadata.jsonl", [duplicate_metadata])


def record_order_fixtures(root):
    sessions = make_root(root)
    write_jsonl(sessions, "rollout-record-order.jsonl", [
        {"type": "session_meta", "payload": {
            "id": "record-seed-id", "thread_name": "seed-title",
            "cwd": "/synthetic/seed-cwd", "model_provider": "seed-provider",
            "timestamp": "2026-10-24T00:00:00Z",
        }},
        {"type": "turn_context", "payload": {
            "id": "ignored-turn-id", "thread_name": "turn-title",
            "cwd": "/synthetic/turn-cwd", "model_provider": "turn-provider",
            "timestamp": "2026-10-24T01:00:00Z",
            "parent_thread_id": "turn-parent",
        }},
        {"type": "event_msg", "payload": {
            "id": "ignored-event-id", "thread_name": "event-title",
            "model_provider": "event-provider",
            "timestamp": "2026-10-24T02:00:00Z",
            "parent_thread_id": "event-parent",
        }},
        {"type": 42, "payload": {
            "id": "non-string-type-id", "thread_name": "number-type-title",
        }},
    ])
    write_jsonl(sessions, "rollout-no-type.jsonl", [{
        "payload": {"id": "missing-type-id", "thread_name": "missing-type-title"},
        "timestamp": "2026-10-24T02:00:00Z",
    }])
    for filename, record_type, seeded_id, attempted_id in (
        ("rollout-turn-context-guard.jsonl", "turn_context", "turn-seed-id", "turn-overwrite-id"),
        ("rollout-event-guard.jsonl", "event_msg", "event-seed-id", "event-overwrite-id"),
        ("rollout-empty-type-guard.jsonl", "", "empty-type-seed-id", "empty-type-overwrite-id"),
    ):
        write_jsonl(sessions, filename, [
            {"type": "session_meta", "payload": {"id": seeded_id, "thread_name": "seed-title"}},
            {"type": record_type, "payload": {
                "id": attempted_id, "thread_name": f"{record_type or 'empty'}-title",
            }},
        ])
    for filename, identifier, title in (
        ("rollout-same-z.jsonl", "same-id", "same-z"),
        ("rollout-same-a.jsonl", "same-id", "same-a"),
        ("rollout-id-a.jsonl", "a-id", "id-a"),
    ):
        write_jsonl(sessions, filename, [{
            "type": "session_meta", "payload": {"id": identifier, "thread_name": title},
            "timestamp": "2026-10-24T04:00:00Z",
        }])


def timestamp_fixtures(root):
    sessions = make_root(root)
    records = (
        ("rollout-time-zulu.jsonl", "zulu-id", {"updated_at": "2026-10-24T03:30:00Z"}, 5),
        ("rollout-time-offset.jsonl", "offset-id", {"updated_at": "2026-10-24T06:00:00+02:30"}, 6),
        ("rollout-time-number.jsonl", "number-id", {"updated_at": 1_700_000_000}, 7),
        ("rollout-time-ts.jsonl", "ts-id", {"ts": 1_700_000_001}, 8),
        ("rollout-time-invalid.jsonl", "invalid-id", {
            "updated_at": "not-a-timestamp", "ts": 1_700_000_002,
        }, 9),
        ("rollout-time-negative.jsonl", "negative-id", {"timestamp": "1969-12-31T23:59:59Z"}, 10),
        ("rollout-time-mtime.jsonl", "mtime-id", {}, 1_700_000_003),
    )
    for filename, identifier, fields, mtime in records:
        write_jsonl(sessions, filename, [{
            "type": "session_meta", "payload": {"id": identifier}, **fields,
        }], mtime=mtime)


def query_fixtures(root):
    sessions = make_root(root)
    record = {
        "type": "session_meta",
        "payload": {
            "id": "query-id-needle",
            "thread_name": "query-title-needle",
            "cwd": str(root / "workspace/query-cwd-needle"),
            "model_provider": "query-provider-needle",
            "parent_thread_id": "query-parent-excluded",
        },
        "timestamp": "2030-01-02T03:04:05Z",
    }
    write_jsonl(sessions, "rollout-query-path-needle.jsonl", [record])


def run_cli(binary, root, argv0, arguments):
    result = subprocess.run(
        sandbox_command(binary, root, arguments, timezone="UTC", argv0=argv0),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=10,
        check=False,
    )
    fixture_root = str(root).encode()
    return (
        result.returncode,
        result.stdout.replace(fixture_root, b"<FIXTURE_ROOT>"),
        result.stderr.replace(fixture_root, b"<FIXTURE_ROOT>"),
    )


class GeneratedSessionStatelessMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()
        if (not ORACLE_01651.is_file()
                or hashlib.sha256(ORACLE_01651.read_bytes()).hexdigest() != ORACLE_01651_SHA256):
            raise AssertionError("Prodex oracle does not match frozen release 0.165.1")

    def observe(self, fixture_builder, arguments):
        observed = {}
        with tempfile.TemporaryDirectory(prefix="modex-session-generated-matrix-") as directory:
            base = Path(directory)
            for label, binary, argv0 in TARGETS:
                root = base / label
                root.mkdir()
                fixture_builder(root)
                observed[label] = run_cli(binary, root, argv0, arguments)
        return observed

    def assert_release_parity(self, observed):
        for label, result in observed.items():
            with self.subTest(target=label):
                self.assertEqual(result[0], 0, result[2].decode(errors="replace"))
                self.assertEqual(result[2], b"")
        self.assertEqual(observed["prodex-01651"], observed["prodex-04392"])
        self.assertEqual(observed["prodex-04392"], observed["modex"])

    def test_metadata_alias_precedence(self):
        observed = self.observe(metadata_alias_fixtures, ["session", "list", "--json"])
        self.assert_release_parity(observed)
        reports = json.loads(observed["prodex-04392"][1])
        self.assertEqual(len(reports), 1)
        report = reports[0]
        self.assertEqual(report["id"], "alias-report-id")
        self.assertEqual(report["thread_name"], "payload-title")
        self.assertEqual(report["cwd"], "/synthetic/payload-metadata-cwd")
        self.assertEqual(report["updated_at"], "2026-10-24T03:30:00+00:00")
        self.assertEqual(report["model_provider"], "payload-provider")
        self.assertEqual(report["parent_thread_id"], "nested-parent")

    def test_duplicate_json_keys(self):
        observed = self.observe(duplicate_key_fixtures, ["session", "list", "--json"])
        self.assert_release_parity(observed)
        reports = json.loads(observed["prodex-04392"][1])
        by_id = {report["id"]: report for report in reports}
        self.assertEqual(len(reports), 2)
        report = by_id["payload-last-id"]
        self.assertEqual(report["id"], "payload-last-id")
        self.assertEqual(report["thread_name"], "payload-last-title")
        self.assertEqual(report["updated_at"], "2026-10-23T00:00:00Z")
        self.assertEqual(report["model_provider"], "last-provider")
        self.assertEqual(by_id["duplicate-root-metadata"]["thread_name"], "root-metadata-last")
        self.assertEqual(by_id["duplicate-root-metadata"]["model_provider"], "root-provider-last")

    def test_record_order_types_and_sort_ties(self):
        observed = self.observe(record_order_fixtures, ["session", "list", "--json"])
        self.assert_release_parity(observed)
        reports = json.loads(observed["prodex-04392"][1])
        by_id = {report["id"]: report for report in reports}
        self.assertEqual(by_id["non-string-type-id"]["thread_name"], "number-type-title")
        self.assertEqual(by_id["non-string-type-id"]["cwd"], "/synthetic/turn-cwd")
        self.assertEqual(by_id["non-string-type-id"]["model_provider"], "event-provider")
        self.assertEqual(by_id["non-string-type-id"]["parent_thread_id"], "event-parent")
        self.assertEqual(by_id["missing-type-id"]["thread_name"], "missing-type-title")
        self.assertEqual(by_id["turn-seed-id"]["thread_name"], "turn_context-title")
        self.assertEqual(by_id["event-seed-id"]["thread_name"], "event_msg-title")
        self.assertEqual(by_id["empty-type-seed-id"]["thread_name"], "empty-title")
        self.assertEqual([report["thread_name"] for report in reports[:3]], ["id-a", "same-a", "same-z"])

    def test_timestamp_aliases_and_sorting(self):
        observed = self.observe(timestamp_fixtures, ["session", "list", "--json"])
        self.assert_release_parity(observed)
        reports = json.loads(observed["prodex-04392"][1])
        by_id = {report["id"]: report for report in reports}
        self.assertEqual(by_id["zulu-id"]["updated_at"], "2026-10-24T03:30:00Z")
        self.assertEqual(by_id["offset-id"]["updated_at"], "2026-10-24T06:00:00+02:30")
        self.assertEqual(by_id["invalid-id"]["updated_at"], "not-a-timestamp")
        self.assertEqual(by_id["number-id"]["updated_at"], "2023-11-14 22:13:20 +00:00")
        self.assertEqual(by_id["ts-id"]["updated_at"], "2023-11-14 22:13:21 +00:00")
        self.assertEqual(by_id["mtime-id"]["updated_at"], "2023-11-14 22:13:23 +00:00")
        self.assertEqual([report["id"] for report in reports], [
            "offset-id", "zulu-id", "mtime-id", "ts-id", "number-id", "invalid-id", "negative-id",
        ])
        self.assertEqual([report["id"] for report in reports[:2]], ["offset-id", "zulu-id"])

    def test_query_fields_use_only_stateless_report_metadata(self):
        queries = (
            ("query-id-needle", True),
            ("QUERY-TITLE-NEEDLE", True),
            ("query-cwd-needle", True),
            ("query-provider-needle", True),
            ("query-path-needle", True),
            ("  query-title-needle  ", True),
            ("query-parent-excluded", False),
            ("2030-01-02", False),
        )
        with tempfile.TemporaryDirectory(prefix="modex-session-generated-query-") as directory:
            base = Path(directory)
            roots = {}
            for label, binary, argv0 in TARGETS:
                root = base / label
                root.mkdir()
                query_fixtures(root)
                roots[label] = (binary, argv0, root)
            for query, expected_match in queries:
                by_target = {}
                for label, (binary, argv0, root) in roots.items():
                    by_target[label] = run_cli(
                        binary, root, argv0,
                        ["session", "list", "--query", query, "--id-only"],
                    )
                self.assert_release_parity(by_target)
                expected = b"query-id-needle\n" if expected_match else b""
                self.assertEqual(by_target["prodex-04392"][1], expected)


if __name__ == "__main__":
    unittest.main()
