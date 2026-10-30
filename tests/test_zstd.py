"""Independent compression interoperability and malformed-frame checks."""

from compression import zstd
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

from test_cli import ROOT


DRIVER = ROOT / "build/tests/zstd_driver"
NONCANONICAL = ROOT / "tests/fixtures/zstd-noncanonical-huffman.zst"


def decode(encoded):
    with tempfile.TemporaryDirectory(prefix="modex-zstd-") as directory:
        source = Path(directory) / "input.zst"
        output = Path(directory) / "decoded.bin"
        source.write_bytes(encoded)
        result = subprocess.run([str(DRIVER), str(source), str(output)], capture_output=True,
                                timeout=15, check=False)
        return result, output.read_bytes() if output.exists() else b""


def raw_frame(data, *, rle=False):
    count = len(data)
    descriptor = b"\xa0"  # Single segment, four-byte content size.
    header = ((count << 3) | (3 if rle else 1)).to_bytes(3, "little")
    return b"\x28\xb5\x2f\xfd" + descriptor + count.to_bytes(4, "little") + header + (data[:1] if rle else data)


def compressed_frame(blocks, size):
    header = b"\x28\xb5\x2f\xfd\x80\x00" + size.to_bytes(4, "little")
    for index, block in enumerate(blocks):
        header += ((len(block) << 3) | 4 | (index == len(blocks) - 1)).to_bytes(3, "little") + block
    return header


