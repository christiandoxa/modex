"""Verify real pipe redirection, restoration, explicit env, and spawn failures."""

from std.collections import List, Span
from std.os import getenv, setenv, unsetenv
from std.os.process import Pipe
from std.sys import argv
from std.sys._libc import fcntl, FcntlCommands
from std.testing import assert_equal, assert_true

from modex.process_spawn import spawn_with_env_stdio, wait_or_kill


def main() raises:
    var args = argv()
    assert_equal(len(args), 2)
    assert_true(setenv("MODEX_PARENT_SENTINEL", "parent-only"))
    var original_input_flags = fcntl(0, FcntlCommands.F_GETFD, 0)
    var original_output_flags = fcntl(1, FcntlCommands.F_GETFD, 0)
    var original_error_flags = fcntl(2, FcntlCommands.F_GETFD, 0)
    var input = Pipe()
    var output = Pipe()
    var child = spawn_with_env_stdio(String(args[1]), [String("echo")], [String("MODEX_STDIO_MARKER=synthetic")], input.fd_in.value().value, output.fd_out.value().value)
    input.set_output_only()
    output.set_input_only()
    assert_equal(fcntl(0, FcntlCommands.F_GETFD, 0), original_input_flags)
    assert_equal(fcntl(1, FcntlCommands.F_GETFD, 0), original_output_flags)
    var message = String("native redirected stdin/stdout: 雪とé\n")
    input.write_bytes(message.as_bytes())
    input.set_input_only()
    var bytes = List[UInt8](length=4096, fill=0)
    var count = output.read_bytes(Span(bytes))
    assert_equal(String(from_utf8=Span(bytes)[0:count]), message)
    assert_equal(output.read_bytes(Span(bytes)), 0)
    var result = wait_or_kill(child, 1000)
    assert_true(not result.timed_out)
    assert_equal(result.status.exit_code.value(), 0)
    assert_equal(getenv("MODEX_PARENT_SENTINEL", ""), "parent-only")

    var error_input = Pipe()
    var error_output = Pipe()
    var diagnostics = Pipe()
    var diagnostic_child = spawn_with_env_stdio(String(args[1]), [String("echo-with-stderr")], [String("MODEX_STDIO_MARKER=synthetic")], error_input.fd_in.value().value, error_output.fd_out.value().value, diagnostics.fd_out.value().value)
    error_input.set_output_only()
    error_input.set_input_only()
    error_output.set_input_only()
    diagnostics.set_input_only()
    var diagnostic_result = wait_or_kill(diagnostic_child, 1000)
    assert_equal(diagnostic_result.status.exit_code.value(), 0)
    count = diagnostics.read_bytes(Span(bytes))
    assert_equal(String(from_utf8=Span(bytes)[0:count]), "synthetic-child-stderr\n")
    assert_equal(diagnostics.read_bytes(Span(bytes)), 0)
    assert_equal(fcntl(2, FcntlCommands.F_GETFD, 0), original_error_flags)

    var failed_input = Pipe()
    var failed_output = Pipe()
    var rejected = False
    try:
        var absent = spawn_with_env_stdio("/modex/no-such-child", List[String](), List[String](), failed_input.fd_in.value().value, failed_output.fd_out.value().value)
    except:
        rejected = True
    assert_true(rejected)
    assert_equal(fcntl(0, FcntlCommands.F_GETFD, 0), original_input_flags)
    assert_equal(fcntl(1, FcntlCommands.F_GETFD, 0), original_output_flags)

    rejected = False
    try:
        var invalid = spawn_with_env_stdio(String(args[1]), [String("bad\0argument")], List[String](), failed_input.fd_in.value().value, failed_output.fd_out.value().value)
    except:
        rejected = True
    assert_true(rejected)
    assert_equal(fcntl(0, FcntlCommands.F_GETFD, 0), original_input_flags)
    assert_equal(fcntl(1, FcntlCommands.F_GETFD, 0), original_output_flags)

    rejected = False
    try:
        var invalid = spawn_with_env_stdio(String(args[1]), List[String](), List[String](), -1, failed_output.fd_out.value().value)
    except:
        rejected = True
    assert_true(rejected)
    assert_true(unsetenv("MODEX_PARENT_SENTINEL"))
    print("native redirected spawn, EOF, environment, and stdio restoration checks: PASS")

