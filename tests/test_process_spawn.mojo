"""Native child-process checks for argv and explicit environment handling."""

from std.collections import List
from std.testing import assert_true
from std.sys import argv
from std.os import getenv, setenv, unsetenv
from modex.process_spawn import spawn_with_env


def main() raises:
    assert_true(len(argv()) > 1, "pass compiled synthetic child path")
    var child_path = String(argv()[1])
    assert_true(setenv("MODEX_PARENT_SENTINEL", "parent-only"))

    var args = List[String]()
    args.append("arg-one")
    args.append("arg two")
    args.append("")
    args.append("雪とé")
    args.append("long-" + String("x" * 8192))
    var env = List[String]()
    env.append("MODEX_CHILD_MARKER=synthetic")
    env.append("MODEX_LONG_VALUE=" + String("v" * 8192))
    var before = getenv("MODEX_CHILD_MARKER", "absent")
    var child = spawn_with_env(child_path, args, env)
    var status = child.wait()
    assert_true(status.exit_code and status.exit_code.value() == 0)
    assert_true(getenv("MODEX_CHILD_MARKER", "absent") == before)
    assert_true(getenv("MODEX_PARENT_SENTINEL") == "parent-only")

    var nonzero_args = List[String]()
    nonzero_args.append("exit-nonzero")
    var nonzero = spawn_with_env(child_path, nonzero_args, List[String]())
    var nonzero_status = nonzero.wait()
    assert_true(nonzero_status.exit_code and nonzero_status.exit_code.value() == 7)

    var bad_args = List[String]()
    bad_args.append("bad\0arg")
    var rejected_argument = False
    try:
        var ignored = spawn_with_env(child_path, bad_args, List[String]())
    except:
        rejected_argument = True
    assert_true(rejected_argument)

    var bad_env = List[String]()
    bad_env.append("NO_EQUALS")
    var rejected_environment = False
    try:
        var ignored = spawn_with_env(child_path, List[String](), bad_env)
    except:
        rejected_environment = True
    assert_true(rejected_environment)

    var nul_env = List[String]()
    nul_env.append("BAD=value\0tail")
    var rejected_nul_environment = False
    try:
        var ignored = spawn_with_env(child_path, List[String](), nul_env)
    except:
        rejected_nul_environment = True
    assert_true(rejected_nul_environment)

    var missing = False
    try:
        var absent = spawn_with_env("/modex/no-such-executable", List[String](), List[String]())
        var absent_status = absent.wait()
        missing = absent_status.exit_code and absent_status.exit_code.value() == 127
    except:
        missing = True
    assert_true(missing)
    var relative_rejected = False
    try:
        var ignored = spawn_with_env("relative-child", List[String](), [String("PATH=/untrusted")])
    except:
        relative_rejected = True
    assert_true(relative_rejected)
    assert_true(unsetenv("MODEX_PARENT_SENTINEL"))
    print("explicit environment spawn checks: PASS")