class ZstdTests(unittest.TestCase):
    def assert_decode(self, encoded, expected):
        self.assertEqual(zstd.decompress(encoded), expected)
        result, decoded = decode(encoded)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        self.assertEqual(decoded, expected)

    def test_raw_rle_and_small_frames(self):
        for data in (b"", b"test", bytes(range(256)), b"r" * 131072):
            with self.subTest(size=len(data), kind="raw"):
                self.assert_decode(raw_frame(data), data)
        for size in (1, 16, 131072):
            data = b"r" * size
            with self.subTest(size=size, kind="rle"):
                self.assert_decode(raw_frame(data, rle=True), data)
        for size in range(40):
            data = bytes(range(size))
            with self.subTest(size=size, kind="compressed"):
                self.assert_decode(zstd.compress(data), data)

    def test_levels_strategies_and_checksums(self):
        random_source = random.Random(8878)
        samples = [b"a" * 60000, bytes(range(256)) * 300,
                   random_source.randbytes(180000),
                   (b'{"type":"event","payload":{"text":"Session compression fixture"}}\n' * 5000),
                   (random_source.randbytes(30000) + b"repeated content" * 3000) * 4,
                   bytes(random_source.choices(range(256), weights=[90 if value in b"aeot " else 1
                         for value in range(256)], k=180000)),
                   bytes(random_source.choices(b"abcdefghijklmnpqrstuvwxyz 012345", k=400000))]
        for sample_index, data in enumerate(samples):
            for level in (-3, 1, 3, 9, 19):
                for checksum in (0, 1):
                    with self.subTest(sample=sample_index, level=level, checksum=checksum):
                        options = {zstd.CompressionParameter.compression_level: level,
                                   zstd.CompressionParameter.checksum_flag: checksum}
                        self.assert_decode(zstd.compress(data, options=options), data)
        data = samples[3]
        for strategy in zstd.Strategy:
            with self.subTest(strategy=strategy.name):
                self.assert_decode(zstd.compress(data, options={
                    zstd.CompressionParameter.strategy: strategy,
                    zstd.CompressionParameter.content_size_flag: 0}), data)
        for window_log in (10, 14, 17):
            with self.subTest(window_log=window_log):
                self.assert_decode(zstd.compress(samples[6], options={
                    zstd.CompressionParameter.window_log: window_log,
                    zstd.CompressionParameter.content_size_flag: 0,
                    zstd.CompressionParameter.checksum_flag: 1}), samples[6])

    def test_explicit_huffman_and_sequence_modes(self):
        # RFC 8878 section 4.2.1 gives the weights and prefix codes for symbols 0,1,4,5.
        bitstream = (int("10100000001", 2) | (1 << 11)).to_bytes(2, "little")
        tree = b"\x84\x43\x20\x10"
        literal_header = ((len(tree + bitstream) << 14) | (4 << 4) | 2).to_bytes(3, "little")
        first = literal_header + tree + bitstream + b"\x00"
        repeat = ((len(bitstream) << 14) | (4 << 4) | 3).to_bytes(3, "little") + bitstream + b"\x00"
        self.assert_decode(compressed_frame([first, repeat], 8), bytes([0, 1, 4, 5]) * 2)
        self.assert_decode(compressed_frame([bytes([(20 << 3) | 1, 65, 0])], 20), b"A" * 20)
        first = b"\x08A\x01\x54\x01\x00\x00\x01"
        repeat = b"\x08A\x01\xfc\x01"
        self.assert_decode(compressed_frame([first, repeat], 8), b"A" * 8)

    def test_concatenation_skippable_frames_and_block_flushes(self):
        parts = [b"prefix\n", b"repeating middle\n" * 30000, b"suffix\n"]
        encoded = b""
        for index, part in enumerate(parts):
            encoded += (0x184D2A50 + index).to_bytes(4, "little") + b"\x04\x00\x00\x00meta"
            encoded += zstd.compress(part)
        self.assert_decode(encoded, b"".join(parts))
        compressor = zstd.ZstdCompressor(options={zstd.CompressionParameter.checksum_flag: 1})
        encoded = b"".join(compressor.compress(part, zstd.ZstdCompressor.FLUSH_BLOCK) for part in parts)
        encoded += compressor.flush()
        self.assert_decode(encoded, b"".join(parts))

    def test_noncanonical_huffman_leftover_bits_stay_rejected(self):
        encoded = NONCANONICAL.read_bytes()
        self.assertTrue(zstd.decompress(encoded))
        result, output = decode(encoded)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"Data corruption detected", result.stderr)
        self.assertEqual(output, b"")

    def test_truncation_and_malformed_frames(self):
        encoded = zstd.compress(b"frame fixture " * 300, options={zstd.CompressionParameter.checksum_flag: 1})
        cases = [encoded[:index] for index in range(1, len(encoded))]
        cases += [b"", b"garbage", encoded[:-1] + bytes([encoded[-1] ^ 1]),
                  raw_frame(b"data")[:4] + b"\xa8" + raw_frame(b"data")[5:]]
        for index, damaged in enumerate(cases):
            with self.subTest(case=index):
                with self.assertRaises(zstd.ZstdError):
                    zstd.decompress(damaged)
                result, unused = decode(damaged)
                self.assertEqual(result.returncode, 1)
                self.assertTrue(result.stderr)

    def test_generated_payloads_and_mutated_entropy(self):
        random_source = random.Random(9659)
        known_difference = NONCANONICAL.read_bytes()
        for case in range(60):
            alphabet = random_source.sample(range(256), random_source.randint(2, 256))
            data = bytes(random_source.choices(alphabet, k=random_source.randint(100, 20000)))
            level = random_source.choice((-3, 1, 3, 9, 19))
            encoded = zstd.compress(data, level=level)
            with self.subTest(case=case, kind="valid"):
                self.assert_decode(encoded, data)
            damaged = bytearray(encoded)
            position = random_source.randrange(len(damaged))
            damaged[position] ^= 1 << random_source.randrange(8)
            with self.subTest(case=case, kind="mutated"):
                try:
                    expected = zstd.decompress(damaged)
                except zstd.ZstdError:
                    result, unused = decode(damaged)
                    self.assertEqual(result.returncode, 1)
                else:
                    if damaged == known_difference:
                        # The frozen release accepts unused Huffman bits; RFC 8878 requires exact consumption.
                        result, unused = decode(damaged)
                        self.assertEqual(result.returncode, 1)
                        self.assertIn(b"Data corruption detected", result.stderr)
                    else:
                        self.assert_decode(damaged, expected)


if __name__ == "__main__":
    unittest.main()
