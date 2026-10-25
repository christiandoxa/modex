from std.collections import List, Span
from std.io import RawFileDescriptor
from std.sys import argv
from modex.loopback_http import LoopbackHTTPStream


def _drive(var stream: LoopbackHTTPStream, stop_after_first: Bool, drop_after_first: Bool) raises:
    var output = RawFileDescriptor(1)
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
    if len(args) < 4 or len(args) > 5:
        raise Error("usage: driver ADDRESS PATH BODY [mode]")
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
    if len(args) == 5:
        if args[4] == "idle-short":
            idle_timeout = 100
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
        else:
            raise Error("invalid stream test mode")
    var stream = LoopbackHTTPStream(args[1], args[2], headers, body, connect_timeout, request_timeout, idle_timeout, 1048576)
    if move_stream:
        var moved = stream^
        _drive(moved^, stop_after_first, drop_after_first)
    else:
        _drive(stream^, stop_after_first, drop_after_first)
