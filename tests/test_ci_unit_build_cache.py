"""Exercise the Make unit cache with a fake compiler and an isolated build root."""

import fcntl
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = tuple(f"cache_probe_{index}" for index in range(5))
FAKE_MOJO = r'''#!PYTHON_EXECUTABLE
import fcntl
import os
from pathlib import Path
import sys
import time

if sys.argv[1:] == ["--version"]:
    print("Mojo 1.2.0 (2016d0cd)")
    raise SystemExit(0)
if not sys.argv[1:] or sys.argv[1] != "build":
    raise SystemExit(f"unexpected fake Mojo arguments: {sys.argv[1:]}")

arguments = sys.argv[2:]
output = Path(arguments[arguments.index("-o") + 1])
program_name = output.name.rsplit(".tmp.", 1)[0]
flags = " ".join(arguments[:arguments.index("-I")])
source = next(item for item in arguments if item.endswith(".mojo"))
counter = Path(os.environ["MODEX_FAKE_MOJO_COUNTER"])
counter_lock = Path(str(counter) + ".lock")
maximum = Path(str(counter) + ".maximum")
with counter_lock.open("a+") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    active = int(counter.read_text() or "0") if counter.exists() else 0
    active += 1
    counter.write_text(str(active))
    observed = int(maximum.read_text() or "0") if maximum.exists() else 0
    maximum.write_text(str(max(observed, active)))
    with Path(os.environ["MODEX_FAKE_MOJO_LOG"]).open("a") as log:
        log.write(source + " | " + flags + "\n")

try:
    time.sleep(float(os.environ.get("MODEX_FAKE_MOJO_DELAY", "0.12")))
    output.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get("MODEX_FAKE_MOJO_FAIL_AFTER_WRITE"):
        output.write_bytes(b"partial executable that must not be published")
        raise SystemExit("simulated compiler failure after writing a partial output")
    executable = output.with_name(output.name + f".tmp-{os.getpid()}")
    executable.write_text(
        "#!/bin/sh\n# fake compiler flags: " + flags + "\n"
        "printf '%s\\n' '" + program_name + "' >>\"$MODEX_FAKE_MOJO_RUN_LOG\"\n"
        "if [ \"${MODEX_FAKE_MOJO_SPAWN_CHILD:-}\" = 1 ]; then\n"
        "  (sleep 10) >/dev/null 2>&1 &\n"
        "  printf '%s\\n' \"$!\" >\"$MODEX_FAKE_MOJO_CHILD_PID_FILE\"\n"
        "fi\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    executable.replace(output)
finally:
    with counter_lock.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        counter.write_text(str(int(counter.read_text()) - 1))
'''


class UnitBuildCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="modex-unit-cache-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "repo"
        (self.root / "scripts/ci").mkdir(parents=True)
        shutil.copyfile(ROOT / "Makefile", self.root / "Makefile")
        helper = ROOT / "scripts/ci/update-unit-build-state.sh"
        shutil.copyfile(helper, self.root / "scripts/ci/update-unit-build-state.sh")
        (self.root / "scripts/ci/update-unit-build-state.sh").chmod(0o755)
        build_helper = ROOT / "scripts/ci/build-unit-target.sh"
        shutil.copyfile(build_helper, self.root / "scripts/ci/build-unit-target.sh")
        (self.root / "scripts/ci/build-unit-target.sh").chmod(0o755)

        test_runner = self.root / "scripts/ci/run-unittest.py"
        test_runner.write_text(
            "import os\n"
            "from pathlib import Path\n"
            "import time\n"
            "target = Path(os.environ['MODEX_TEST_TARGET'])\n"
            "expected = os.environ['MODEX_TEST_EXPECTED_FLAGS']\n"
            "before = target.read_text()\n"
            "assert 'fake compiler flags: ' + expected in before, before\n"
            "product_name = os.environ.get('MODEX_TEST_PRODUCT_TARGET')\n"
            "product = Path(product_name) if product_name else None\n"
            "product_before = product.read_text() if product else None\n"
            "if product:\n"
            "    assert 'fake compiler flags: ' + expected in product_before, product_before\n"
            "Path(os.environ['MODEX_TEST_PYTHON_STARTED']).write_text('started')\n"
            "time.sleep(float(os.environ.get('MODEX_TEST_PYTHON_DELAY', '0.5')))\n"
            "assert target.read_text() == before, 'unit binary changed during Python suite'\n"
            "if product:\n"
            "    assert product.read_text() == product_before, 'production binary changed during Python suite'\n"
            "Path(os.environ['MODEX_TEST_PYTHON_DONE']).write_text('passed')\n",
            encoding="utf-8",
        )

        (self.root / "src/modex").mkdir(parents=True)
        (self.root / "src/modex/shared.mojo").write_text("# imported source v1\n", encoding="utf-8")
        (self.root / "tests").mkdir()
        for program in PROGRAMS:
            (self.root / "tests" / f"{program}.mojo").write_text(
                "from modex.shared import value\n", encoding="utf-8",
            )

        self.toolchain = self.root / "toolchain"
        (self.toolchain / "bin").mkdir(parents=True)
        self.python_link = self.toolchain / "bin/python-link"
        self.python_link.symlink_to(sys.executable)
        self.mojo = self.toolchain / "bin/mojo"
        self.mojo.write_text(FAKE_MOJO.replace("PYTHON_EXECUTABLE", str(self.python_link)), encoding="utf-8")
        self.mojo.chmod(0o755)
        package_root = self.toolchain / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
        (package_root / "modular/bin").mkdir(parents=True)
        (package_root / "modular/lib/mojo").mkdir(parents=True)
        (package_root / "mojo").mkdir()
        (package_root / "modular/bin/mojo").write_bytes(b"compiler identity v1\n")
        (package_root / "modular/lib/mojo/std.mojoc").write_bytes(b"stdlib identity v1\n")
        (package_root / "mojo/_entrypoints.py").write_text("# launcher identity\n", encoding="utf-8")

        self.fake_bin = self.root / "fake-bin"
        self.fake_bin.mkdir()
        fake_flock = self.fake_bin / "flock"
        fake_flock.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$MODEX_TEST_LOCK_LABEL\" >>\"$MODEX_TEST_LOCK_LOG\"\n"
            "exec /usr/bin/flock \"$@\"\n",
            encoding="utf-8",
        )
        fake_flock.chmod(0o755)

        self.build_dir = self.root / "isolated-build"
        self.compiler_log = self.root / "compiler.log"
        self.run_log = self.root / "run.log"
        self.lock_log = self.root / "lock-attempts.log"
        self.counter = self.root / "active-compilers"
        self.environment = {
            "PATH": os.pathsep.join((str(self.fake_bin), str(Path(sys.executable).parent), "/usr/bin", "/bin")),
            "MODEX_FAKE_MOJO_LOG": str(self.compiler_log),
            "MODEX_FAKE_MOJO_RUN_LOG": str(self.run_log),
            "MODEX_FAKE_MOJO_COUNTER": str(self.counter),
            "MODEX_FAKE_MOJO_CHILD_PID_FILE": str(self.root / "background-child.pid"),
            "MODEX_TEST_LOCK_LOG": str(self.lock_log),
            "MODEX_TEST_LOCK_LABEL": "default",
            "HOME": str(self.root / "home"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }

    def unit_command(self, flags, jobs, programs, build_dir=None, target="unit", python=None):
        build_dir = self.build_dir if build_dir is None else build_dir
        command = [
            "make", "--no-print-directory", target,
            f"BUILD_DIR={build_dir}",
            f"MOJO={self.mojo}",
            f"MOJO_FLAGS={flags}",
            f"MODEX_UNIT_JOBS={jobs}",
            "UNIT_BUILD_PROGRAMS=" + " ".join(programs),
            "UNIT_RUNS=" + " ".join(programs),
        ]
        if python is not None:
            command.append(f"PYTHON={python}")
        return command

    def run_unit(self, flags="-O3 --target-cpu=x86-64-v3", jobs=2, programs=PROGRAMS, check=True):
        result = subprocess.run(
            self.unit_command(flags, jobs, programs),
            cwd=self.root,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
            check=False,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout)
        return result

    def compile_count(self):
        if not self.compiler_log.exists():
            return 0
        return len(self.compiler_log.read_text(encoding="utf-8").splitlines())

    def test_clean_build_reuses_unchanged_outputs_and_bounds_parallelism(self):
        self.run_unit(jobs=2)
        self.assertEqual(self.compile_count(), len(PROGRAMS))
        self.assertEqual(int(Path(str(self.counter) + ".maximum").read_text()), 2)
        self.assertEqual(
            sorted(path.name for path in (self.build_dir / "tests").iterdir()),
            sorted(PROGRAMS),
        )

        self.run_unit(jobs=2)
        self.assertEqual(self.compile_count(), len(PROGRAMS))
        self.assertEqual(
            self.run_log.read_text(encoding="utf-8").splitlines(),
            list(PROGRAMS) * 2,
        )

    def test_imported_source_flags_compiler_and_stdlib_changes_invalidate(self):
        self.run_unit(jobs=2)
        count = len(PROGRAMS)

        shared_source = self.root / "src/modex/shared.mojo"
        shared_source.write_text("# imported source v2\n", encoding="utf-8")
        self.run_unit(jobs=2)
        count += len(PROGRAMS)
        self.assertEqual(self.compile_count(), count)

        shared_source.unlink()
        self.run_unit(jobs=2)
        count += len(PROGRAMS)
        self.assertEqual(self.compile_count(), count)

        self.run_unit(flags="-O2 --target-cpu=x86-64-v3", jobs=2)
        count += len(PROGRAMS)
        self.assertEqual(self.compile_count(), count)

        compiler_identity = self.toolchain / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages/modular/bin/mojo"
        compiler_identity.write_bytes(b"compiler identity v2\n")
        self.run_unit(flags="-O2 --target-cpu=x86-64-v3", jobs=2)
        count += len(PROGRAMS)
        self.assertEqual(self.compile_count(), count)

        stdlib_identity = self.toolchain / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages/modular/lib/mojo/std.mojoc"
        stdlib_identity.write_bytes(b"stdlib identity v2\n")
        self.run_unit(flags="-O2 --target-cpu=x86-64-v3", jobs=2)
        count += len(PROGRAMS)
        self.assertEqual(self.compile_count(), count)

        self.python_link.unlink()
        self.python_link.symlink_to("/usr/bin/python3")
        self.run_unit(flags="-O2 --target-cpu=x86-64-v3", jobs=2)
        count += len(PROGRAMS)
        self.assertEqual(self.compile_count(), count)

    def test_failed_compiler_output_is_not_published_or_reused(self):
        program = (PROGRAMS[0],)
        flags = "-O3 --target-cpu=x86-64-v3"
        self.run_unit(flags=flags, programs=program)
        target = self.build_dir / "tests" / program[0]
        previous_output = target.read_bytes()
        previous_mode = stat.S_IMODE(target.stat().st_mode)
        self.assertEqual(previous_mode, 0o755)

        self.environment["MODEX_FAKE_MOJO_FAIL_AFTER_WRITE"] = "1"
        changed_flags = "-O2 --target-cpu=x86-64-v3"
        failed = self.run_unit(flags=changed_flags, programs=program, check=False)
        self.assertNotEqual(failed.returncode, 0, failed.stdout)
        self.assertIn("simulated compiler failure after writing a partial output", failed.stdout)
        self.assertEqual(target.read_bytes(), previous_output)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), previous_mode)
        self.assertEqual(list(target.parent.glob(target.name + ".tmp.*")), [])

        self.environment.pop("MODEX_FAKE_MOJO_FAIL_AFTER_WRITE")
        self.run_unit(flags=changed_flags, programs=program)
        self.assertEqual(self.compile_count(), 3)
        self.assertTrue(target.is_file())

    def test_future_target_mtime_cannot_hide_source_or_flag_changes(self):
        program = (PROGRAMS[0],)
        flags_a = "-O1 --target-cpu=x86-64-v3"
        flags_b = "-O2 --target-cpu=x86-64-v3"
        self.run_unit(flags=flags_a, programs=program)
        target = self.build_dir / "tests" / program[0]

        future = time.time_ns() + 600_000_000_000
        os.utime(target, ns=(future, future))
        (self.root / "src/modex/shared.mojo").write_text("# changed imported source\n", encoding="utf-8")
        self.run_unit(flags=flags_a, programs=program)
        self.assertEqual(self.compile_count(), 2)

        future = time.time_ns() + 600_000_000_000
        os.utime(target, ns=(future, future))
        self.run_unit(flags=flags_b, programs=program)
        self.assertEqual(self.compile_count(), 3)
        self.assertIn("fake compiler flags: " + flags_b, target.read_text(encoding="utf-8"))

    def test_corrupted_or_chmodded_cached_executable_is_rebuilt(self):
        program = (PROGRAMS[0],)
        flags = "-O3 --target-cpu=x86-64-v3"
        self.run_unit(flags=flags, programs=program)
        target = self.build_dir / "tests" / program[0]
        original = target.read_text(encoding="utf-8")

        target.write_text("#!/bin/sh\n# corrupted cached output\n", encoding="utf-8")
        target.chmod(0o755)
        self.run_unit(flags=flags, programs=program)
        self.assertEqual(self.compile_count(), 2)
        self.assertEqual(target.read_text(encoding="utf-8"), original)

        target.chmod(0o700)
        self.run_unit(flags=flags, programs=program)
        self.assertEqual(self.compile_count(), 3)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o755)
        self.assertEqual(target.read_text(encoding="utf-8"), original)

    def test_overlapping_different_flags_serialize_cache_and_execution(self):
        program = (PROGRAMS[0],)
        flags_a = "-O1 --target-cpu=x86-64-v3"
        flags_b = "-O2 --target-cpu=x86-64-v3"

        environment_a = self.environment.copy()
        environment_a["MODEX_FAKE_MOJO_DELAY"] = "0.8"
        environment_a["MODEX_TEST_LOCK_LABEL"] = "A"
        process_a = subprocess.Popen(
            self.unit_command(flags_a, 1, program),
            cwd=self.root,
            env=environment_a,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.compiler_log.exists() and self.compile_count() >= 1:
                break
            if process_a.poll() is not None:
                output, _ = process_a.communicate()
                self.fail(f"first unit invocation exited before compiling: {output}")
            time.sleep(0.02)
        else:
            process_a.kill()
            output, _ = process_a.communicate()
            self.fail(f"first unit invocation did not reach the compiler: {output}")

        environment_b = self.environment.copy()
        environment_b["MODEX_FAKE_MOJO_DELAY"] = "0.05"
        environment_b["MODEX_TEST_LOCK_LABEL"] = "B"
        build_alias = self.root / "build-alias"
        build_alias.symlink_to(self.build_dir, target_is_directory=True)
        process_b = subprocess.Popen(
            self.unit_command(flags_b, 1, program, build_alias),
            cwd=self.root,
            env=environment_b,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.lock_log.exists() and self.lock_log.read_text(encoding="utf-8").splitlines() == ["A", "B"]:
                break
            if process_b.poll() is not None:
                output, _ = process_b.communicate()
                self.fail(f"second unit invocation exited before lock acquisition: {output}")
            time.sleep(0.02)
        else:
            process_b.kill()
            output, _ = process_b.communicate()
            self.fail(f"second unit invocation did not reach the build lock: {output}")
        self.assertIsNone(process_a.poll(), "first compiler should still hold the lock")
        output_a, _ = process_a.communicate(timeout=30)
        output_b, _ = process_b.communicate(timeout=30)
        self.assertEqual(process_a.returncode, 0, output_a)
        self.assertEqual(process_b.returncode, 0, output_b)

        target = self.build_dir / "tests" / program[0]
        self.assertIn("fake compiler flags: " + flags_b, target.read_text(encoding="utf-8"))
        self.assertEqual(self.compile_count(), 2)

        self.run_unit(flags=flags_b, programs=program)
        self.assertEqual(self.compile_count(), 2)
        self.assertIn("fake compiler flags: " + flags_b, target.read_text(encoding="utf-8"))

    def test_make_test_holds_lock_through_python_suite(self):
        program = (PROGRAMS[0],)
        flags_a = "-O1 --target-cpu=x86-64-v3"
        flags_b = "-O2 --target-cpu=x86-64-v3"
        environment_a = self.environment.copy()
        environment_a.update({
            "MODEX_FAKE_MOJO_DELAY": "0.05",
            "MODEX_TEST_LOCK_LABEL": "test-A",
            "MODEX_TEST_TARGET": str(self.build_dir / "tests" / program[0]),
            "MODEX_TEST_EXPECTED_FLAGS": flags_a,
            "MODEX_TEST_PYTHON_STARTED": str(self.root / "python-started"),
            "MODEX_TEST_PYTHON_DONE": str(self.root / "python-done"),
            "MODEX_TEST_PYTHON_DELAY": "1.0",
        })
        test_process = subprocess.Popen(
            self.unit_command(flags_a, 1, program, target="test", python=sys.executable),
            cwd=self.root,
            env=environment_a,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        deadline = time.monotonic() + 20
        started = Path(environment_a["MODEX_TEST_PYTHON_STARTED"])
        while time.monotonic() < deadline:
            if started.is_file():
                break
            if test_process.poll() is not None:
                output, _ = test_process.communicate()
                self.fail(f"make test exited before Python tests started: {output}")
            time.sleep(0.02)
        else:
            test_process.kill()
            output, _ = test_process.communicate()
            self.fail(f"make test did not start its Python suite: {output}")

        environment_b = self.environment.copy()
        environment_b.update({
            "MODEX_FAKE_MOJO_DELAY": "0.05",
            "MODEX_TEST_LOCK_LABEL": "unit-B",
        })
        build_alias = self.root / "build-alias"
        build_alias.symlink_to(self.build_dir, target_is_directory=True)
        unit_process = subprocess.Popen(
            self.unit_command(flags_b, 1, program, build_alias),
            cwd=self.root,
            env=environment_b,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.lock_log.exists() and self.lock_log.read_text(encoding="utf-8").splitlines() == ["test-A", "unit-B"]:
                break
            if unit_process.poll() is not None:
                output, _ = unit_process.communicate()
                self.fail(f"overlapping unit invocation exited before lock acquisition: {output}")
            time.sleep(0.02)
        else:
            unit_process.kill()
            output, _ = unit_process.communicate()
            self.fail(f"overlapping unit invocation did not reach the build lock: {output}")

        self.assertIsNone(test_process.poll(), "Python suite should still hold the build lock")
        self.assertFalse(Path(environment_a["MODEX_TEST_PYTHON_DONE"]).exists())
        self.assertFalse(any(flags_b in line for line in self.compiler_log.read_text(encoding="utf-8").splitlines()))

        test_output, _ = test_process.communicate(timeout=30)
        unit_output, _ = unit_process.communicate(timeout=30)
        self.assertEqual(test_process.returncode, 0, test_output)
        self.assertEqual(unit_process.returncode, 0, unit_output)
        self.assertEqual(Path(environment_a["MODEX_TEST_PYTHON_DONE"]).read_text(), "passed")

        target = self.build_dir / "tests" / program[0]
        self.assertIn("fake compiler flags: " + flags_b, target.read_text(encoding="utf-8"))
        self.assertEqual(self.compile_count(), 3)  # production build, test driver, overlapping unit driver

    def test_public_build_waits_for_make_test_python_suite(self):
        program = (PROGRAMS[0],)
        flags_a = "-O1 --target-cpu=x86-64-v3"
        flags_b = "-O2 --target-cpu=x86-64-v3"
        environment_a = self.environment.copy()
        environment_a.update({
            "MODEX_FAKE_MOJO_DELAY": "0.05",
            "MODEX_TEST_LOCK_LABEL": "test-A",
            "MODEX_TEST_TARGET": str(self.build_dir / "tests" / program[0]),
            "MODEX_TEST_PRODUCT_TARGET": str(self.build_dir / "modex"),
            "MODEX_TEST_EXPECTED_FLAGS": flags_a,
            "MODEX_TEST_PYTHON_STARTED": str(self.root / "python-started"),
            "MODEX_TEST_PYTHON_DONE": str(self.root / "python-done"),
            "MODEX_TEST_PYTHON_DELAY": "1.0",
        })
        test_process = subprocess.Popen(
            self.unit_command(flags_a, 1, program, target="test", python=sys.executable),
            cwd=self.root,
            env=environment_a,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        deadline = time.monotonic() + 20
        started = Path(environment_a["MODEX_TEST_PYTHON_STARTED"])
        while time.monotonic() < deadline:
            if started.is_file():
                break
            if test_process.poll() is not None:
                output, _ = test_process.communicate()
                self.fail(f"make test exited before Python tests started: {output}")
            time.sleep(0.02)
        else:
            test_process.kill()
            output, _ = test_process.communicate()
            self.fail(f"make test did not start its Python suite: {output}")

        environment_b = self.environment.copy()
        environment_b.update({
            "MODEX_FAKE_MOJO_DELAY": "0.05",
            "MODEX_TEST_LOCK_LABEL": "build-B",
        })
        build_alias = self.root / "build-alias"
        build_alias.symlink_to(self.build_dir, target_is_directory=True)
        build_process = subprocess.Popen(
            self.unit_command(flags_b, 1, program, build_alias, target="build"),
            cwd=self.root,
            env=environment_b,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.lock_log.exists() and self.lock_log.read_text(encoding="utf-8").splitlines() == ["test-A", "build-B"]:
                break
            if build_process.poll() is not None:
                output, _ = build_process.communicate()
                self.fail(f"public build exited before lock acquisition: {output}")
            time.sleep(0.02)
        else:
            build_process.kill()
            output, _ = build_process.communicate()
            self.fail(f"public build did not reach the build lock: {output}")

        self.assertIsNone(test_process.poll(), "Python suite should still hold the build lock")
        self.assertFalse(Path(environment_a["MODEX_TEST_PYTHON_DONE"]).exists())
        self.assertFalse(any(flags_b in line for line in self.compiler_log.read_text(encoding="utf-8").splitlines()))

        test_output, _ = test_process.communicate(timeout=30)
        build_output, _ = build_process.communicate(timeout=30)
        self.assertEqual(test_process.returncode, 0, test_output)
        self.assertEqual(build_process.returncode, 0, build_output)
        self.assertEqual(Path(environment_a["MODEX_TEST_PYTHON_DONE"]).read_text(), "passed")

        product = self.build_dir / "modex"
        self.assertIn("fake compiler flags: " + flags_b, product.read_text(encoding="utf-8"))
        self.assertIn("fake compiler flags: " + flags_a, (self.build_dir / "tests" / program[0]).read_text(encoding="utf-8"))
        self.assertEqual(self.compile_count(), 3)  # test product, test driver, public build product

    def test_locked_unit_does_not_leave_lock_held_by_a_child(self):
        program = (PROGRAMS[0],)
        self.environment["MODEX_FAKE_MOJO_SPAWN_CHILD"] = "1"
        self.run_unit(programs=program)
        child_pid_path = Path(self.environment["MODEX_FAKE_MOJO_CHILD_PID_FILE"])
        child_pid = int(child_pid_path.read_text(encoding="utf-8"))
        lock_path = self.build_dir / ".modex/unit-build.lock"
        try:
            acquired = subprocess.run(
                ["/usr/bin/flock", "--exclusive", "--nonblock", str(lock_path), "/bin/true"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=5,
                check=False,
            )
            self.assertEqual(acquired.returncode, 0, acquired.stdout)
        finally:
            try:
                os.kill(child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    def test_symlinked_sources_and_toolchain_files_are_rejected(self):
        program = (PROGRAMS[0],)
        external_source = self.root / "outside-source.mojo"
        external_source.write_text("# source target\n", encoding="utf-8")
        source_link = self.root / "src/modex/linked.mojo"
        source_link.symlink_to(external_source)
        result = self.run_unit(programs=program, check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("does not support symlinked Mojo sources/imports", result.stdout)
        self.assertEqual(self.compile_count(), 0)

        source_link.unlink()
        package_root = self.toolchain / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
        stdlib = package_root / "modular/lib/mojo/std.mojoc"
        stdlib.unlink()
        external_stdlib = self.root / "outside-stdlib.mojoc"
        external_stdlib.write_bytes(b"outside stdlib target\n")
        stdlib.symlink_to(external_stdlib)
        result = self.run_unit(programs=program, check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("does not support symlinked compiler/stdlib files", result.stdout)
        self.assertEqual(self.compile_count(), 0)


if __name__ == "__main__":
    unittest.main()
