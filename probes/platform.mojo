from std.atomic import Atomic
from std.collections import List
from std.os import getenv, isatty, lstat, mkdir, remove, rmdir, stat, symlink
from std.pathlib import Path
from std.sys import argv
from std.testing import assert_equal, assert_true
from std.time import perf_counter_ns, sleep


def main() raises:
    var args = argv()
    assert_equal(len(args), 2)
    var root = String(args[1])
    mkdir(root, 0o700)
    assert_equal(stat(root).st_mode & 0o777, 0o700)
    var file_path = root + "/data"
    var link_path = root + "/link"
    with open(file_path, "w") as file:
        file.write("Mojo filesystem probe\n")
    assert_equal(Path(file_path).read_text(), "Mojo filesystem probe\n")
    symlink(file_path, link_path)
    assert_true((lstat(link_path).st_mode & 0o170000) == 0o120000)
    assert_equal(Path(link_path).read_text(), "Mojo filesystem probe\n")
    assert_equal(getenv("MODEX_PROBE_SENTINEL"), "isolated-probe")
    var started = perf_counter_ns()
    sleep(0.001)
    assert_true(perf_counter_ns() > started)
    var counter = Atomic[Int](0)
    _ = counter.fetch_add(1)
    assert_equal(counter.load(), 1)
    with open("/dev/urandom", "r") as random_source:
        assert_equal(len(random_source.read_bytes(32)), 32)
    print("filesystem read/write; directory permissions; symlink/lstat; environment; timer; atomic; OS random read: PASS")
    print("stdout is a terminal:", isatty(1))
    remove(link_path)
    remove(file_path)
    rmdir(root)
