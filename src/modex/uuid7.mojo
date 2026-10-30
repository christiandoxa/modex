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


def uuid7_suffix_u32(identifier: String) raises -> UInt64:
    if identifier.byte_length() != 36:
        raise Error("UUIDv7 string has invalid length")
    var value: UInt64 = 0
    for byte in String(identifier[byte=28:]).as_bytes():
        var code = Int(byte)
        var digit = -1
        if 48 <= code <= 57:
            digit = code - 48
        elif 65 <= code <= 70:
            digit = code - 55
        elif 97 <= code <= 102:
            digit = code - 87
        if digit < 0:
            raise Error("UUIDv7 string has invalid suffix")
        value = (value << UInt64(4)) | UInt64(digit)
    return value


def runtime_request_sequence_next(sequence: UInt64) -> UInt64:
    return UInt64(0) if sequence == UInt64.MAX else sequence + UInt64(1)


def runtime_request_sequence_take(sequence: UInt64) -> Tuple[UInt64, UInt64]:
    return (sequence, runtime_request_sequence_next(sequence))


def _uuid7_u64(identifier: String, start_hex: Int) raises -> UInt64:
    if identifier.byte_length() != 36:
        raise Error("UUIDv7 string has invalid length")
    var value = UInt64(0)
    var byte_index = 0
    var hex_index = 0
    for byte in identifier.as_bytes():
        var code = Int(byte)
        if byte_index == 8 or byte_index == 13 or byte_index == 18 or byte_index == 23:
            if code != 45:
                raise Error("UUIDv7 string has invalid format")
        else:
            var digit = -1
            if 48 <= code <= 57:
                digit = code - 48
            elif 65 <= code <= 70:
                digit = code - 55
            elif 97 <= code <= 102:
                digit = code - 87
            if digit < 0:
                raise Error("UUIDv7 string has invalid format")
            if start_hex <= hex_index < start_hex + 16:
                value = (value << UInt64(4)) | UInt64(digit)
            hex_index += 1
        byte_index += 1
    return value


def _rotate_left(value: UInt64, bits: Int) -> UInt64:
    return (value << UInt64(bits)) | (value >> UInt64(64 - bits))


def _siphash13_round(state: Tuple[UInt64, UInt64, UInt64, UInt64]) -> Tuple[UInt64, UInt64, UInt64, UInt64]:
    var (v0, v1, v2, v3) = state
    v0 += v1
    v2 += v3
    v1 = _rotate_left(v1, 13)
    v1 ^= v0
    v3 = _rotate_left(v3, 16)
    v3 ^= v2
    v0 = _rotate_left(v0, 32)
    v2 += v1
    v0 += v3
    v1 = _rotate_left(v1, 17)
    v1 ^= v2
    v3 = _rotate_left(v3, 21)
    v3 ^= v0
    v2 = _rotate_left(v2, 32)
    return (v0, v1, v2, v3)


def _siphash13_compress(state: Tuple[UInt64, UInt64, UInt64, UInt64], word: UInt64) -> Tuple[UInt64, UInt64, UInt64, UInt64]:
    var (v0, v1, v2, v3) = state
    v3 ^= word
    var (next0, next1, next2, next3) = _siphash13_round((v0, v1, v2, v3))
    next0 ^= word
    return (next0, next1, next2, next3)


def runtime_request_id_from_uuid7(identifier: String, local_sequence: UInt64) raises -> UInt64:
    # Match pinned 0.166.0 DefaultHasher input order: UUID u128, then sequence u64.
    var state = (
        UInt64(0x736f6d6570736575), UInt64(0x646f72616e646f6d),
        UInt64(0x6c7967656e657261), UInt64(0x7465646279746573),
    )
    # UUID::as_u128 hashes its lower word first on the little-endian release targets.
    state = _siphash13_compress(state, _uuid7_u64(identifier, 16))
    state = _siphash13_compress(state, _uuid7_u64(identifier, 0))
    state = _siphash13_compress(state, local_sequence)
    state = _siphash13_compress(state, UInt64(24) << UInt64(56))
    var (v0, v1, v2, v3) = state
    v2 ^= UInt64(0xff)
    state = _siphash13_round((v0, v1, v2, v3))
    state = _siphash13_round(state)
    state = _siphash13_round(state)
    var hash = state[0] ^ state[1] ^ state[2] ^ state[3]
    var prefix = hash >> UInt64(32)
    if prefix == 0:
        prefix = 1
    return (prefix << UInt64(32)) | (local_sequence & UInt64(0xFFFFFFFF))


def _hex_byte(value: UInt8) -> String:
    return _hex_digit(Int(value >> 4)) + _hex_digit(Int(value & 15))


def _hex_digit(value: Int) -> String:
    if value < 10:
        return String(chr(48 + value))
    return String(chr(87 + value))
