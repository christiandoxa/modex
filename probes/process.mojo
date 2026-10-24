from std.collections import List, Span
from std.os import Pipe, Process
from std.testing import assert_equal, assert_true


def main() raises:
    var pipe = Pipe()
    pipe.write_bytes("pipe".as_bytes())
    var buffer = List[UInt8](length=4, fill=0)
    assert_equal(pipe.read_bytes(Span(buffer)), 4)
    assert_equal(buffer[0], UInt8(112))
    var child = Process.run("/usr/bin/true", List[String]())
    var status = child.wait()
    assert_true(status.exit_code)
    assert_equal(status.exit_code.value(), 0)
    var sleeping = Process.run("/usr/bin/sleep", ["30"])
    assert_true(sleeping.kill())
    var killed = sleeping.wait()
    assert_true(killed.term_signal)
    assert_equal(killed.term_signal.value(), 9)
    print("pipe; direct argv spawn; exit status; direct-child signal/wait: PASS")
