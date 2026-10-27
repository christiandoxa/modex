from std.collections.string import Codepoint, String
from std.sys import argv

from modex.unicode_width import text_width


def _report_width(value: String, measure: Bool, linear_control: Bool, count: Int, hold: Bool) raises:
    var result = value.byte_length()
    if measure:
        result = text_width(value)
    if linear_control:
        var auxiliary = String()
        auxiliary.reserve_bytes(count * 4)
        for _ in range(count * 4):
            auxiliary.append(Codepoint.ord("A"))
        print(result)
        print(auxiliary.byte_length())
        if hold:
            _ = input()
        return
    print(result)
    if hold:
        _ = input()


def main() raises:
    var args = argv()
    if len(args) < 3 or len(args) > 5:
        raise Error("usage: width_memory_driver MODE COUNT [input-only|linear-control] [hold]")
    var mode = args[1]
    var count = Int(args[2])
    var operation = "width"
    if len(args) == 4:
        if args[3] != "hold":
            operation = args[3]
        if operation != "width" and operation != "input-only" and operation != "linear-control":
            raise Error("unknown width memory operation: " + args[3])
    if len(args) == 5:
        operation = args[3]
        if operation != "width" and operation != "input-only" and operation != "linear-control":
            raise Error("unknown width memory operation: " + args[3])
        if args[4] != "hold":
            raise Error("unknown width memory option: " + args[4])
    if count < 0:
        raise Error("COUNT must be non-negative")
    var measure = operation != "input-only"
    var linear_control = operation == "linear-control"
    var hold = (len(args) == 4 and args[3] == "hold") or len(args) == 5

    var value = String()
    if mode == "ascii":
        value.reserve_bytes(count)
        for _ in range(count):
            value.append(Codepoint.ord("A"))
        _report_width(value, measure, linear_control, count, hold)
        return

    if mode == "mixed":
        var unit = "A界é🙂"
        value.reserve_bytes(count * unit.byte_length())
        for _ in range(count):
            for character in unit.codepoints():
                value.append(character)
        _report_width(value, measure, linear_control, count, hold)
        return

    if mode == "tifinagh":
        value.reserve_bytes(3 + count * 6)
        value.append(Codepoint.ord("ⴱ"))
        for _ in range(count):
            value.append(Codepoint.ord("\u200d"))
            value.append(Codepoint.ord("ⴱ"))
        _report_width(value, measure, linear_control, count, hold)
        return

    if mode == "kirat":
        value.reserve_bytes(count * 4)
        var vowel = Codepoint(unsafe_unchecked_codepoint=UInt32(0x16D69))
        for _ in range(count):
            value.append(vowel)
        _report_width(value, measure, linear_control, count, hold)
        return

    if mode == "emoji-tag":
        value.reserve_bytes(8 + count * 4)
        value.append(Codepoint(unsafe_unchecked_codepoint=UInt32(0x1F3F4)))
        var tag = Codepoint(unsafe_unchecked_codepoint=UInt32(0xE0061))
        for _ in range(count):
            value.append(tag)
        value.append(Codepoint(unsafe_unchecked_codepoint=UInt32(0xE007F)))
        _report_width(value, measure, linear_control, count, hold)
        return

    raise Error("unknown mode: " + mode)
