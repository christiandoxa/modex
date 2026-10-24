"""Test-only scalar census driver for Unicode property parity."""

from std.collections import List, Span
from std.io import RawFileDescriptor

from modex.unicode_properties import is_alphanumeric


def main():
    var output = List[UInt8](length=0x110000, fill=0)
    for code in range(0x110000):
        if 0xD800 <= code <= 0xDFFF:
            output[code] = 255
        else:
            output[code] = UInt8(is_alphanumeric(code))
    var stdout = RawFileDescriptor(1)
    stdout.write_bytes(Span(output))
