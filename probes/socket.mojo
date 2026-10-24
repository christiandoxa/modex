from std.collections import Array, List
from std.net._sys.unix import AF_UNIX, SOCK_STREAM, recv, send, socketpair
from std.sys._libc import close
from std.testing import assert_equal


def main() raises:
    # The official internal API is probed here; its stability is not assumed.
    var descriptors = Array[Int32, 2](fill=-1)
    assert_equal(socketpair(AF_UNIX, SOCK_STREAM, 0, Pointer(to=descriptors)), 0)
    var message: List[UInt8] = [1, 2, 3, 4]
    var received = List[UInt8](length=4, fill=0)
    # Both buffers and descriptors stay alive through these synchronous calls.
    var sent = send(descriptors[0], message.unsafe_ptr(), UInt(len(message)), 0)
    var read = recv(descriptors[1], received.unsafe_ptr(), UInt(len(received)), 0)
    var closed_first = close(descriptors[0])
    var closed_second = close(descriptors[1])
    assert_equal(sent, 4)
    assert_equal(read, 4)
    assert_equal(received[3], UInt8(4))
    assert_equal(closed_first, 0)
    assert_equal(closed_second, 0)
    print("official internal stdlib socketpair/send/recv/close: PASS")
