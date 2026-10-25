"""Synthetic native child for startup-only redirected spawn checks."""

from std.collections import List, Span
from std.io import RawFileDescriptor
from std.os import getenv
from std.sys import argv


def main() raises:
    var args = argv()
    if len(args) != 2 or (args[1] != "echo" and args[1] != "echo-with-stderr"):
        raise Error("synthetic stdio child requires echo mode")
    if getenv("MODEX_STDIO_MARKER", "") != "synthetic" or getenv("MODEX_PARENT_SENTINEL", ""):
        raise Error("redirected child environment was not isolated")
    var input = RawFileDescriptor(0)
    var output = RawFileDescriptor(1)
    if args[1] == "echo-with-stderr":
        var error_output = RawFileDescriptor(2)
        error_output.write_bytes("synthetic-child-stderr\n".as_bytes())
    var buffer = List[UInt8](length=4096, fill=0)
    while True:
        var count = input.read_bytes(Span(buffer))
        if count == 0:
            break
        output.write_bytes(Span(buffer)[0:count])
