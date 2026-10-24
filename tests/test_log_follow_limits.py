"""Black-box coverage for detached runtime log follower limits."""

import os
import resource
import subprocess
import unittest

from session_oracle import sandbox_command
from test_cli import MODEX, ORACLE
from test_log_upstream_follow import UpstreamProcess, upstream_record


def run_limited_trace(binary, mode, scenario):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory(prefix="modex-upstream-fd-limit-") as directory:
        root = Path(directory)
        (root / "home").mkdir(mode=0o700)
        (root / "workspace").mkdir()
        (root / ".prodex").mkdir(mode=0o700)
        runtime = root / "runtime"
        runtime.mkdir()
        log = runtime / "prodex-runtime-primary.log"
        log.write_bytes(b"not an upstream event\n")
        args = ["log", "upstream"] + ([] if mode == "plain" else ["--json"])
        command = sandbox_command(
            binary, root, args, argv0="prodex" if binary == ORACLE else "modex",
            environment={"TZ": "UTC", "PRODEX_RUNTIME_LOG_DIR": str(runtime)},
        )
        def limit_descriptors():
            resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))

        # Apply the same cap to bwrap and the observed application process.
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True,
                                   preexec_fn=limit_descriptors)
        follower = object.__new__(UpstreamProcess)
        follower.root = root
        follower.runtime = runtime
        follower.log = log
        follower.process = process
        import selectors
        follower.selector = selectors.DefaultSelector()
        follower.selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        follower.selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        follower.output = {"stdout": bytearray(), "stderr": bytearray()}
        try:
            result = scenario(follower)
            if process.poll() is not None:
                raise AssertionError(f"upstream follower exited: {process.returncode}")
            return result
        finally:
            follower.stop()


class LogFollowLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_cli
        test_cli.CliTests.setUpClass()

    def assert_matches_oracle(self, mode, scenario, *, limited=False):
        runner = run_limited_trace if limited else None
        if runner:
            expected = runner(ORACLE, mode, scenario)
            actual = runner(MODEX, mode, scenario)
        else:
            from test_log_upstream_follow import run_trace
            expected = run_trace(ORACLE, mode, b"not an upstream event\n", scenario)
            actual = run_trace(MODEX, mode, b"not an upstream event\n", scenario)
        self.assertEqual(actual, expected)

    def test_more_than_32_runtime_files_prunes_old_paths_but_follows_recent(self):
        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                def scenario(follower):
                    initial = follower.require_marker("Waiting for processed upstream payload events...")
                    files = []
                    for index in range(40):
                        path = follower.runtime / f"prodex-runtime-{index:02d}.log"
                        path.write_bytes(b"not an upstream event\n")
                        os.utime(path, ns=(index + 1, index + 1))
                        files.append(path)
                    follower.require_quiet(2.4)
                    with files[-1].open("ab") as stream:
                        stream.write(upstream_record("recent-runtime-marker"))
                    recent = follower.require_marker("recent-runtime-marker", timeout=8)
                    with files[0].open("ab") as stream:
                        stream.write(upstream_record("pruned-runtime-marker"))
                    old = follower.collect(0.5)
                    if b"pruned-runtime-marker" in old["stdout"] + old["stderr"]:
                        raise AssertionError("an old runtime file remained followed after pruning")
                    if follower.process.poll() is not None:
                        raise AssertionError("follower exited after runtime file pruning")
                    return [initial, recent, old]

                self.assert_matches_oracle(mode, scenario)

    def test_oversized_partial_line_can_recover_to_valid_event(self):
        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                def scenario(follower):
                    initial = follower.require_marker("Waiting for processed upstream payload events...")
                    follower.require_quiet(2.2)
                    with follower.log.open("ab") as stream:
                        stream.write(b"x" * (1024 * 1024 + 1))
                    overflow = follower.collect(0.5)
                    if follower.process.poll() is not None:
                        raise AssertionError("follower exited after an oversized partial line")
                    with follower.log.open("ab") as stream:
                        stream.write(b"\n" + upstream_record("after-oversized-partial"))
                    recovered = follower.require_marker("after-oversized-partial", timeout=8)
                    return [initial, overflow, recovered]

                self.assert_matches_oracle(mode, scenario)

    def test_recent_file_survives_descriptor_pressure(self):
        if not hasattr(resource, "RLIMIT_NOFILE"):
            self.skipTest("RLIMIT_NOFILE is unavailable")
        for mode in ("json", "plain"):
            with self.subTest(mode=mode):
                def scenario(follower):
                    initial = follower.require_marker("Waiting for processed upstream payload events...")
                    files = []
                    for index in range(40):
                        path = follower.runtime / f"prodex-runtime-{index:02d}.log"
                        path.write_bytes(b"not an upstream event\n")
                        os.utime(path, ns=(index + 1, index + 1))
                        files.append(path)
                    follower.require_quiet(2.4)
                    if follower.process.poll() is not None:
                        raise AssertionError("follower exited at RLIMIT_NOFILE=48")
                    with files[-1].open("ab") as stream:
                        stream.write(upstream_record("descriptor-pressure-marker"))
                    recent = follower.require_marker("descriptor-pressure-marker", timeout=8)
                    return [initial, recent]

                self.assert_matches_oracle(mode, scenario, limited=True)


if __name__ == "__main__":
    unittest.main()
