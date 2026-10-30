from std.collections import List
from std.testing import assert_equal, assert_false, assert_true

from modex.uuid7 import new_uuid7, runtime_request_id_from_uuid7, runtime_request_sequence_next, runtime_request_sequence_take, uuid7_from_parts, uuid7_suffix_u32


def main() raises:
    var random = List[UInt8]()
    for _ in range(16):
        random.append(0)
    random[6] = 0x0C
    random[7] = 0xC3
    random[8] = 0x18
    random[9] = 0xC4
    random[10] = 0xDC
    random[11] = 0x0C
    random[12] = 0x0C
    random[13] = 0x07
    random[14] = 0x39
    random[15] = 0x8F
    # RFC 9562 Appendix A.6 supplies the independent timestamp and output vector.
    assert_equal(uuid7_from_parts(1645557742000, random), "017f22e2-79b0-7cc3-98c4-dc0c0c07398f")
    assert_equal(uuid7_suffix_u32("017f22e2-79b0-7cc3-98c4-dc0c0c07398f"), UInt64(0x0C07398F))
    assert_equal(uuid7_suffix_u32("ffffffff-ffff-7fff-bfff-ffffffffffff"), UInt64(0xFFFFFFFF))
    # Fixed vectors from Rust 1.99.1 DefaultHasher for UUID-as-u128 then u64 sequence.
    var entropy = "017f22e2-79b0-7cc3-98c4-dc0c0c07398f"
    assert_equal(runtime_request_id_from_uuid7(entropy, UInt64(1)), UInt64(0x3C2A7A9D00000001))
    assert_equal(runtime_request_id_from_uuid7(entropy, UInt64(0x123456789ABCDEF0)), UInt64(0x9A52489A9ABCDEF0))
    assert_equal(runtime_request_id_from_uuid7(entropy, UInt64.MAX), UInt64(0x14E68C0DFFFFFFFF))
    assert_equal(runtime_request_sequence_next(UInt64(0)), UInt64(1))
    assert_equal(runtime_request_sequence_next(UInt64.MAX), UInt64(0))
    var taken = runtime_request_sequence_take(UInt64(1))
    assert_equal(taken[0], UInt64(1))
    assert_equal(taken[1], UInt64(2))
    taken = runtime_request_sequence_take(UInt64.MAX)
    assert_equal(taken[0], UInt64.MAX)
    assert_equal(taken[1], UInt64(0))
    var invalid_id = False
    try:
        _ = runtime_request_id_from_uuid7("017f22e2-79b0-7cc3-98c4_dc0c0c07398f", UInt64(1))
    except error:
        invalid_id = String(error) == "UUIDv7 string has invalid format"
    assert_true(invalid_id)
    var invalid_suffix = False
    try:
        _ = uuid7_suffix_u32("not-a-uuid")
    except error:
        invalid_suffix = String(error) == "UUIDv7 string has invalid length"
    assert_true(invalid_suffix)
    invalid_suffix = False
    try:
        _ = uuid7_suffix_u32("00000000-0000-7000-8000-00000000000z")
    except error:
        invalid_suffix = String(error) == "UUIDv7 string has invalid suffix"
    assert_true(invalid_suffix)

    var extremes = List[UInt8](length=16, fill=0)
    assert_equal(uuid7_from_parts(0, extremes), "00000000-0000-7000-8000-000000000000")
    for index in range(16):
        extremes[index] = 255
    assert_equal(uuid7_from_parts(0xFFFFFFFFFFFF, extremes), "ffffffff-ffff-7fff-bfff-ffffffffffff")

    var bounded = False
    try:
        _ = uuid7_from_parts(0x1000000000000, random)
    except error:
        bounded = String(error) == "UUIDv7 timestamp exceeds 48 bits"
    assert_true(bounded)
    var short = List[UInt8]()
    bounded = False
    try:
        _ = uuid7_from_parts(0, short)
    except error:
        bounded = String(error) == "UUIDv7 requires 16 random bytes"
    assert_true(bounded)

    var first = new_uuid7()
    var second = new_uuid7()
    assert_false(first == second)
    assert_equal(first[byte=14:15], "7")
    var variant = Int(first.as_bytes()[19])
    assert_true(variant == 56 or variant == 57 or variant == 97 or variant == 98)
    print("UUIDv7 checks: PASS")
