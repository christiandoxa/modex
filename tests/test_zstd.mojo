from std.collections import List, Span
from std.testing import assert_equal

from modex.xxhash import Xxh64
from modex.zstd import ZstdReader
from modex.zstd import default_table
from modex.zstd_entropy import ReverseBits


def zstd_error(data: List[UInt8]) -> String:
    var reader = ZstdReader(data)
    try:
        _ = reader.read_block()
    except error:
        return String(error)
    return "no error"


def main() raises:
    var hash = Xxh64()
    assert_equal(hash.digest(), UInt64(0xEF46DB3751D8E999))
    hash.update([UInt8(97), UInt8(98), UInt8(99)])
    assert_equal(hash.digest(), UInt64(0x44BC2CF5AD770999))
    var bits = ReverseBits([UInt8(0b101101)])
    assert_equal(bits.read(2), 1)
    assert_equal(bits.read(3), 5)
    for kind in range(3):
        var table = default_table(kind)
        assert_equal(len(table.entries), 32 if kind == 1 else 64)
    var frame = ZstdReader([
        UInt8(0x28), UInt8(0xB5), UInt8(0x2F), UInt8(0xFD), UInt8(0x20), UInt8(2),
        UInt8(0x11), UInt8(0), UInt8(0), UInt8(0x6F), UInt8(0x6B),
    ])
    var decoded = frame.read_block()
    assert_equal(String(from_utf8=Span(decoded)), "ok")
    assert_equal(frame.read_block(), List[UInt8]())
    var skippable = ZstdReader([
        UInt8(0x5F), UInt8(0x2A), UInt8(0x4D), UInt8(0x18), UInt8(4), UInt8(0), UInt8(0), UInt8(0),
        UInt8(0x6D), UInt8(0x65), UInt8(0x74), UInt8(0x61),
        UInt8(0x28), UInt8(0xB5), UInt8(0x2F), UInt8(0xFD), UInt8(0x20), UInt8(2),
        UInt8(0x11), UInt8(0), UInt8(0), UInt8(0x6F), UInt8(0x6B),
    ])
    assert_equal(String(from_utf8=Span(skippable.read_block())), "ok")
    assert_equal(zstd_error([UInt8(0x28)]), "incomplete frame")
    assert_equal(zstd_error([UInt8(0x28), UInt8(0xB5), UInt8(0x2F)]), "incomplete frame")
    assert_equal(zstd_error([
        UInt8(0x28), UInt8(0xB5), UInt8(0x2F), UInt8(0xFD), UInt8(0x20),
    ]), "incomplete frame")
    assert_equal(zstd_error([UInt8(0x50)]), "incomplete frame")
    assert_equal(zstd_error([UInt8(0x5F)]), "incomplete frame")
    assert_equal(zstd_error([UInt8(0x5F), UInt8(0x2A), UInt8(0x4D), UInt8(0x18)]), "incomplete frame")
    assert_equal(zstd_error([UInt8(0x78)]), "Unknown frame descriptor")
    assert_equal(zstd_error([UInt8(0x28), UInt8(0)]), "Unknown frame descriptor")
    assert_equal(zstd_error([UInt8(0x60)]), "Unknown frame descriptor")
    print("Zstandard bits, default entropy tables and checksum checks: PASS")
