from std.collections import List, Span
from std.testing import assert_equal

from modex.xxhash import Xxh64
from modex.zstd import default_table
from modex.zstd_entropy import ReverseBits


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
    print("Zstandard bits, default entropy tables and checksum checks: PASS")
