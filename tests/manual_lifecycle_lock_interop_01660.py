"""Linux-only syscall characterization; this is not a Modex parity test."""

import selectors
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


FLOCK_OWNER = r'''import fcntl, sys
with open(sys.argv[1], "a+") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    print("flock-owner-ready", flush=True)
    sys.stdin.readline()
'''
FLOCK_CONTENDER = r'''import fcntl, sys
with open(sys.argv[1], "a+") as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("flock-blocked")
    else:
        raise SystemExit("flock contender unexpectedly acquired")
'''
RECORD_LOCK_CONTENDER = r'''import fcntl, sys
with open(sys.argv[1], "a+") as lock:
    fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    print("record-lock-acquired")
'''


class LifecycleLockInterop01660Tests(unittest.TestCase):
    def test_fcntl_record_lock_does_not_contend_with_flock(self):
        with tempfile.TemporaryDirectory(
            prefix="modex-lock-interop-01660-", dir="/tmp"
        ) as root:
            lock_path = str(Path(root) / "profile-lifecycle.json.lock")
            child_environment = {
                "HOME": root,
                "TMPDIR": root,
                "PATH": "/usr/bin:/bin",
                "LANG": "C",
            }
            owner = subprocess.Popen(
                [sys.executable, "-I", "-S", "-c", FLOCK_OWNER, lock_path],
                cwd=root,
                env=child_environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            try:
                with selectors.DefaultSelector() as ready:
                    ready.register(owner.stdout, selectors.EVENT_READ)
                    self.assertTrue(ready.select(timeout=3), "flock owner did not become ready")
                    self.assertEqual(owner.stdout.readline(), "flock-owner-ready\n")

                flock_result = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-S",
                        "-c",
                        FLOCK_CONTENDER,
                        lock_path,
                    ],
                    cwd=root,
                    env=child_environment,
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
                self.assertEqual(
                    (flock_result.returncode, flock_result.stdout.strip()),
                    (0, "flock-blocked"),
                    flock_result.stderr,
                )

                record_result = subprocess.run(
                    [
                        sys.executable,
                        "-I",
                        "-S",
                        "-c",
                        RECORD_LOCK_CONTENDER,
                        lock_path,
                    ],
                    cwd=root,
                    env=child_environment,
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
                self.assertEqual(
                    (record_result.returncode, record_result.stdout.strip()),
                    (0, "record-lock-acquired"),
                    record_result.stderr,
                )
            finally:
                if owner.poll() is None:
                    try:
                        owner.stdin.write("release\n")
                        owner.stdin.flush()
                    except (BrokenPipeError, OSError):
                        pass
                try:
                    owner.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    owner.kill()
                    owner.communicate(timeout=3)


if __name__ == "__main__":
    if sys.platform != "linux":
        raise SystemExit("manual characterization runs on Linux only")
    unittest.main()
