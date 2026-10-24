from std.collections import List, Span
from std.os import mkdir, remove, rmdir
from std.sys import argv
from std.testing import assert_equal, assert_true

from modex.log_follow import FOLLOW_MAX_PENDING_BYTES, FollowedLog, collect_new_followed_lines


def write(path: String, content: String) raises:
    with open(path, "w") as file:
        file.write(content)


def append(path: String, content: String) raises:
    with open(path, "a") as file:
        file.write(content)


def append_bytes(path: String, bytes: List[UInt8]) raises:
    with open(path, "a") as file:
        file.write_bytes(bytes)


def main() raises:
    var args = argv()
    assert_equal(len(args), 2)
    var root = String(args[1])
    mkdir(root, 0o700)
    var path = root + "/runtime.log"
    write(path, "history\n")
    var state = FollowedLog(path)
    assert_equal(len(collect_new_followed_lines(path, state)), 0)
    append(path, "one\r\ntwo\npart")
    assert_equal(collect_new_followed_lines(path, state), ["one", "two"])
    append(path, "ial\n")
    assert_equal(collect_new_followed_lines(path, state), ["partial"])
    var utf8 = List[UInt8]()
    utf8.append(0xF0)
    utf8.append(0x9F)
    append_bytes(path, utf8^)
    assert_equal(len(collect_new_followed_lines(path, state)), 0)
    utf8 = List[UInt8]()
    utf8.append(0x8C)
    utf8.append(0x8B)
    utf8.append(10)
    append_bytes(path, utf8^)
    assert_equal(collect_new_followed_lines(path, state), ["🌋"])

    write(path, "old")
    write(path, "x\n")
    assert_equal(collect_new_followed_lines(path, state), ["x"])

    remove(path)
    assert_equal(len(collect_new_followed_lines(path, state)), 0)
    write(path, "resume\n")
    assert_equal(collect_new_followed_lines(path, state), ["sume"])
    remove(path)
    rmdir(root)

    var bounded_root = root + "-bounds"
    mkdir(bounded_root, 0o700)
    var large_path = bounded_root + "/partial.log"
    var large = List[UInt8]()
    for _ in range(FOLLOW_MAX_PENDING_BYTES + 1):
        large.append(97)
    with open(large_path, "w") as file:
        file.write_bytes(Span(large))
    var bounded_state = FollowedLog()
    assert_equal(len(collect_new_followed_lines(large_path, bounded_state)), 0)
    assert_equal(len(bounded_state.pending), FOLLOW_MAX_PENDING_BYTES)
    assert_equal(collect_new_followed_lines(large_path, bounded_state), ["[log] runtime_log_gap dropped=1 reason=oversized_partial_line"])
    assert_equal(len(bounded_state.pending), 0)
    remove(large_path)

    var blocker = bounded_root + "/regular-file"
    write(blocker, "x")
    var failed = False
    try:
        _ = collect_new_followed_lines(blocker + "/child.log", bounded_state)
    except error:
        failed = String(error).startswith("failed to inspect")
    assert_true(failed)
    remove(blocker)

    var malformed_path = bounded_root + "/malformed.log"
    write(malformed_path, "\n")
    var malformed_state = FollowedLog()
    for _ in range(FOLLOW_MAX_PENDING_BYTES):
        malformed_state.pending.append(255)
    assert_equal(collect_new_followed_lines(malformed_path, malformed_state), ["[log] runtime_log_gap dropped=1 reason=oversized_line"])
    remove(malformed_path)
    rmdir(bounded_root)
    print("native incremental log follow: PASS")
