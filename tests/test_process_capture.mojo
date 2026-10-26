"""Native resource, channel, environment and reap checks for process capture."""

from std.collections import List, Span
from std.os import setenv, unsetenv
from std.sys import argv
from std.testing import assert_equal, assert_true
from std.time import perf_counter

from modex.process_spawn import capture_with_env, inherited_environment


def main() raises:
    var arguments = argv()
    assert_equal(len(arguments), 2)
    assert_true(setenv("MODEX_CAPTURE_MARKER", "synthetic"))
    assert_true(setenv("MODEX_CAPTURE_EXCLUDED", "parent-only"))
    var environment = inherited_environment([String("MODEX_CAPTURE_EXCLUDED")])
    assert_true("MODEX_CAPTURE_MARKER=synthetic" in environment)
    assert_true("MODEX_CAPTURE_EXCLUDED=parent-only" not in environment)
    var child = String(arguments[1])
    var result = capture_with_env(child, [String("exit-seven")], environment, "synthetic probe", 1000)
    assert_equal(result.status.exit_code.value(), 7)
    assert_equal(String(from_utf8=Span(result.stdout)), String("o") * 100000)
    assert_equal(String(from_utf8=Span(result.stderr)), String("e") * 100000)
    var failed = False
    try:
        var ignored = capture_with_env(child, [String("large")], environment, "synthetic probe", 1000, 1024)
    except error:
        assert_equal(String(error), "synthetic probe output exceeded the limit")
        failed = True
    assert_true(failed)
    failed = False
    var started = perf_counter()
    try:
        var ignored = capture_with_env(child, [String("hold")], environment, "synthetic probe", 40)
    except error:
        assert_equal(String(error), "synthetic probe timed out")
        failed = True
    assert_true(failed and perf_counter() - started < 1.0)
    assert_true(unsetenv("MODEX_CAPTURE_MARKER"))
    assert_true(unsetenv("MODEX_CAPTURE_EXCLUDED"))
    print("bounded simultaneous process capture, explicit environment and timeout checks: PASS")
