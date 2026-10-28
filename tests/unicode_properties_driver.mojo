"""Test-only scalar census driver for Unicode property parity."""

from std.collections import List, Span
from std.io import RawFileDescriptor
from std.sys import argv

from modex.unicode_properties import is_alphanumeric, is_cased, is_case_ignorable


def main():
    var output = List[UInt8](length=0x110000, fill=0)
    var case_properties = len(argv()) > 1 and argv()[1] == "--case"
    for code in range(0x110000):
        if 0xD800 <= code <= 0xDFFF:
            output[code] = 255
        elif case_properties:
            output[code] = UInt8(is_cased(code)) + 2 * UInt8(is_case_ignorable(code))
        else:
            output[code] = UInt8(is_alphanumeric(code))
    var stdout = RawFileDescriptor(1)
    stdout.write_bytes(Span(output))
