"""Output-focused differential checks; full side-effect parity is tracked separately."""

import json
import os
from datetime import datetime, timezone as datetime_timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import subprocess
import tempfile
import unittest

from session_oracle import SESSION_ID, fixture, sandbox_command
import test_cli
from test_cli import MODEX, ORACLE


def normalize_output(data, root, arguments, *, modex=False):
    if "--json" in arguments:
        reports = json.loads(data)
        for report in reports:
            for field in ("cwd", "path"):
                value = report.get(field)
                if value and value.startswith(str(root) + "/"):
                    report[field] = "<FIXTURE_ROOT>" + value[len(str(root)):]
        # Only fixture-root paths change; field order, whitespace and Unicode stay checked.
        original = json.loads(data)
        expected_raw = json.dumps(original, ensure_ascii=False, indent=2) + "\n"
        if data.decode() != expected_raw:
            raise AssertionError("JSON output does not match baseline pretty serialization")
        return reports
    if "--resume-command" in arguments and modex:
        return b"\n".join(b"prodex run " + line[len(b"modex run "):]
                           if line.startswith(b"modex run ") else line
                           for line in data.split(b"\n"))
    return data


def compare_outputs(arguments, change=None, *, timezone="UTC", timezone_data=None, reference=ORACLE):
    with tempfile.TemporaryDirectory(prefix="modex-session-pair-") as directory:
        parent = Path(directory)
        observations = []
        for name, binary in (("baseline", reference), ("modex", MODEX)):
            root = parent / name
            root.mkdir()
            fixture(root)
            if change:
                change(root)
            zone_name = timezone
            if timezone_data is not None:
                zone_file = root / "fixture.tzif"
                zone_file.write_bytes(timezone_data)
                zone_name = ":" + str(zone_file)
            result = subprocess.run(sandbox_command(binary, root, arguments, timezone=zone_name),
                                    capture_output=True, timeout=10, check=False)
            if result.returncode != 0:
                raise AssertionError(f"{name} exited {result.returncode}: {result.stderr!r}")
            if result.stderr:
                raise AssertionError(f"{name} wrote unexpected stderr: {result.stderr!r}")
            observations.append(normalize_output(result.stdout, root, arguments, modex=name == "modex"))
        return observations


class SessionOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def assert_outputs(self, arguments, change=None, *, timezone="UTC"):
        baseline, modex = compare_outputs(arguments, change, timezone=timezone)
        self.assertEqual(modex, baseline)
        return baseline

    def test_populated_json(self):
        reports = self.assert_outputs(["session", "list", "--json"])
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["id"], SESSION_ID)

    def test_filters_limits_and_machine_output_modes(self):
        for arguments in (
            ["session", "list", "--json", "--limit", "0"],
            ["session", "list", "--json", "--limit", "18446744073709551615"],
            ["session", "list", "--json", "--profile", "missing"],
            ["session", "list", "--json", "--query", "SESSION FIXTURE"],
            ["session", "list", "--json", "--query", "absent phrase"],
            ["session", "current", "--json"],
            ["session", "current", "--json", "--cwd", "/elsewhere"],
            ["session", "list", "--id-only"],
            ["session", "list", "--resume-command"],
            ["session", "list", "--json", "--include-subagents"],
            ["session", "list", "--json", "--parent-only"],
        ):
            with self.subTest(arguments=arguments):
                self.assert_outputs(arguments)

    def test_json_file_and_metadata_precedence(self):
        def change(root):
            session = next((root / "home/.codex").rglob("*.jsonl"))
            metadata = json.loads(session.read_text().splitlines()[0])
            metadata["payload"]["title"] = "Wrong title"
            metadata["thread_name"] = "Wrong root name"
            metadata["payload"]["thread_name"] = "Résumé CHECK"
            metadata["payload"]["metadata"] = {"cwd": "/wrong-directory"}
            session.unlink()
            session.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        reports = self.assert_outputs(["session", "list", "--json", "--query", "résumé"], change)
        self.assertEqual(reports[0]["thread_name"], "Résumé CHECK")

    def test_archived_children_and_newest_first_ordering(self):
        def change(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            metadata = json.loads(original.read_text().splitlines()[0])
            metadata["payload"]["id"] = "child-session"
            metadata["payload"]["source"] = {"subagent": {"thread_spawn": {"parent_thread_id": SESSION_ID}}}
            metadata["timestamp"] = "2026-10-24T03:00:00+01:00"
            archived = root / "home/.codex/archived_sessions"
            archived.mkdir()
            (archived / "child.jsonl").write_text(json.dumps(metadata) + "\n")
        reports = self.assert_outputs(["session", "list", "--json"], change)
        self.assertEqual([report["id"] for report in reports], ["child-session", SESSION_ID])
        self.assert_outputs(["session", "list", "--json", "--parent-only"], change)

    def test_malformed_records_and_symlinks(self):
        def change(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            original.write_text("\n\n" + original.read_text() + "{bad json}\n")
            (original.parent / "invalid.jsonl").write_text("{bad json}\n" + original.read_text())
            (original.parent / "link.jsonl").symlink_to(original)
        self.assert_outputs(["session", "list", "--json"], change)

    def test_unicode_whitespace_and_blank_string_fallbacks(self):
        def change(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            metadata = json.loads(original.read_text().splitlines()[0])
            metadata["payload"]["thread_name"] = "\u2000\u00a0"
            metadata["payload"]["title"] = "\u2000Trimmed title\u00a0"
            original.write_text(json.dumps(metadata) + "\n")
        reports = self.assert_outputs(["session", "list", "--json"], change)
        self.assertEqual(reports[0]["thread_name"], "Trimmed title")

    def test_unicode_prefix_on_first_metadata_record_is_not_accepted(self):
        def change(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            original.write_text("\u2000" + original.read_text())
        self.assertEqual(self.assert_outputs(["session", "list", "--json"], change), [])

    def test_nonobject_followup_records_do_not_crash_modex(self):
        # Safe behavior differs from a baseline panic; this is not a parity PASS.
        with tempfile.TemporaryDirectory(prefix="modex-session-scalar-") as directory:
            root = Path(directory)
            fixture(root)
            original = next((root / "home/.codex").rglob("*.jsonl"))
            original.write_text(original.read_text() + "[]\nnull\n")
            result = subprocess.run(sandbox_command(MODEX, root, ["session", "list", "--json"]),
                                    capture_output=True, timeout=10, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)[0]["id"], SESSION_ID)

    def test_signed_date_components_use_file_time_for_ordering(self):
        timestamps = (
            "+026-01-01T00:00:00Z", "2026-+1-01T00:00:00Z",
            "2026-01-+1T00:00:00Z", "2026-01-01T+1:00:00Z",
            "2026-01-01T00:+1:00Z", "2026-01-01T00:00:+1Z",
            "2026-01-01T00:00:00++1:00", "2026-01-01T00:00:00+00:+1",
        )
        def change(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            original.unlink()
            for index, timestamp in enumerate(timestamps):
                path = original.parent / f"signed-{index}.jsonl"
                path.write_text(json.dumps({"type": "session_meta", "timestamp": timestamp,
                                            "payload": {"id": f"signed-{index}"}}) + "\n")
                os.utime(path, (1577836800, 1577836800))
            path = original.parent / "valid.jsonl"
            path.write_text(json.dumps({"type": "session_meta", "timestamp": "2026-01-01T00:00:00Z",
                                        "payload": {"id": "valid"}}) + "\n")
            os.utime(path, (1577836800, 1577836800))
        reports = self.assert_outputs(["session", "list", "--json"], change)
        self.assertEqual([report["id"] for report in reports],
                         ["valid", *(f"signed-{index}" for index in range(len(timestamps)))])

    def test_numeric_timestamps_and_fallback_file_times(self):
        for epoch in (0, -1, 951782400, 1792800000, 253402300800,
                      -8334601228800, 8210266876799, -9223372036854775808, 9223372036854775807):
            def change(root):
                original = next((root / "home/.codex").rglob("*.jsonl"))
                original.write_text(original.read_text() + json.dumps({"type": "event_msg", "updated_at": epoch}) + "\n")
            with self.subTest(epoch=epoch):
                self.assert_outputs(["session", "list", "--json"], change)
        def fallback(root):
            original = next((root / "home/.codex").rglob("*.jsonl"))
            metadata = json.loads(original.read_text().splitlines()[0])
            metadata["timestamp"] = ""
            metadata["payload"]["timestamp"] = ""
            original.write_text(json.dumps(metadata) + "\n")
            os.utime(original, (1792800000, 1792800000))
        self.assert_outputs(["session", "list", "--json"], fallback)

    def test_numeric_timezones_and_daylight_transitions(self):
        for timezone in ("Asia/Jakarta", "America/New_York", "Europe/London", "UTC0", "GMT0"):
            for epoch in (1767225600, 1782864000, 1792800000):
                def change(root):
                    original = next((root / "home/.codex").rglob("*.jsonl"))
                    original.write_text(original.read_text() + json.dumps({"updated_at": epoch}) + "\n")
                with self.subTest(timezone=timezone, epoch=epoch):
                    self.assert_outputs(["session", "list", "--json"], change, timezone=timezone)

    def test_future_recurring_timezone_rules(self):
        for timezone in ("America/New_York", "Europe/London", "Australia/Sydney",
                         "Australia/Lord_Howe", "Pacific/Chatham", "Africa/Casablanca"):
            for date in ((2050, 1, 1), (2050, 7, 1), (2100, 1, 1), (2100, 7, 1)):
                epoch = int(datetime(*date, tzinfo=datetime_timezone.utc).timestamp())
                def change(root):
                    original = next((root / "home/.codex").rglob("*.jsonl"))
                    original.write_text(original.read_text() + json.dumps({"updated_at": epoch}) + "\n")
                with self.subTest(timezone=timezone, date=date):
                    self.assert_outputs(["session", "list", "--json"], change, timezone=timezone)

    def test_posix_timezone_strings(self):
        for timezone in ("EST5", "<-0430>4:30", "IST-5:30", "NPT-5:45",
                         "EST5EDT,M3.2.0,M11.1.0", "EST5EDT",
                         "AEST-10AEDT,M10.1.0,M4.1.0/3", "XST0XDT,J60/0,J300/0",
                         "XST0XDT,59/0,300/0", "XST0XDT,M3.5.0/-2,M10.5.0/26",
                         "EST5EDT,0/0,J365/25", "XXX3EDT4,0/0,J365/23",
                         "XST5XDT", "invalid/zone", "UTC25", ":IST-5:30"):
            for date in ((2024, 2, 29), (2024, 3, 1), (2050, 1, 1), (2050, 7, 1)):
                epoch = int(datetime(*date, tzinfo=datetime_timezone.utc).timestamp())
                def change(root):
                    original = next((root / "home/.codex").rglob("*.jsonl"))
                    original.write_text(original.read_text() + json.dumps({"updated_at": epoch}) + "\n")
                with self.subTest(timezone=timezone, date=date):
                    self.assert_outputs(["session", "list", "--json"], change, timezone=timezone)

    def test_future_timezone_transition_seconds(self):
        first = int(datetime(2050, 1, 1, tzinfo=datetime_timezone.utc).timestamp())
        for timezone in ("America/New_York", "Europe/London", "Australia/Sydney",
                         "Australia/Lord_Howe", "Pacific/Chatham", "Europe/Dublin"):
            zone = ZoneInfo(timezone)
            previous = datetime.fromtimestamp(first, zone).utcoffset()
            changes = []
            for day in range(1, 366):
                current = first + day * 86400
                offset = datetime.fromtimestamp(current, zone).utcoffset()
                if offset != previous:
                    low, high = current - 86400, current
                    while high - low > 1:
                        middle = (low + high) // 2
                        if datetime.fromtimestamp(middle, zone).utcoffset() == previous:
                            low = middle
                        else:
                            high = middle
                    changes.extend((high - 1, high))
                previous = offset
            self.assertEqual(len(changes), 4, timezone)
            for epoch in changes:
                def change(root):
                    original = next((root / "home/.codex").rglob("*.jsonl"))
                    original.write_text(original.read_text() + json.dumps({"updated_at": epoch}) + "\n")
                with self.subTest(timezone=timezone, epoch=epoch):
                    self.assert_outputs(["session", "list", "--json"], change, timezone=timezone)


if __name__ == "__main__":
    unittest.main()
