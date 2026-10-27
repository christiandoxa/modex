from std.collections.string import Codepoint, String
from std.sys import argv

from modex.unicode_width import text_width


def _report_width(value: String, measure: Bool) raises:
    print(text_width(value) if measure else value.byte_length())


def main() raises:
    var args = argv()
    if len(args) != 3 and len(args) != 4:
        raise Error("usage: width_memory_driver MODE COUNT [input-only]")
    var mode = args[1]
    var count = Int(args[2])
    var measure = len(args) == 3
    if len(args) == 4:
        if args[3] != "input-only":
            raise Error("unknown width memory operation: " + args[3])
        measure = False
    if count < 0:
        raise Error("COUNT must be non-negative")

    var value = String()
    if mode == "ascii":
        value.reserve_bytes(count)
        for _ in range(count):
            value.append(Codepoint.ord("A"))
        _report_width(value, measure)
        return

    if mode == "mixed":
        var unit = "A界é🙂"
        value.reserve_bytes(count * unit.byte_length())
        for _ in range(count):
            for character in unit.codepoints():
                value.append(character)
        _report_width(value, measure)
        return

    if mode == "tifinagh":
        value.reserve_bytes(3 + count * 6)
        value.append(Codepoint.ord("ⴱ"))
        for _ in range(count):
            value.append(Codepoint.ord("\u200d"))
            value.append(Codepoint.ord("ⴱ"))
        _report_width(value, measure)
        return

    if mode == "kirat":
        value.reserve_bytes(count * 4)
        var vowel = Codepoint(unsafe_unchecked_codepoint=UInt32(0x16D69))
        for _ in range(count):
            value.append(vowel)
        _report_width(value, measure)
        return

    if mode == "emoji-tag":
        value.reserve_bytes(8 + count * 4)
        value.append(Codepoint(unsafe_unchecked_codepoint=UInt32(0x1F3F4)))
        var tag = Codepoint(unsafe_unchecked_codepoint=UInt32(0xE0061))
        for _ in range(count):
            value.append(tag)
        value.append(Codepoint(unsafe_unchecked_codepoint=UInt32(0xE007F)))
        _report_width(value, measure)
        return

    raise Error("unknown mode: " + mode)
