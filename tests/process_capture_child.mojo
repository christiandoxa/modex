"""Synthetic native child for simultaneous bounded stdout/stderr capture."""

from std.collections import List, Span
from std.io import RawFileDescriptor
from std.os import getenv
from std.sys import argv, exit
from std.time import sleep


def main() raises:
    var arguments = argv()
    var input = RawFileDescriptor(0)
    var bytes = List[UInt8](length=1, fill=0)
    if len(arguments) != 2 or input.read_bytes(Span(bytes)) != 0:
        raise Error("capture child requires a mode and closed stdin")
    if getenv("MODEX_CAPTURE_MARKER", "") != "synthetic" or getenv("MODEX_CAPTURE_EXCLUDED", ""):
        raise Error("capture child environment is not isolated")
    if arguments[1] == "hold":
        sleep(30.0)
        return
    var output = RawFileDescriptor(1)
    var error = RawFileDescriptor(2)
    if arguments[1] == "large":
        output.write_bytes((String("x") * 1048577).as_bytes())
        return
    output.write_bytes((String("o") * 100000).as_bytes())
    error.write_bytes((String("e") * 100000).as_bytes())
    if arguments[1] == "exit-seven":
        exit(7)
