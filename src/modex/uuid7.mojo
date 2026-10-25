"""RFC 9562 UUIDv7 generation from a millisecond timestamp and random bytes."""

from std.collections import ImmSpan, List
from std.time.time import _realtime_nanoseconds


def uuid7_from_parts(milliseconds: UInt64, random: ImmSpan[UInt8, _]) raises -> String:
    if milliseconds > 0xFFFFFFFFFFFF:
        raise Error("UUIDv7 timestamp exceeds 48 bits")
    if len(random) != 16:
        raise Error("UUIDv7 requires 16 random bytes")
    var bytes = List[UInt8]()
    for _ in range(16):
        bytes.append(0)
    for offset in range(6):
        bytes[5 - offset] = UInt8((milliseconds >> UInt64(offset * 8)) & UInt64(255))
    bytes[6] = UInt8(0x70 | (random[6] & 0x0F))
    bytes[7] = random[7]
    bytes[8] = UInt8(0x80 | (random[8] & 0x3F))
    for offset in range(9, 16):
        bytes[offset] = random[offset]
    var result = String()
    for offset in range(16):
        if offset == 4 or offset == 6 or offset == 8 or offset == 10:
            result += "-"
        result += _hex_byte(bytes[offset])
    return result


def new_uuid7() raises -> String:
    var nanoseconds = _realtime_nanoseconds()
    if nanoseconds < 0:
        raise Error("system clock returned a negative timestamp")
    var random_file = open("/dev/urandom", "r")
    var random = random_file.read_bytes(16)
    if len(random) != 16:
        raise Error("could not read 16 UUIDv7 random bytes")
    return uuid7_from_parts(UInt64(nanoseconds // 1_000_000), Span(random))


def _hex_byte(value: UInt8) -> String:
    return _hex_digit(Int(value >> 4)) + _hex_digit(Int(value & 15))


def _hex_digit(value: Int) -> String:
    if value < 10:
        return String(chr(48 + value))
    return String(chr(87 + value))
