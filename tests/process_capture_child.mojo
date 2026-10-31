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
    if arguments[1] == "split-valid":
        output.write_bytes((String("x") * 8191).as_bytes())
        var lead = List[UInt8]()
        lead.append(0xC2)
        output.write_bytes(Span(lead))
        sleep(0.02)
        var tail = List[UInt8]()
        tail.append(0xA2)
        output.write_bytes(Span(tail))
        output.write_bytes((String("x") * 8190).as_bytes())
        lead = List[UInt8]()
        lead.append(0xE2)
        output.write_bytes(Span(lead))
        sleep(0.02)
        tail = List[UInt8]()
        tail.append(0x82)
        tail.append(0xAC)
        output.write_bytes(Span(tail))
        output.write_bytes((String("x") * 8189).as_bytes())
        lead = List[UInt8]()
        lead.append(0xF0)
        output.write_bytes(Span(lead))
        sleep(0.02)
        tail = List[UInt8]()
        tail.append(0x90)
        output.write_bytes(Span(tail))
        sleep(0.02)
        tail = List[UInt8]()
        tail.append(0x80)
        output.write_bytes(Span(tail))
        sleep(0.02)
        tail = List[UInt8]()
        tail.append(0x80)
        output.write_bytes(Span(tail))
        output.write_bytes((String("x") * 8189).as_bytes())
        output.write_bytes((String("x") * 100000).as_bytes())
        return
    if arguments[1] == "invalid-tail":
        output.write_bytes((String("x") * 100000).as_bytes())
        var invalid = List[UInt8]()
        invalid.append(0xFF)
        output.write_bytes(Span(invalid))
        return
    if arguments[1] == "incomplete-tail":
        output.write_bytes((String("x") * 100000).as_bytes())
        var incomplete = List[UInt8]()
        incomplete.append(0xF0)
        output.write_bytes(Span(incomplete))
        return
    if arguments[1] == "hold-after-large":
        output.write_bytes((String("x") * 100000).as_bytes())
        sleep(30.0)
        return
    output.write_bytes((String("o") * 100000).as_bytes())
    error.write_bytes((String("e") * 100000).as_bytes())
    if arguments[1] == "exit-seven":
        exit(7)
