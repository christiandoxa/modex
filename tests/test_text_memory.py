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


def _process_memory_sample(pid, expected_executable):
    try:
        proc = Path(f"/proc/{pid}")
        executable = (proc / "exe").resolve()
        if executable != expected_executable:
            return None
        status = (proc / "status").read_text().splitlines()
        vmhwm = next((line for line in status if line.startswith("VmHWM:")), None)
        if vmhwm is None:
            raise AssertionError(f"/proc/{pid}/status is missing VmHWM")
        peak_rss = int(vmhwm.split()[1]) * 1024
        stat = (proc / "stat").read_text()
        stat_tail = stat[stat.rfind(")") + 2:].split()
        if len(stat_tail) <= 7:
            raise AssertionError(f"/proc/{pid}/stat is missing minflt")
        minor_faults = int(stat_tail[7])
    except (FileNotFoundError, PermissionError):
        pass
    else:
        smaps = None
        try:
            smaps = {}
            for line in (proc / "smaps_rollup").read_text().splitlines():
                name, separator, value = line.partition(":")
                if separator and value.strip().endswith("kB"):
                    smaps[name] = int(value.strip().split()[0]) * 1024
        except OSError:
            smaps = None
        return {"peak_rss_bytes": peak_rss, "minor_faults": minor_faults,
                "smaps_rollup_bytes": smaps}
    return None


def _read_lines(process, output, expected_lines, deadline, mode, count):
    while output.count(b"\n") < expected_lines:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"width driver exceeded 120 seconds: {mode}/{count}")
        ready, _, _ = select.select([process.stdout], [], [], min(0.01, remaining))
        if ready:
            chunk = os.read(process.stdout.fileno(), 4096)
            if not chunk:
                break
            output.extend(chunk)
    return output


def _measure_process_peak_rss(mode, count, operation="width"):
    """Measure resident high-water growth after a same-process input baseline."""
    driver = DRIVER.resolve()
    arguments = [str(driver), mode, str(count), operation, "staged"]
    process = subprocess.Popen(arguments, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, bufsize=0)
    deadline = time.monotonic() + 120
    expected_lines = 2 if operation == "linear-control" else 1
    output = bytearray()
    try:
        output = _read_lines(process, output, 1, deadline, mode, count)
        if output != b"baseline\n":
            raise AssertionError(f"width driver emitted unexpected baseline marker: {output!r}")
        baseline = _process_memory_sample(process.pid, driver)
        if baseline is None:
            raise AssertionError(f"width driver baseline was unavailable: {mode}/{count}")
        process.stdin.write(b"continue\n")
        process.stdin.flush()
        output.clear()
        output = _read_lines(process, output, expected_lines, deadline, mode, count)
        if output.count(b"\n") < expected_lines:
            rest, error = process.communicate(timeout=max(1, deadline - time.monotonic()))
            output.extend(rest)
            if process.returncode != 0:
                raise AssertionError(f"width driver failed for {mode}/{count}: {output!r} {error!r}")
            raise AssertionError(f"width driver exited before complete output: {mode}/{count}")
        post = _process_memory_sample(process.pid, driver)
        if post is None:
            raise AssertionError(f"width driver post-operation sample was unavailable: {mode}/{count}")
        process.stdin.write(b"continue\n")
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
    smaps_growth = None
    if baseline["smaps_rollup_bytes"] is not None and post["smaps_rollup_bytes"] is not None:
        smaps_growth = {name: post["smaps_rollup_bytes"].get(name, 0)
                        - baseline["smaps_rollup_bytes"].get(name, 0)
                        for name in baseline["smaps_rollup_bytes"].keys()
                        | post["smaps_rollup_bytes"].keys()}
    sample = {
        "baseline_peak_rss_bytes": baseline["peak_rss_bytes"],
        "post_peak_rss_bytes": post["peak_rss_bytes"],
        "peak_rss_growth_bytes": post["peak_rss_bytes"] - baseline["peak_rss_bytes"],
        "baseline_minor_faults": baseline["minor_faults"],
        "post_minor_faults": post["minor_faults"],
        "minor_fault_growth": post["minor_faults"] - baseline["minor_faults"],
        "baseline_smaps_rollup_bytes": baseline["smaps_rollup_bytes"],
        "post_smaps_rollup_bytes": post["smaps_rollup_bytes"],
        "smaps_rollup_growth_bytes": smaps_growth,
    }
    return output, sample


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
        "peak_rss_source": "same-process /proc/<pid>/status VmHWM after input baseline",
        "vmhwm_unit": "KiB, converted to bytes in samples",
        "peak_rss_growth_sample_unit": "bytes",
        "minor_fault_source": "/proc/<pid>/stat minflt",
        "smaps_rollup_source": "/proc/<pid>/smaps_rollup when readable",
        "measurement_limit": (
            "Measures incremental resident high-water growth; allocations that reuse already-"
            "resident allocator pages may not increase VmHWM or minor faults."
        ),
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
            raise unittest.SkipTest("staged /proc VmHWM measurement is Linux-only")
        proc_status = Path("/proc/self/status")
        if not proc_status.is_file():
            raise unittest.SkipTest("Linux /proc status files are unavailable")
        if not any(line.startswith("VmHWM:") for line in proc_status.read_text().splitlines()):
            raise unittest.SkipTest("Linux /proc status files do not expose VmHWM")
        proc_stat = Path("/proc/self/stat")
        if not proc_stat.is_file():
            raise unittest.SkipTest("Linux /proc stat files do not expose minflt")
        self_stat = proc_stat.read_text()
        if len(self_stat[self_stat.rfind(")") + 2:].split()) <= 7:
            raise unittest.SkipTest("Linux /proc stat files do not expose minflt")
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
                # The driver measures each operation after constructing this retained input.
                operations = {}
                for operation in ("input-only", "width", "linear-control"):
                    samples = []
                    outputs = []
                    for _ in range(3):
                        result, sample = _measure_process_peak_rss(mode, count, operation)
                        outputs.append(result)
                        samples.append(sample)
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
                    peak_growths = [sample["peak_rss_growth_bytes"] for sample in samples]
                    operations[operation.replace("-", "_")] = {
                        "peak_rss_growth_samples_bytes": peak_growths,
                        "median_peak_rss_growth_bytes": statistics.median(peak_growths),
                        "sample_spread_bytes": max(peak_growths) - min(peak_growths),
                        "samples": samples,
                    }
                points.append({"count": count, "input_bytes": _input_bytes(mode, count), **operations})
            input_growth = points[1]["input_bytes"] - points[0]["input_bytes"]
            width_growth = (points[1]["width"]["median_peak_rss_growth_bytes"]
                            - points[0]["width"]["median_peak_rss_growth_bytes"])
            input_only_growth = (points[1]["input_only"]["median_peak_rss_growth_bytes"]
                                 - points[0]["input_only"]["median_peak_rss_growth_bytes"])
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
            control_growth = (points[1]["linear_control"]["median_peak_rss_growth_bytes"]
                              - points[0]["linear_control"]["median_peak_rss_growth_bytes"])
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
