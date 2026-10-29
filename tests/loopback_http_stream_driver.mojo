from std.collections import List, Span
from std.io import RawFileDescriptor
from std.net._sys.inet import in_addr
from std.net._sys.unix import connect, sockaddr, sockaddr_in
from std.sys import argv
from std.sys import size_of
from std.sys._libc import close
from std.sys._libc_errno import ErrNo, get_errno
from std.time import perf_counter
from modex.loopback_http import HTTP_HEADER_LIMIT, LoopbackHTTPStream, _finish_loopback_connect, _network32, _number, _open_loopback_socket, _port_bytes


def _wait_for_cancelled_connect(address: String, cancel_fd: Int32) raises:
    var parts = address.split(":")
    if len(parts) != 2 or String(parts[0]) != "127.0.0.1":
        raise Error("connect cancellation probe requires IPv4 loopback")
    var port = _number(parts[1])
    var fd = _open_loopback_socket(False)
    var peer = sockaddr_in(port=_port_bytes(port), addr=in_addr(s_addr=_network32(UInt32(0x7f000001))))
    var result = connect(fd, Pointer(to=peer).unsafe_bitcast[sockaddr](), UInt32(size_of[sockaddr_in]()))
    var e = get_errno()
    if result >= 0 or (e != ErrNo.EINPROGRESS and e != ErrNo.EINTR and e != ErrNo.EAGAIN):
        _ = close(fd)
        raise Error("connect cancellation probe did not remain pending")
    var output = RawFileDescriptor(1)
    output.write_bytes("CONNECT_PENDING\n".as_bytes())
    try:
        _finish_loopback_connect(fd, result, perf_counter() + 1.0, -1, cancel_fd)
    except error:
        _ = close(fd)
        if String(error) != "loopback HTTP request cancelled":
            raise
        output.write_bytes("CANCELLED loopback HTTP request cancelled\n".as_bytes())
        return
    _ = close(fd)
    raise Error("connect cancellation probe completed without cancellation")


def _drive(var stream: LoopbackHTTPStream, stop_after_first: Bool, drop_after_first: Bool, downstream_fd: Int32 = -1) raises:
    var output = RawFileDescriptor(1)
    var downstream_output = RawFileDescriptor(downstream_fd)
    var first = True
    while not stream.done:
        var chunk = stream.read_chunk()
        if first:
            print("S " + String(stream.status))
            for header in stream.headers:
                print("H " + header[0] + ": " + header[1])
            print()
            first = False
        if len(chunk) > 0:
            if downstream_fd >= 0:
                downstream_output.write_bytes(Span(chunk))
            output.write_bytes(Span(chunk))
            if stop_after_first:
                stream.close()
            if stop_after_first or drop_after_first:
                break
    if first:
        print("S " + String(stream.status))
        for header in stream.headers:
            print("H " + header[0] + ": " + header[1])
        print()


def main() raises:
    var args = argv()
    if len(args) < 4 or len(args) > 6:
        raise Error("usage: driver ADDRESS PATH BODY [mode [DOWNSTREAM_FD]]")
    var body = List[UInt8]()
    for b in args[3].as_bytes():
        body.append(b)
    var headers = List[Tuple[String, String]]()
    headers.append(("X-Test", "one"))
    headers.append(("X-Test", "two"))
    var connect_timeout: UInt64 = 1000
    var request_timeout: UInt64 = 1000
    var idle_timeout: UInt64 = 250
    var stop_after_first = False
    var drop_after_first = False
    var move_stream = False
    var watch_downstream = False
    var watch_cancellation = False
    var allow_unbounded_body = False
    var downstream_fd: Int32 = -1
    var cancel_fd: Int32 = -1
    if len(args) >= 5:
        if args[4] == "idle-short":
            idle_timeout = 100
        elif args[4] == "unbounded":
            allow_unbounded_body = True
        elif args[4] == "request-short":
            request_timeout = 100
        elif args[4] == "close":
            stop_after_first = True
        elif args[4] == "drop":
            drop_after_first = True
        elif args[4] == "move":
            move_stream = True
        elif args[4] == "header-compat":
            headers.append(("X.Foo", "a\tb"))
        elif args[4] == "header-large":
            headers.append(("X-Large", String("x") * 70000))
        elif args[4] == "header-inject":
            headers.append(("X-Evil\r\nInjected", "yes"))
        elif args[4] == "header-value":
            headers.append(("X-Evil", "yes\r\nInjected: no"))
        elif args[4] == "header-host":
            headers.append(("hOsT", "127.0.0.1"))
        elif args[4] == "header-length":
            headers.append(("Content-Length", "1"))
        elif args[4] == "header-transfer":
            headers.append(("Transfer-Encoding", "chunked"))
        elif args[4] == "header-connection":
            headers.append(("Connection", "keep-alive"))
        elif args[4] == "watch":
            if len(args) != 6:
                raise Error("watch mode requires a downstream descriptor")
            watch_downstream = True
            downstream_fd = Int32(Int(args[5]))
        elif args[4] == "cancel-read" or args[4] == "cancel-write" or args[4] == "cancel-connect":
            if len(args) != 6:
                raise Error("cancellation mode requires a cancellation descriptor")
            watch_cancellation = True
            cancel_fd = Int32(Int(args[5]))
            if args[4] == "cancel-write":
                body = List[UInt8](length=16 * 1024 * 1024, fill=120)
        elif args[4] == "connect-errno":
            if len(args) != 6:
                raise Error("connect-errno requires a downstream descriptor")
            downstream_fd = Int32(Int(args[5]))
            _ = close(-1)
            try:
                _finish_loopback_connect(-1, -1, perf_counter() + 0.1, downstream_fd)
            except error:
                if String(error) != "loopback HTTP connect failed":
                    raise
                print("CONNECT_ERRNO_PASS")
                return
            raise Error("invalid connect unexpectedly succeeded")
        else:
            raise Error("invalid stream test mode")
        if len(args) == 6 and not watch_downstream and not watch_cancellation:
            raise Error("descriptor is only valid in watch or cancellation mode")
    if move_stream:
        var stream = LoopbackHTTPStream(args[1], args[2], headers, body, connect_timeout, request_timeout, idle_timeout, 1048576, downstream_fd, allow_unbounded_body)
        var moved = stream^
        _drive(moved^, stop_after_first, drop_after_first, downstream_fd)
    elif watch_cancellation and args[4] == "cancel-connect":
        _wait_for_cancelled_connect(args[1], cancel_fd)
    elif watch_downstream or watch_cancellation:
        try:
            var stream = LoopbackHTTPStream(args[1], args[2], headers, body, connect_timeout, request_timeout, idle_timeout, 1048576, downstream_fd, allow_unbounded_body, "POST", HTTP_HEADER_LIMIT, HTTP_HEADER_LIMIT, cancel_fd)
            _drive(stream^, stop_after_first, drop_after_first, downstream_fd)
        except error:
            print("CANCELLED " + String(error))
    else:
        var stream = LoopbackHTTPStream(args[1], args[2], headers, body, connect_timeout, request_timeout, idle_timeout, 1048576, downstream_fd, allow_unbounded_body)
        _drive(stream^, stop_after_first, drop_after_first, downstream_fd)
