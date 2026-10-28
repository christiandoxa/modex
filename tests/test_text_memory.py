"""Measure text_width working-set growth and compare large session text to Prodex."""

import ctypes
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
MINOR_FAULT_EVENT_ALLOWANCE = 1
MAX_MEMORY_FAILURE_MESSAGE_CHARS = 1200
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


def _input_normalized_growth(points, operation, metric):
    return ((points[1][operation][metric] - points[0][operation][metric])
            - (points[1]["input_only"][metric] - points[0]["input_only"][metric]))


def _minor_fault_event_allowance(points):
    sample_noise_events = sum(
        point[operation]["minor_fault_sample_spread_events"]
        for point in points for operation in ("width", "input_only")
    )
    return sample_noise_events + MINOR_FAULT_EVENT_ALLOWANCE


def _control_minor_fault_allowance(point):
    return (point["linear_control"]["minor_fault_sample_spread_events"]
            + point["input_only"]["minor_fault_sample_spread_events"]
            + MINOR_FAULT_EVENT_ALLOWANCE)


def _peak_rss_control_allowance(points, base_allowance):
    sample_noise_bytes = sum(
        points[1][operation]["peak_rss_sample_spread_bytes"]
        for operation in ("input_only", "linear_control")
    )
    return sample_noise_bytes + base_allowance


