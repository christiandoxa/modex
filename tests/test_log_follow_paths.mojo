"""Native checks for bounded runtime/session follower path selection."""

from std.collections import List
from std.os import listdir, setenv
from std.testing import assert_equal, assert_true
from std.sys import argv

from modex.log_follow_paths import bounded_follow_paths, recent_session_log_paths


def files_in(directory: String) raises -> List[String]:
    var result = List[String]()
    for name in listdir(directory):
        if name.endswith(".mojo") or name.endswith(".py"):
            result.append(directory + "/" + name)
    return result^


def main() raises:
    var paths = files_in("tests")
    assert_true(len(paths) >= 32)
    var selected = bounded_follow_paths(paths, paths)
    assert_equal(len(selected[0]), 16)
    assert_equal(len(selected[1]), 16)
    for path in selected[0]:
        assert_true(path in paths)
    for path in selected[1]:
        assert_true(path in paths)

    var one_session = List[String]()
    one_session.append(paths[0])
    var spare = bounded_follow_paths(paths, one_session)
    assert_equal(len(spare[0]), 31)
    assert_equal(len(spare[1]), 1)

    var duplicate_runtime = List[String](length=40, fill=paths[0])
    var duplicate_sessions = List[String]()
    duplicate_sessions.append(paths[0])
    duplicate_sessions.append(paths[1])
    var duplicates = bounded_follow_paths(duplicate_runtime, duplicate_sessions)
    assert_equal(duplicates[0], duplicate_runtime)
    assert_equal(duplicates[1], duplicate_sessions)

    var small_runtime = List[String]()
    small_runtime.append(paths[0])
    small_runtime.append(paths[1])
    var small_sessions = List[String]()
    small_sessions.append(paths[0])
    var unchanged = bounded_follow_paths(small_runtime, small_sessions)
    assert_equal(unchanged[0], small_runtime)
    assert_equal(unchanged[1], small_sessions)

    assert_true(len(argv()) > 1, "pass a synthetic fixture root")
    assert_true(setenv("HOME", String(argv()[1]) + "/home"))
    var absent_shared = String(argv()[1]) + "/absent-shared"
    assert_true(setenv("PRODEX_SHARED_CODEX_HOME", absent_shared))
    var recent = recent_session_log_paths(String(argv()[1]))
    assert_equal(len(recent), 0)
    print("Log follower path selection checks: PASS")
