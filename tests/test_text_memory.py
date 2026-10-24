"""Measure text_width working-set growth and compare large session text to Prodex."""

import json
import os
from pathlib import Path
import platform
import select
import signal
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import unittest

import test_cli
from session_oracle import fixture, sandbox_command
from test_cli import ORACLE, ROOT


ARTIFACTS = ROOT / "test-results/text-memory"
DRIVER = ROOT / "build/tests/width_memory_driver"
MIB = 1024 * 1024
SESSION_LINE_LIMIT = 64 * MIB
MIXED = "A界e\u0301🙂"


def _input_bytes(mode, count):
    if mode == "ascii":
        return count
    if mode == "mixed":
        return count * len(MIXED.encode("utf-8"))
    if mode == "tifinagh":
        return 3 + count * 6
    if mode == "kirat":
        return count * 4
    return 8 + count * 4


def _measure_width_process(mode, count):
    # A fresh harness prevents fork's inherited RSS floor from masking driver growth.
    result = subprocess.run([sys.executable, __file__, "--measure-width", mode, str(count)],
                            capture_output=True, text=True, timeout=130, check=True)
    return json.loads(result.stdout)


def _wait4_width_process(mode, count):
    """Return output and wait4 peak RSS for one isolated Mojo process."""
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(read_fd)
            os.dup2(write_fd, 1)
            os.close(write_fd)
            os.execv(str(DRIVER), [str(DRIVER), mode, str(count)])
        except BaseException as error:
            try:
                os.write(2, f"width driver exec failed: {error}\n".encode())
            finally:
                os._exit(127)

    os.close(write_fd)
    deadline = time.monotonic() + 120
    status = None
    usage = None
    eof = False
    output = bytearray()
    try:
        while status is None or not eof:
            if status is None:
                waited, status, usage = os.wait4(pid, os.WNOHANG)
                if waited == 0:
                    status = None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if status is None:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    _, status, usage = os.wait4(pid, 0)
                raise TimeoutError(f"width driver exceeded 120 seconds: {mode}/{count}")
            ready, _, _ = select.select([read_fd], [], [], min(0.05, remaining))
            if ready:
                chunk = os.read(read_fd, 4096)
                if chunk:
                    output.extend(chunk)
                else:
                    eof = True
    finally:
        os.close(read_fd)
    output = output.decode("ascii").strip()
    if os.waitstatus_to_exitcode(status) != 0:
        raise AssertionError(f"width driver failed for {mode}/{count}: {output!r}")
    return int(output), usage.ru_maxrss * 1024


def _record_host():
    available = None
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemAvailable:"):
                available = int(line.split()[1]) * 1024
                break
    cgroup = None
    for path in (Path("/sys/fs/cgroup/memory.max"),
                 Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")):
        if path.is_file():
            value = path.read_text().strip()
            if value != "max":
                cgroup = value
            break
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "page_size_bytes": os.sysconf("SC_PAGE_SIZE"),
        "mem_available_bytes_at_start": available,
        "cgroup_memory_limit_bytes": cgroup,
        "ru_maxrss_unit": "KiB (Linux wait4)",
    }


def _set_title(path, title):
    records = path.read_text().splitlines()
    metadata = json.loads(records[0])
    metadata["payload"]["thread_name"] = title
    path.write_text(json.dumps(metadata, ensure_ascii=False) + "\n" + "\n".join(records[1:]) + "\n")


class WidthMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if platform.system() != "Linux":
            raise unittest.SkipTest("wait4 peak RSS measurement is Linux-only")
        if not DRIVER.is_file():
            raise AssertionError("Build test driver at build/tests/width_memory_driver")
        ARTIFACTS.mkdir(parents=True, exist_ok=True)

    def test_auxiliary_rss_does_not_scale_with_non_ascii_input(self):
        measurements = {"host": _record_host(), "patterns": {}}
        failures = []
        cases = {
            "ascii": (512 * 1024, 8 * MIB),
            "mixed": (48 * 1024, 768 * 1024),
            "tifinagh": (32 * 1024, 512 * 1024),
            "kirat": (32 * 1024, 512 * 1024),
            "emoji-tag": (32 * 1024, 512 * 1024),
        }
        for mode, (small, large) in cases.items():
            points = []
            for count in (small, large):
                peak_samples = []
                overhead_samples = []
                for _ in range(3):
                    width, peak = _measure_width_process(mode, count)
                    expected = (count if mode in ("ascii", "kirat") else count * 6 if mode == "mixed"
                                else (count + 2) // 2 if mode == "tifinagh" else 2)
                    if width != expected:
                        failures.append(f"{mode}: got width {width}, expected {expected} for {count}")
                    peak_samples.append(peak)
                    overhead_samples.append(peak - _input_bytes(mode, count))
                points.append({"count": count, "input_bytes": _input_bytes(mode, count),
                               "peak_rss_samples_bytes": peak_samples,
                               "median_peak_rss_bytes": statistics.median(peak_samples),
                               "median_rss_over_input_bytes": statistics.median(overhead_samples),
                               "overhead_sample_spread_bytes": max(overhead_samples) - min(overhead_samples)})
            input_growth = points[1]["input_bytes"] - points[0]["input_bytes"]
            overhead_growth = (points[1]["median_rss_over_input_bytes"]
                               - points[0]["median_rss_over_input_bytes"])
            sample_noise = (points[0]["overhead_sample_spread_bytes"]
                            + points[1]["overhead_sample_spread_bytes"])
            tolerance = sample_noise + max(16 * measurements["host"]["page_size_bytes"], input_growth // 100)
            points[1]["normalized_growth_bytes"] = overhead_growth
            points[1]["allowed_growth_bytes"] = tolerance
            if overhead_growth > tolerance:
                failures.append(
                    f"{mode} auxiliary RSS grew {overhead_growth} bytes over {tolerance}; points={points}"
                )
            measurements["patterns"][mode] = points
        (ARTIFACTS / "width-rss.json").write_text(json.dumps(measurements, indent=2) + "\n")
        self.assertEqual(failures, [], f"see {ARTIFACTS / 'width-rss.json'}")


class SessionTextMemoryParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_cli.CliTests.setUpClass()

    def test_large_mixed_title_output_matches_checksum_verified_oracle(self):
        title = MIXED * 100_000

        def change(root):
            path = next((root / "home/.codex").rglob("*.jsonl"))
            _set_title(path, title)

        with tempfile.TemporaryDirectory(prefix="modex-large-title-") as directory:
            root = Path(directory) / "fixture"
            outputs = []
            for binary in (ORACLE, test_cli.MODEX):
                root.mkdir()
                fixture(root)
                change(root)
                command = sandbox_command(binary, root, ["session", "list"],
                                          environment={"PRODEX_TERM_COLUMNS": "110"})
                result = subprocess.run(command, capture_output=True, timeout=120, check=False)
                outputs.append((result.returncode, result.stdout, result.stderr))
                shutil.rmtree(root)
            self.assertEqual(outputs[0], outputs[1])

    def test_session_line_limit_and_overflow_match_oracle(self):
        with tempfile.TemporaryDirectory(prefix="modex-session-line-boundary-") as directory:
            root = Path(directory) / "fixture"
            for line_size in (SESSION_LINE_LIMIT, SESSION_LINE_LIMIT + 1):
                outputs = []
                for binary in (ORACLE, test_cli.MODEX):
                    root.mkdir()
                    fixture(root)
                    path = next((root / "home/.codex").rglob("*.jsonl"))
                    records = path.read_text().splitlines()
                    metadata = json.loads(records[0])
                    metadata["payload"]["thread_name"] = ""
                    empty = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
                    title_size = line_size - len(empty) - 1
                    metadata["payload"]["thread_name"] = "x" * title_size
                    header = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
                    self.assertEqual(len(header) + 1, line_size)
                    path.write_bytes(header + b"\n" + records[1].encode() + b"\n")
                    command = sandbox_command(binary, root, ["session", "list"],
                                              environment={"PRODEX_TERM_COLUMNS": "110"})
                    result = subprocess.run(command, capture_output=True, timeout=300, check=False)
                    outputs.append((result.returncode, result.stdout, result.stderr))
                    shutil.rmtree(root)
                self.assertEqual(outputs[0], outputs[1], f"line size {line_size}")
                self.assertEqual(outputs[0][0] == 0, line_size == SESSION_LINE_LIMIT,
                                 f"baseline behavior at line size {line_size}")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--measure-width":
        print(json.dumps(_wait4_width_process(sys.argv[2], int(sys.argv[3]))))
    else:
        unittest.main()
