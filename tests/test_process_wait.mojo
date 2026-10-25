"""Direct-child timeout, termination, and exit-status checks."""

from std.collections import List
from std.sys import argv
from std.testing import assert_equal, assert_true
from std.time import perf_counter
from modex.process_spawn import spawn_with_env, wait_or_kill


def child_args(mode: String) -> List[String]:
    var args = List[String]()
    args.append(mode)
    return args^


def main() raises:
    var args = argv()
    assert_true(len(args) == 2, "pass compiled synthetic child path")
    var child_path = String(args[1])

    var immediate = spawn_with_env(child_path, child_args("exit-seven"), List[String]())
    var immediate_result = wait_or_kill(immediate, 1000)
    assert_true(not immediate_result.timed_out)
    assert_true(immediate_result.status.exit_code)
    assert_equal(immediate_result.status.exit_code.value(), 7)

    var delayed = spawn_with_env(child_path, child_args("delayed-exit"), List[String]())
    var delayed_result = wait_or_kill(delayed, 1000)
    assert_true(not delayed_result.timed_out)
    assert_true(delayed_result.status.exit_code)
    assert_equal(delayed_result.status.exit_code.value(), 0)

    var held = spawn_with_env(child_path, child_args("hold-open"), List[String]())
    var started = perf_counter()
    var timeout_result = wait_or_kill(held, 40)
    assert_true(perf_counter() - started < 1.0, "synthetic sleeper should be terminated promptly")
    assert_true(timeout_result.timed_out)
    assert_true(timeout_result.status.term_signal)
    assert_equal(timeout_result.status.term_signal.value(), 9)
    var reaped_status = held.poll()
    assert_true(reaped_status.term_signal)
    assert_equal(reaped_status.term_signal.value(), 9)
    var cached_result = wait_or_kill(held, 1000)
    assert_true(not cached_result.timed_out)
    assert_true(cached_result.status.term_signal)
    assert_equal(cached_result.status.term_signal.value(), 9)

    var immediate_timeout_rejected = False
    try:
        var ignored = wait_or_kill(immediate, 0)
    except:
        immediate_timeout_rejected = True
    assert_true(immediate_timeout_rejected)
    print("direct-child polling, timeout termination, and cached reap checks: PASS")
