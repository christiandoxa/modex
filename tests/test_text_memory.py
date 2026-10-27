"""Measure text_width working-set growth and compare large session text to Prodex."""

import json
import os
from pathlib import Path
import platform
import select
import shutil
import statistics
import subprocess
import tempfile
import time
import unittest

import test_cli
from session_oracle import fixture, sandbox_command
from test_cli import ORACLE, ROOT


ARTIFACTS = Path(os.environ.get("MODEX_WIDTH_MEMORY_ARTIFACTS", ROOT / "test-results/text-memory"))
DRIVER = Path(os.environ.get("MODEX_WIDTH_MEMORY_DRIVER", ROOT / "build/tests/width_memory_driver"))
MIB = 1024 * 1024
SESSION_LINE_LIMIT = 64 * MIB
LINEAR_CONTROL_BYTES_PER_UNIT = 4
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


def _process_peak_rss_bytes(pid, expected_executable):
    try:
        executable = Path(f"/proc/{pid}/exe").resolve()
        if executable != expected_executable:
            return None
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024
    except FileNotFoundError:
        pass
    return None


def _measure_process_peak_rss(mode, count, operation="width"):
    """Sample a direct-exec Mojo process's kernel peak RSS, excluding the Python parent."""
    driver = DRIVER.resolve()
    arguments = [str(driver), mode, str(count), operation, "hold"]
    process = subprocess.Popen(arguments, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    deadline = time.monotonic() + 120
    peak_rss = 0
    expected_lines = 2 if operation == "linear-control" else 1
    output = bytearray()
    try:
        while output.count(b"\n") < expected_lines:
            peak = _process_peak_rss_bytes(process.pid, driver)
            if peak is not None:
                peak_rss = max(peak_rss, peak)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"width driver exceeded 120 seconds: {mode}/{count}")
            ready, _, _ = select.select([process.stdout], [], [], min(0.01, remaining))
            if ready:
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    break
                output.extend(chunk)
        peak = _process_peak_rss_bytes(process.pid, driver)
        if peak is not None:
            peak_rss = max(peak_rss, peak)
        if output.count(b"\n") < expected_lines:
            rest, error = process.communicate(timeout=max(1, deadline - time.monotonic()))
            output.extend(rest)
            if process.returncode != 0:
                raise AssertionError(f"width driver failed for {mode}/{count}: {output!r} {error!r}")
            raise AssertionError(f"width driver exited before complete output: {mode}/{count}")
        if peak_rss == 0:
            raise AssertionError(f"width driver exited before VmHWM could be sampled: {mode}/{count}")
        process.stdin.write(b"\n")
        process.stdin.flush()
        rest, error = process.communicate(timeout=max(1, deadline - time.monotonic()))
        output.extend(rest)
    finally:
        if process.poll() is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            process.communicate()
    if process.returncode != 0:
        raise AssertionError(f"width driver failed for {mode}/{count}: {output!r} {error!r}")
    output = output.decode("ascii").strip()
    if operation == "linear-control":
        lines = output.splitlines()
        if len(lines) != 2:
            raise AssertionError(f"linear control returned unexpected output: {output!r}")
        output = [int(lines[0]), int(lines[1])]
    else:
        output = int(output)
    return output, peak_rss


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
        "peak_rss_source": "/proc/<pid>/status VmHWM after direct exec",
        "vmhwm_unit": "KiB, converted to bytes in samples",
        "peak_rss_sample_unit": "bytes",
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
            raise unittest.SkipTest("/proc VmHWM peak RSS measurement is Linux-only")
        proc_status = Path("/proc/self/status")
        if not proc_status.is_file():
            raise unittest.SkipTest("Linux /proc status files are unavailable")
        if not any(line.startswith("VmHWM:") for line in proc_status.read_text().splitlines()):
            raise unittest.SkipTest("Linux /proc status files do not expose VmHWM")
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
                # Compare identical input construction so allocator pages and runtime setup cancel.
                operations = {}
                for operation in ("input-only", "width", "linear-control"):
                    samples = []
                    outputs = []
                    for _ in range(3):
                        result, peak = _measure_process_peak_rss(mode, count, operation)
                        outputs.append(result)
                        samples.append(peak)
                    expected_width = (
                        count if mode in ("ascii", "kirat") else count * 6 if mode == "mixed"
                        else (count + 2) // 2 if mode == "tifinagh" else 2
                    )
                    if operation == "input-only":
                        expected = _input_bytes(mode, count)
                    elif operation == "linear-control":
                        expected = [expected_width, count * LINEAR_CONTROL_BYTES_PER_UNIT]
                    else:
                        expected = expected_width
                    if outputs != [expected] * 3:
                        failures.append(
                            f"{mode} {operation}: "
                            f"got {outputs}, expected {expected} for {count}"
                        )
                    operations[operation.replace("-", "_")] = {
                        "peak_rss_samples_bytes": samples,
                        "median_peak_rss_bytes": statistics.median(samples),
                        "sample_spread_bytes": max(samples) - min(samples),
                    }
                points.append({"count": count, "input_bytes": _input_bytes(mode, count), **operations})
            input_growth = points[1]["input_bytes"] - points[0]["input_bytes"]
            width_growth = (points[1]["width"]["median_peak_rss_bytes"]
                            - points[0]["width"]["median_peak_rss_bytes"])
            input_only_growth = (points[1]["input_only"]["median_peak_rss_bytes"]
                                 - points[0]["input_only"]["median_peak_rss_bytes"])
            auxiliary_growth = width_growth - input_only_growth
            sample_noise = sum(point[operation]["sample_spread_bytes"]
                               for point in points for operation in ("width", "input_only"))
            tolerance = sample_noise + max(16 * measurements["host"]["page_size_bytes"], input_growth // 100)
            points[1]["normalized_growth_bytes"] = auxiliary_growth
            points[1]["allowed_growth_bytes"] = tolerance
            if auxiliary_growth > tolerance:
                failures.append(
                    f"{mode} text_width auxiliary RSS grew {auxiliary_growth} bytes over "
                    f"{tolerance}; width growth={width_growth}, input construction growth="
                    f"{input_only_growth}, points={points}"
                )
            control_growth = (points[1]["linear_control"]["median_peak_rss_bytes"]
                              - points[0]["linear_control"]["median_peak_rss_bytes"])
            control_auxiliary_growth = control_growth - input_only_growth
            points[1]["linear_control_normalized_growth_bytes"] = control_auxiliary_growth
            points[1]["linear_control_required_growth_bytes"] = tolerance
            if control_auxiliary_growth <= tolerance:
                failures.append(
                    f"{mode} linear-control was not detected by the production RSS bound: "
                    f"growth={control_auxiliary_growth}, required>{tolerance}, points={points}"
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
    unittest.main()
