"""Budget, tied-mtime ordering, and discovery checks for log stream paths."""

import os
from pathlib import Path
import tempfile
import time
import unittest

from test_cli import MODEX, ORACLE
from test_log_stream import StreamProcess, runtime_record, run_trace, session_record


def selected_path_fixture(follower):
    # Identical future mtimes exercise path byte ordering without sleeps.
    mtime_ns = time.time_ns() + 60_000_000_000
    follower.fixture_mtime_ns = mtime_ns
    follower.selected_runtime = []
    follower.selected_sessions = []
    for index in range(40):
        runtime = follower.runtime / f"prodex-runtime-{index:02d}.log"
        runtime.write_bytes(runtime_record("stream_payload", {
            "source": "synthetic-stream", "stream": f"runtime-{index:02d}-initial",
        }, f"2026-10-24T01:00:{index:02d}Z"))
        os.utime(runtime, ns=(mtime_ns, mtime_ns))
        follower.selected_runtime.append(runtime)

        session = follower.session.parent / f"rollout-{index:02d}.jsonl"
        session.write_bytes(session_record(f"2026-10-24T01:00:{index:02d}Z",
                                           f"session-{index:02d}-initial"))
        os.utime(session, ns=(mtime_ns, mtime_ns))
        follower.selected_sessions.append(session)



def followed_path_snapshot(process, root):
    parents = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
            fields = stat[stat.rfind(")") + 2 :].split()
            parents[int(entry.name)] = int(fields[1])
        except (OSError, ValueError, IndexError):
            continue
    pids = {process.pid}
    while True:
        children = {pid for pid, parent in parents.items() if parent in pids}
        if children <= pids:
            break
        pids.update(children)

    selected_runtime = set()
    selected_sessions = set()
    for pid in pids:
        try:
            descriptors = (Path("/proc") / str(pid) / "fd").iterdir()
            for descriptor in descriptors:
                try:
                    target = os.readlink(descriptor)
                    if target.endswith(" (deleted)"):
                        target = target[:-10]
                    relative = Path(target).relative_to(root)
                except (OSError, ValueError):
                    continue
                if not relative.parts:
                    continue
                if relative.parts[0] == "runtime" and target.endswith(".log"):
                    selected_runtime.add(str(relative))
                elif relative.parts[:5] == ("home", ".codex", "sessions", "2026", "10") and target.endswith(".jsonl"):
                    selected_sessions.add(str(relative))
        except OSError:
            continue
    return selected_runtime, selected_sessions

def run_capped_trace(binary, mode, scenario, *, prepare):
    with tempfile.TemporaryDirectory(prefix="modex-log-stream-budget-") as directory:
        follower = StreamProcess(
            binary, mode, Path(directory), b"", b"invalid runtime line\n",
            prepare=prepare, nofile=48,
        )
        try:
            scenario(follower)
            if follower.process.poll() is not None:
                raise AssertionError(f"log stream exited: {follower.process.returncode}")
            return follower.stop()
        finally:
            follower.stop()


class LogStreamPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_cli
        test_cli.CliTests.setUpClass()

    def test_combined_budget_ties_and_follow_survival_under_descriptor_limit(self):
        if not Path("/proc/self/fd").is_dir():
            self.skipTest("Linux /proc is required for followed descriptor snapshots")
        snapshots = []

        def scenario(follower):
            follower.require_markers(("session-00-initial", "runtime-39-initial"), timeout=8)
            follower.require_quiet(0.3)
            if follower.process.poll() is not None:
                raise AssertionError("log stream exited with 32 combined files under RLIMIT_NOFILE=48")
            runtime, sessions = followed_path_snapshot(follower.process, follower.root)
            snapshots.append((runtime, sessions))
            if (len(runtime), len(sessions)) != (16, 16):
                raise AssertionError(f"expected 16 followed paths per source, got {len(runtime)} and {len(sessions)}")
            if len(snapshots) > 1 and snapshots[-1] != snapshots[0]:
                raise AssertionError("Modex followed descriptor paths differ from the frozen oracle")

            # Append to one proven selected path per source and preserve its mtime during the follow check.
            runtime_path = follower.root / sorted(runtime)[0]
            session_path = follower.root / sorted(sessions)[0]
            runtime_mtime = runtime_path.stat().st_mtime_ns
            session_mtime = session_path.stat().st_mtime_ns
            with runtime_path.open("ab") as stream:
                stream.write(runtime_record("stream_payload", {
                    "source": "synthetic-stream", "stream": "selected-runtime-follow-marker",
                }, "2026-10-24T01:01:00Z"))
            with session_path.open("ab") as stream:
                stream.write(session_record("2026-10-24T01:01:01Z", "selected-session-follow-marker"))
            os.utime(runtime_path, ns=(runtime_mtime, runtime_mtime))
            os.utime(session_path, ns=(session_mtime, session_mtime))
            follower.require_markers(("selected-runtime-follow-marker", "selected-session-follow-marker"), timeout=8)

            # A path outside the observed descriptor set must stay pruned after reconciliation.
            pruned_runtime = follower.runtime / "prodex-runtime-39.log"
            pruned_session = follower.session.parent / "rollout-39.jsonl"
            self.assertNotIn(str(pruned_runtime.relative_to(follower.root)), runtime)
            self.assertNotIn(str(pruned_session.relative_to(follower.root)), sessions)
            for path, data in (
                (pruned_runtime, runtime_record("stream_payload", {
                    "source": "synthetic-stream", "stream": "pruned-runtime-marker",
                }, "2026-10-24T01:02:00Z")),
                (pruned_session, session_record("2026-10-24T01:02:01Z", "pruned-session-marker")),
            ):
                old_mtime = path.stat().st_mtime_ns
                with path.open("ab") as stream:
                    stream.write(data)
                os.utime(path, ns=(old_mtime, old_mtime))
            follower.require_quiet(2.4)
            if follower.process.poll() is not None:
                raise AssertionError("log stream exited after pruning under descriptor limit")
            output = bytes(follower.output["stdout"] + follower.output["stderr"])
            if b"pruned-runtime-marker" in output or b"pruned-session-marker" in output:
                raise AssertionError("a pruned path emitted a followed event")

        expected = run_capped_trace(ORACLE, "json", scenario, prepare=selected_path_fixture)
        actual = run_capped_trace(MODEX, "json", scenario, prepare=selected_path_fixture)
        self.assertEqual(snapshots[0], snapshots[1])
        self.assertEqual(actual, expected)

    def test_runtime_two_second_and_session_ten_second_path_discovery(self):
        def prepare(follower):
            follower.runtime_new = follower.runtime / "prodex-runtime-discovered.log"
            follower.session_new = follower.session.parent / "rollout-discovered.jsonl"

        def scenario(follower):
            follower.require_marker("Waiting for transcript, upstream payload, or token events.", timeout=8)
            follower.require_quiet(0.3)
            follower.runtime_new.write_bytes(b"")
            follower.require_quiet(2.4)
            with follower.runtime_new.open("ab") as stream:
                stream.write(runtime_record("stream_payload", {
                    "source": "synthetic-stream", "stream": "new-runtime-path-marker",
                }, "2026-10-24T01:03:00Z"))
            follower.require_marker("new-runtime-path-marker", timeout=8)

            follower.session_new.write_bytes(b"")
            follower.require_quiet(10.4)
            with follower.session_new.open("ab") as stream:
                stream.write(session_record("2026-10-24T01:04:00Z", "new-session-path-marker"))
            follower.require_marker("new-session-path-marker", timeout=8)
            if follower.process.poll() is not None:
                raise AssertionError("log stream exited during path reconciliation")

        # The Modex and oracle traces share deadlines and handshakes; oracle controls observed timing.
        expected = run_trace(ORACLE, "json", b"", b"invalid runtime line\n", scenario,
                             prepare=prepare, nofile=48)
        actual = run_trace(MODEX, "json", b"", b"invalid runtime line\n", scenario,
                           prepare=prepare, nofile=48)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
