from std.collections import Span
from std.io import RawFileDescriptor
from std.sys import argv
from modex.loopback_http import loopback_get


def main() raises:
    var args = argv()
    if len(args) < 5 or len(args) > 7:
        raise Error("usage: driver ADDRESS PATH HEADER VALUE [zero|overflow] [repeat]")
    var cap = 4194304
    if len(args) >= 6:
        if args[5] == "zero":
            cap = 0
        elif args[5] == "overflow":
            cap = 9223372036854775807
        else:
            raise Error("invalid test body cap")
    var repeat = len(args) == 7
    var count = 100 if repeat else 1
    var output = RawFileDescriptor(1)
    for _ in range(count):
        if repeat:
            try:
                var result = loopback_get(args[1], args[2], args[3], args[4], 1000, 1000, cap)
                print(result[0])
                output.write_bytes(Span(result[1]))
            except:
                print("ERROR")
        else:
            var result = loopback_get(args[1], args[2], args[3], args[4], 1000, 1000, cap)
            print(result[0])
            output.write_bytes(Span(result[1]))