def _evaluate_memory_points(points, page_size_bytes):
    """Apply the production thresholds to small/large point summaries."""
    input_growth = points[1]["input_bytes"] - points[0]["input_bytes"]
    base_allowance = max(16 * page_size_bytes, input_growth // 100)
    failures = []

    anonymous_width_growth = _input_normalized_growth(
        points, "width", "median_anonymous_rss_growth_bytes")
    anonymous_width_noise = sum(point[operation]["anonymous_sample_spread_bytes"]
                                for point in points for operation in ("width", "input_only"))
    anonymous_allowance = anonymous_width_noise + base_allowance
    points[1]["anonymous_normalized_growth_bytes"] = anonymous_width_growth
    points[1]["anonymous_allowed_growth_bytes"] = anonymous_allowance
    if anonymous_width_growth > anonymous_allowance:
        failures.append(
            f"width anonymous RSS {anonymous_width_growth}>{anonymous_allowance} bytes"
        )

    large = points[1]
    anonymous_control_growth = (
        large["linear_control"]["median_anonymous_rss_growth_bytes"]
        - large["input_only"]["median_anonymous_rss_growth_bytes"]
    )
    anonymous_control_allowance = (
        large["linear_control"]["anonymous_sample_spread_bytes"]
        + large["input_only"]["anonymous_sample_spread_bytes"]
        + base_allowance
    )
    points[1]["linear_control_anonymous_normalized_growth_bytes"] = anonymous_control_growth
    points[1]["linear_control_anonymous_required_growth_bytes"] = anonymous_control_allowance
    if anonymous_control_growth <= anonymous_control_allowance:
        failures.append(
            f"anonymous control {anonymous_control_growth}<={anonymous_control_allowance} bytes"
        )

    fault_width_growth = _input_normalized_growth(
        points, "width", "median_minor_fault_growth_events")
    fault_width_allowance = _minor_fault_event_allowance(points)
    points[1]["minor_fault_normalized_growth_events"] = fault_width_growth
    points[1]["minor_fault_allowed_growth_events"] = fault_width_allowance
    if fault_width_growth > fault_width_allowance:
        failures.append(f"width minflt {fault_width_growth}>{fault_width_allowance} events")

    # Event counts stay events. A one-event floor tolerates one changed fault;
    # the independent byte controls establish that the allocation actually ran.
    fault_control_growth = (
        large["linear_control"]["median_minor_fault_growth_events"]
        - large["input_only"]["median_minor_fault_growth_events"]
    )
    fault_control_allowance = _control_minor_fault_allowance(large)
    points[1]["linear_control_minor_fault_normalized_growth_events"] = fault_control_growth
    points[1]["linear_control_minor_fault_required_growth_events"] = fault_control_allowance
    if fault_control_growth <= fault_control_allowance:
        failures.append(
            f"minflt control {fault_control_growth}<={fault_control_allowance} events"
        )

    peak_control_growth = (
        large["linear_control"]["median_peak_rss_growth_bytes"]
        - large["input_only"]["median_peak_rss_growth_bytes"]
    )
    peak_control_allowance = _peak_rss_control_allowance(points, base_allowance)
    points[1]["linear_control_peak_rss_normalized_growth_bytes"] = peak_control_growth
    points[1]["linear_control_peak_rss_required_growth_bytes"] = peak_control_allowance
    if peak_control_growth <= peak_control_allowance:
        failures.append(
            f"VmHWM control {peak_control_growth}<={peak_control_allowance} bytes"
        )
    points[1]["memory_base_allowance_bytes"] = base_allowance
    return failures


def _memory_failure_message(failures, artifact_path):
    prefix = f"width-memory checks failed ({len(failures)}): "
    artifact = str(artifact_path)[-160:]
    suffix = f"; see {artifact}"
    details = "; ".join(failures[:8])
    available = max(0, MAX_MEMORY_FAILURE_MESSAGE_CHARS - len(prefix) - len(suffix))
    omitted = f"; and {len(failures) - 8} more" if len(failures) > 8 else ""
    details = details[:max(0, available - len(omitted))] + omitted
    return prefix + details + suffix


def _process_memory_sample(pid, expected_executable):
    try:
        proc = Path(f"/proc/{pid}")
        executable = (proc / "exe").resolve()
        if executable != expected_executable:
            return None
        status = (proc / "status").read_text().splitlines()
        thp_enabled = next((line for line in status if line.startswith("THP_enabled:")), None)
        if thp_enabled is None or thp_enabled.split()[1] != "0":
            raise AssertionError(f"/proc/{pid}/status does not confirm THP is disabled")
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


def _disable_transparent_huge_pages():
    # PR_SET_THP_DISABLE is Linux-specific and applies only to this measurement child.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(41, 1, 0, 0, 0) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _measure_process_peak_rss(mode, count, operation="width"):
    """Measure resident high-water growth after a same-process input baseline."""
    driver = DRIVER.resolve()
    arguments = [str(driver), mode, str(count), operation, "staged"]
    process = subprocess.Popen(arguments, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, bufsize=0,
                                preexec_fn=_disable_transparent_huge_pages)
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
    if smaps_growth is None or "Anonymous" not in smaps_growth or "Rss" not in smaps_growth:
        raise AssertionError(f"width driver smaps_rollup lacks required Rss/Anonymous fields: {mode}/{count}")
    minor_fault_growth = post["minor_faults"] - baseline["minor_faults"]
    sample = {
        "baseline_peak_rss_bytes": baseline["peak_rss_bytes"],
        "post_peak_rss_bytes": post["peak_rss_bytes"],
        "peak_rss_growth_bytes": post["peak_rss_bytes"] - baseline["peak_rss_bytes"],
        "anonymous_rss_growth_bytes": max(0, smaps_growth["Anonymous"]),
        "minor_fault_growth_events": minor_fault_growth,
        "transparent_huge_pages_disabled": True,
        "baseline_minor_faults": baseline["minor_faults"],
        "post_minor_faults": post["minor_faults"],
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
        "anonymous_rss_source": "same-process /proc/<pid>/smaps_rollup Anonymous after input baseline",
        "minor_fault_source": "/proc/<pid>/stat minflt event count",
        "transparent_huge_pages": (
            "disabled per measurement process with Linux PR_SET_THP_DISABLE; verified by "
            "/proc/<pid>/status THP_enabled at both measurement samples"
        ),
        "linear_control": (
            f"one allocate-touch-release pass at {LINEAR_CONTROL_BYTES_PER_UNIT} bytes per input unit; "
            "compared with same-size input-only runs"
        ),
        "smaps_rollup_source": "/proc/<pid>/smaps_rollup Rss/Anonymous required; retained as diagnostics",
        "measurement_limit": (
            "Anonymous RSS growth measures bytes still resident at the post-operation sample; "
            "allocations that reuse already-resident allocator pages or are returned before that "
            "sample may be missed. minflt is an event count, never a byte estimate, and also "
            "counts code/file faults. Transparent huge pages are disabled in measurement children "
            "to keep the linear positive control observable at its original size; these results "
            "do not characterize allocator behavior with THP enabled. "
            "The transient control checks VmHWM growth, but VmHWM is total RSS and can be masked "
            "by a higher pre-operation peak or include file/code residency; resident-page reuse "
            "and smaller peaks remain limits."
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
        proc_smaps = Path("/proc/self/smaps_rollup")
        if not proc_smaps.is_file():
            raise unittest.SkipTest("Linux /proc smaps_rollup is unavailable")
        smaps_fields = {line.partition(":")[0] for line in proc_smaps.read_text().splitlines()}
        if not {"Rss", "Anonymous"} <= smaps_fields:
            raise unittest.SkipTest("Linux /proc smaps_rollup does not expose Rss and Anonymous")
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
                        expected = [_input_bytes(mode, count), count * LINEAR_CONTROL_BYTES_PER_UNIT]
                    else:
                        expected = expected_width
                    if outputs != [expected] * 3:
                        failures.append(
                            f"{mode} {operation}: "
                            f"got {outputs}, expected {expected} for {count}"
                        )
                    anonymous_growths = [sample["anonymous_rss_growth_bytes"] for sample in samples]
                    peak_rss_growths = [sample["peak_rss_growth_bytes"] for sample in samples]
                    minor_fault_growths = [sample["minor_fault_growth_events"] for sample in samples]
                    operations[operation.replace("-", "_")] = {
                        "peak_rss_growth_samples_bytes": peak_rss_growths,
                        "median_peak_rss_growth_bytes": statistics.median(peak_rss_growths),
                        "peak_rss_sample_spread_bytes": max(peak_rss_growths) - min(peak_rss_growths),
                        "anonymous_rss_growth_samples_bytes": anonymous_growths,
                        "median_anonymous_rss_growth_bytes": statistics.median(anonymous_growths),
                        "anonymous_sample_spread_bytes": max(anonymous_growths) - min(anonymous_growths),
                        "minor_fault_growth_samples_events": minor_fault_growths,
                        "median_minor_fault_growth_events": statistics.median(minor_fault_growths),
                        "minor_fault_sample_spread_events": max(minor_fault_growths) - min(minor_fault_growths),
                        "samples": samples,
                    }
                points.append({"count": count, "input_bytes": _input_bytes(mode, count), **operations})
            failures.extend(
                f"{mode} {failure}"
                for failure in _evaluate_memory_points(
                    points, measurements["host"]["page_size_bytes"])
            )
            measurements["patterns"][mode] = points
        (ARTIFACTS / "width-rss.json").write_text(json.dumps(measurements, indent=2) + "\n")
        if failures:
            self.fail(_memory_failure_message(failures, ARTIFACTS / "width-rss.json"))


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


class MemoryMetricFixtureTests(unittest.TestCase):
    @staticmethod
    def _point(input_bytes, *, width_anon=0, width_faults=0, control_anon=0,
               control_faults=0, control_peak=0, input_anon=0, input_faults=0,
               input_peak=0, width_anon_spread=0, input_anon_spread=0,
               control_anon_spread=0, width_fault_spread=0, input_fault_spread=0,
               control_fault_spread=0, input_peak_spread=0, control_peak_spread=0):
        def operation(anon=0, faults=0, peak=0, anon_spread=0, fault_spread=0, peak_spread=0):
            return {
                "median_peak_rss_growth_bytes": peak,
                "peak_rss_sample_spread_bytes": peak_spread,
                "median_anonymous_rss_growth_bytes": anon,
                "anonymous_sample_spread_bytes": anon_spread,
                "median_minor_fault_growth_events": faults,
                "minor_fault_sample_spread_events": fault_spread,
            }

        return {
            "input_bytes": input_bytes,
            "input_only": operation(input_anon, input_faults, input_peak, input_anon_spread,
                                     input_fault_spread, input_peak_spread),
            "width": operation(width_anon, width_faults, anon_spread=width_anon_spread,
                                fault_spread=width_fault_spread),
            "linear_control": operation(control_anon, control_faults, control_peak,
                                        control_anon_spread, control_fault_spread,
                                        control_peak_spread),
        }

    @classmethod
    def _valid_points(cls, control_fault_events):
        return [
            cls._point(MIB // 2),
            cls._point(4 * MIB + MIB // 2, control_anon=4 * MIB,
                       control_faults=control_fault_events, control_peak=4 * MIB),
        ]

    def test_standard_and_huge_page_controls_use_shared_acceptance_logic(self):
        for page_mode, control_events in (("standard pages", 1024),
                                          ("2 MiB huge pages", 2)):
            with self.subTest(page_mode=page_mode):
                self.assertEqual(_evaluate_memory_points(self._valid_points(control_events), 4096), [])

    def test_transient_huge_page_peak_passes_hwm_but_reports_missing_resident_signal(self):
        points = self._valid_points(2)
        points[1]["linear_control"]["median_anonymous_rss_growth_bytes"] = 0
        failures = _evaluate_memory_points(points, 4096)
        self.assertTrue(any(failure.startswith("anonymous control") for failure in failures))
        self.assertFalse(any(failure.startswith("VmHWM control") for failure in failures))
        self.assertFalse(any(failure.startswith("minflt control") for failure in failures))

    def test_shared_acceptance_logic_rejects_width_rss_regression(self):
        points = self._valid_points(2)
        points[1]["width"]["median_anonymous_rss_growth_bytes"] = 2 * MIB
        failures = _evaluate_memory_points(points, 4096)
        self.assertTrue(any(failure.startswith("width anonymous RSS") for failure in failures))

    def test_noisy_control_samples_raise_the_bound_and_detect_insensitive_hwm(self):
        noisy = self._valid_points(1024)
        noisy[1]["input_only"]["peak_rss_sample_spread_bytes"] = MIB // 4
        noisy[1]["linear_control"]["peak_rss_sample_spread_bytes"] = MIB // 4
        noisy[1]["input_only"]["anonymous_sample_spread_bytes"] = 32 * 1024
        noisy[1]["linear_control"]["anonymous_sample_spread_bytes"] = 32 * 1024
        self.assertEqual(_evaluate_memory_points(noisy, 4096), [])

        obscured = self._valid_points(1024)
        obscured[1]["linear_control"]["peak_rss_sample_spread_bytes"] = 4 * MIB
        failures = _evaluate_memory_points(obscured, 4096)
        self.assertTrue(any(failure.startswith("VmHWM control") for failure in failures))

    def test_fault_positive_control_respects_one_event_noise_threshold(self):
        points = self._valid_points(2)
        points[1]["linear_control"]["minor_fault_sample_spread_events"] = 1
        failures = _evaluate_memory_points(points, 4096)
        self.assertTrue(any(failure.startswith("minflt control 2<=2 events") for failure in failures))

    def test_fault_positive_control_exceeds_host_sample_noise(self):
        noisy = self._valid_points(3)
        noisy[1]["input_only"]["median_minor_fault_growth_events"] = 1
        noisy[1]["input_only"]["minor_fault_sample_spread_events"] = 3
        failures = _evaluate_memory_points(noisy, 4096)
        self.assertTrue(any(failure.startswith("minflt control 2<=4 events") for failure in failures))

        sensitive = self._valid_points(8)
        sensitive[1]["input_only"]["median_minor_fault_growth_events"] = 1
        sensitive[1]["input_only"]["minor_fault_sample_spread_events"] = 3
        failures = _evaluate_memory_points(sensitive, 4096)
        self.assertFalse(any(failure.startswith("minflt control") for failure in failures))

    def test_failure_summary_is_bounded_and_points_to_artifact(self):
        failures = ["ascii width anonymous RSS " + "x" * 500 for _ in range(40)]
        message = _memory_failure_message(failures, "/tmp/private-build/test-results/width-rss.json")
        self.assertLessEqual(len(message), MAX_MEMORY_FAILURE_MESSAGE_CHARS)
        self.assertIn("and 32 more", message)
        self.assertIn("width-rss.json", message)


if __name__ == "__main__":
    unittest.main()
