"""Test-only scalar census and batched string-width requests."""

from std.collections import List, Span
from std.io import RawFileDescriptor
from std.sys import argv

from modex.json import JSON_STRING, JsonDocument
from modex.text import text_width
from modex.unicode_width import EMOJI_PRESENTATION, EMOJI_VARIANTS, MODIFIER_BASES, TEXT_VARIANTS, character_width, in_ranges, joining_transparent


def emit(bytes: List[UInt8]):
    try:
        var document = JsonDocument(String(from_utf8=Span(bytes)))
        ref node = document.nodes[document.root]
        if node.kind != JSON_STRING:
            raise Error("expected a string")
        print(text_width(node.text))
    except:
        print("ERROR")


def main() raises:
    if len(argv()) > 1:
        var widths = List[UInt8](length=0x110000, fill=255)
        for code in range(0x110000):
            if not 0xD800 <= code <= 0xDFFF:
                if argv()[1] == "--scalars":
                    widths[code] = UInt8(character_width(code))
                else:
                    widths[code] = UInt8(joining_transparent(code)) | (UInt8(in_ranges[EMOJI_PRESENTATION](code)) << 1) | (UInt8(in_ranges[EMOJI_VARIANTS](code)) << 2) | (UInt8(in_ranges[MODIFIER_BASES](code)) << 3) | (UInt8(in_ranges[TEXT_VARIANTS](code)) << 4)
        var output = RawFileDescriptor(1)
        output.write_bytes(Span(widths))
        return
    var input = RawFileDescriptor(0)
    var buffer = List[UInt8](length=8192, fill=0)
    var pending = List[UInt8]()
    while True:
        var size = input.read_bytes(Span(buffer))
        if size == 0:
            break
        for index in range(size):
            if buffer[index] == 10:
                emit(pending)
                pending.clear()
            else:
                pending.append(buffer[index])
    if pending:
        emit(pending)
