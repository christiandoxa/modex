"""Streaming dictionary-free Zstandard decoding from RFC 8878."""

from std.collections import List
from std.io import FileHandle

from .xxhash import Xxh64
from .zstd_entropy import FseEntry, FseTable, HuffmanTable, ReverseBits, ZstdBytes, fse_table, huffman_stream, huffman_table, read_fse

comptime ZSTD_BLOCK_MAX = 128 * 1024
comptime ZSTD_WINDOW_MAX = 128 * 1024 * 1024


def default_table(kind: Int) raises -> FseTable:
    if kind == 0:
        return fse_table(6, [4, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1,
                            2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 2, 1, 1, 1, 1, 1,
                            -1, -1, -1, -1])
    if kind == 1:
        var counts = List[Int](length=29, fill=1)
        for index in range(6, 9):
            counts[index] = 2
        for index in range(24, 29):
            counts[index] = -1
        return fse_table(5, counts)
    var counts = List[Int](length=53, fill=1)
    counts[1] = 4
    counts[2] = 3
    for index in range(3, 9):
        counts[index] = 2
    for index in range(46, 53):
        counts[index] = -1
    return fse_table(6, counts)


def literal_length(code: Int, mut bits: ReverseBits) raises -> Int:
    if code <= 15:
        return code
    var bases: List[Int] = [16, 18, 20, 22, 24, 28, 32, 40, 48, 64, 128, 256, 512,
                            1024, 2048, 4096, 8192, 16384, 32768, 65536]
    var widths: List[Int] = [1, 1, 1, 1, 2, 2, 3, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    return bases[code - 16] + bits.read(widths[code - 16])


def match_length(code: Int, mut bits: ReverseBits) raises -> Int:
    if code <= 31:
        return code + 3
    var bases: List[Int] = [35, 37, 39, 41, 43, 47, 51, 59, 67, 83, 99, 131, 259,
                            515, 1027, 2051, 4099, 8195, 16387, 32771, 65539]
    var widths: List[Int] = [1, 1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    return bases[code - 32] + bits.read(widths[code - 32])


struct ZstdReader(Movable):
    var file: FileHandle
    var active: Bool
    var seen_frame: Bool
    var known_size: Bool
    var expected_size: UInt64
    var checksum: Bool
    var window: Int
    var block_limit: Int
    var history: List[UInt8]
    var produced: UInt64
    var hash: Xxh64
    var huffman: HuffmanTable
    var tables: List[FseTable]
    var repeats: List[Int]
    var raw_remaining: Int
    var raw_value: Int
    var raw_last: Bool
    var raw_partial: Bool
    var pending_finish: Bool
    var buffered: List[UInt8]
    var buffered_position: Int
    var incomplete_pending: Bool

    def __init__(out self, var file: FileHandle):
        self.file = file^
        self.active = False
        self.seen_frame = False
        self.known_size = False
        self.expected_size = 0
        self.checksum = False
        self.window = 0
        self.block_limit = 0
        self.history = []
        self.produced = 0
        self.hash = Xxh64()
        self.huffman = HuffmanTable(0, [])
        self.tables = []
        self.repeats = []
        self.raw_remaining = 0
        self.raw_value = -1
        self.raw_last = False
        self.raw_partial = False
        self.pending_finish = False
        self.buffered = []
        self.buffered_position = 0
        self.incomplete_pending = False

    def take(self, count: Int) raises -> List[UInt8]:
        var result = List[UInt8](capacity=count)
        while len(result) < count:
            var block = self.file.read_bytes(count - len(result))
            if not block:
                raise Error("incomplete frame")
            result.extend(block^)
        return result^

    def little(self, count: Int) raises -> UInt64:
        var bytes = self.take(count)
        var result = UInt64(0)
        for index in range(count):
            result |= UInt64(bytes[index]) << UInt64(index * 8)
        return result

    def start_frame(mut self) raises -> Bool:
        while True:
            var magic_bytes = self.file.read_bytes(4)
            if not magic_bytes:
                if not self.seen_frame:
                    raise Error("incomplete frame")
                return False
            if len(magic_bytes) < 4:
                magic_bytes.extend(self.take(4 - len(magic_bytes)))
            var magic_reader = ZstdBytes(magic_bytes^, 0)
            var magic = magic_reader.little(4)
            if 0x184D2A50 <= magic <= 0x184D2A5F:
                var remaining = self.little(4)
                while remaining:
                    var count = Int(min(remaining, UInt64(ZSTD_BLOCK_MAX)))
                    var skipped = self.take(count)
                    remaining -= UInt64(count)
                self.seen_frame = True
                continue
            if magic != 0xFD2FB528:
                raise Error("Unknown frame descriptor")
            break
        var descriptor = Int(self.little(1))
        if descriptor & 8:
            raise Error("Unsupported frame parameter")
        var single = (descriptor & 32) != 0
        self.checksum = (descriptor & 4) != 0
        var window = UInt64(0)
        if not single:
            var encoded = Int(self.little(1))
            var base = UInt64(1) << UInt64(10 + (encoded >> 3))
            window = base + (base >> 3) * UInt64(encoded & 7)
        var dictionary_flag = descriptor & 3
        if dictionary_flag and self.little(1 << (dictionary_flag - 1)) != 0:
            raise Error("Dictionary mismatch")
        var size_flag = descriptor >> 6
        var size_bytes = (1 if single else 0) if size_flag == 0 else 1 << size_flag
        self.known_size = size_bytes != 0
        self.expected_size = self.little(size_bytes)
        if size_bytes == 2:
            self.expected_size += 256
        if single:
            window = self.expected_size
        if window > ZSTD_WINDOW_MAX:
            raise Error("Frame requires too much memory for decoding")
        self.window = Int(window)
        self.block_limit = min(self.window, ZSTD_BLOCK_MAX)
        self.history = List[UInt8](length=max(1, self.window), fill=0)
        self.produced = 0
        self.hash = Xxh64()
        self.huffman = HuffmanTable(0, [])
        self.tables = [FseTable(0, []), FseTable(0, []), FseTable(0, [])]
        self.repeats = [1, 4, 8]
        self.active = True
        self.seen_frame = True
        return True

    def emit(mut self, mut output: List[UInt8], value: UInt8) raises:
        if len(output) >= self.block_limit:
            raise Error("Data corruption detected")
        self.history[Int(self.produced % UInt64(len(self.history)))] = value
        self.produced += 1
        output.append(value)

    def literals(mut self, mut reader: ZstdBytes) raises -> List[UInt8]:
        var first = reader.little(1)
        var kind = first & 3
        var format = (first >> 2) & 3
        if kind < 2:
            var count = first >> 3
            if format == 1:
                count = (first >> 4) | (reader.little(1) << 4)
            elif format == 3:
                count = (first >> 4) | (reader.little(2) << 4)
            if count > self.block_limit:
                raise Error("Data corruption detected")
            if kind == 0:
                return reader.take(count)
            var value = UInt8(reader.little(1))
            return List[UInt8](length=count, fill=value)
        var width = 10 if format < 2 else 14 if format == 2 else 18
        var header_bytes = 3 if format < 2 else 4 if format == 2 else 5
        var header = first | (reader.little(header_bytes - 1) << 8)
        var count = (header >> 4) & ((1 << width) - 1)
        var compressed_size = header >> (4 + width)
        if count > self.block_limit:
            raise Error("Data corruption detected")
        var payload = ZstdBytes(reader.take(compressed_size), 0)
        if kind == 2:
            self.huffman = huffman_table(payload)
        elif not self.huffman.entries:
            raise Error("Data corruption detected")
        if format == 0:
            return huffman_stream(self.huffman, payload.take(len(payload.data) - payload.position), count)
        var sizes: List[Int] = [payload.little(2), payload.little(2), payload.little(2)]
        var last = len(payload.data) - payload.position - sizes[0] - sizes[1] - sizes[2]
        if last < 0:
            raise Error("Data corruption detected")
        sizes.append(last)
        var segment = (count + 3) // 4
        if count < 3 * segment:
            raise Error("Data corruption detected")
        var output = List[UInt8](capacity=count)
        for index in range(4):
            var length = segment if index < 3 else count - 3 * segment
            output.extend(huffman_stream(self.huffman, payload.take(sizes[index]), length))
        return output^

    def sequence_table(self, mut reader: ZstdBytes, kind: Int, mode: Int) raises -> FseTable:
        var maximum = 36 if kind == 0 else 32 if kind == 1 else 53
        if mode == 0:
            return default_table(kind)
        if mode == 1:
            var symbol = reader.little(1)
            if symbol >= maximum:
                raise Error("Data corruption detected")
            return FseTable(0, [FseEntry(symbol, 0, 0)])
        if mode == 2:
            return read_fse(reader, 8 if kind == 1 else 9, maximum)
        if not self.tables[kind].entries:
            raise Error("Data corruption detected")
        return self.tables[kind].copy()

    def compressed_block(mut self, var payload: List[UInt8]) raises -> List[UInt8]:
        var reader = ZstdBytes(payload^, 0)
        var literals = self.literals(reader)
        var count = reader.little(1)
        var output = List[UInt8]()
        var literal_position = 0
        if count:
            if count == 255:
                count = reader.little(2) + 0x7F00
            elif count >= 128:
                count = ((count - 128) << 8) + reader.little(1)
            var modes = reader.little(1)
            if modes & 3:
                raise Error("Data corruption detected")
            for kind in range(3):
                self.tables[kind] = self.sequence_table(reader, kind, (modes >> (6 - kind * 2)) & 3)
            var bits = ReverseBits(reader.take(len(reader.data) - reader.position))
            var ll_state = bits.read(self.tables[0].log)
            var of_state = bits.read(self.tables[1].log)
            var ml_state = bits.read(self.tables[2].log)
            for sequence in range(count):
                var ll = self.tables[0].entries[ll_state].copy()
                var of = self.tables[1].entries[of_state].copy()
                var ml = self.tables[2].entries[ml_state].copy()
                var offset_value = (1 << of.symbol) + bits.read(of.symbol)
                var match_count = match_length(ml.symbol, bits)
                var literal = literal_length(ll.symbol, bits)
                if literal > len(literals) - literal_position:
                    raise Error("Data corruption detected")
                for _ in range(literal):
                    self.emit(output, literals[literal_position])
                    literal_position += 1
                var offset: Int
                if offset_value > 3:
                    offset = offset_value - 3
                    self.repeats[2] = self.repeats[1]
                    self.repeats[1] = self.repeats[0]
                    self.repeats[0] = offset
                else:
                    var repeat = offset_value - 1 + (1 if literal == 0 else 0)
                    offset = self.repeats[0] - 1 if repeat == 3 else self.repeats[repeat]
                    if repeat > 0:
                        if repeat > 1:
                            self.repeats[2] = self.repeats[1]
                        self.repeats[1] = self.repeats[0]
                        self.repeats[0] = offset
                if offset < 1 or UInt64(offset) > self.produced or offset > self.window:
                    raise Error("Data corruption detected")
                for _ in range(match_count):
                    var value = self.history[Int((self.produced - UInt64(offset)) % UInt64(len(self.history)))]
                    self.emit(output, value)
                if sequence + 1 < count:
                    ll_state = ll.baseline + bits.read(ll.bits)
                    ml_state = ml.baseline + bits.read(ml.bits)
                    of_state = of.baseline + bits.read(of.bits)
            if bits.position != 0:
                raise Error("Data corruption detected")
        elif reader.position != len(reader.data):
            raise Error("Data corruption detected")
        while literal_position < len(literals):
            self.emit(output, literals[literal_position])
            literal_position += 1
        return output^

    def finish_frame(mut self) raises:
        if self.known_size and self.produced != self.expected_size:
            raise Error("Data corruption detected")
        if self.checksum and self.little(4) != (self.hash.digest() & 0xFFFFFFFF):
            raise Error("Restored data doesn't match checksum")
        self.active = False
        self.pending_finish = False

    def raw_chunk(mut self) raises -> List[UInt8]:
        var count = min(8192, self.raw_remaining)
        var output = List[UInt8](capacity=count)
        self.raw_partial = False
        if self.raw_value < 0:
            var raw = self.file.read_bytes(count)
            if not raw:
                raise Error("incomplete frame")
            self.raw_partial = len(raw) < count
            for value in raw:
                self.emit(output, value)
        else:
            for _ in range(count):
                self.emit(output, UInt8(self.raw_value))
        self.raw_remaining -= len(output)
        self.hash.update(output)
        if self.known_size and self.produced > self.expected_size:
            raise Error("Data corruption detected")
        if self.raw_remaining == 0 and self.raw_last:
            self.pending_finish = True
        return output^

    def read_block(mut self) raises -> List[UInt8]:
        while True:
            if self.pending_finish:
                self.finish_frame()
            if self.raw_remaining:
                return self.raw_chunk()
            if not self.active and not self.start_frame():
                return []
            var header = Int(self.little(3))
            var kind = (header >> 1) & 3
            var count = header >> 3
            if kind == 3 or count > self.block_limit:
                raise Error("Data corruption detected")
            if kind < 2:
                self.raw_remaining = count
                self.raw_value = Int(self.little(1)) if kind == 1 else -1
                self.raw_last = (header & 1) != 0
                if not count and self.raw_last:
                    self.pending_finish = True
                continue
            var output = self.compressed_block(self.take(count))
            self.hash.update(output)
            if self.known_size and self.produced > self.expected_size:
                raise Error("Data corruption detected")
            if header & 1:
                self.pending_finish = True
            if output:
                return output^

    def read_chunk(mut self) raises -> List[UInt8]:
        # The baseline's JSONL BufReader requests 8192 decoded bytes per read.
        if self.incomplete_pending:
            raise Error("incomplete frame")
        var output = List[UInt8](capacity=8192)
        try:
            while len(output) < 8192:
                if self.buffered_position == len(self.buffered):
                    if self.pending_finish:
                        self.finish_frame()
                        if output:
                            return output^
                    self.buffered = self.read_block()
                    self.buffered_position = 0
                    if not self.buffered:
                        return output^
                var count = min(8192 - len(output), len(self.buffered) - self.buffered_position)
                for index in range(count):
                    output.append(self.buffered[self.buffered_position + index])
                self.buffered_position += count
                if self.raw_partial:
                    return output^
            if self.buffered_position == len(self.buffered) and self.pending_finish:
                self.finish_frame()
        except error:
            # Preserve the release's decoded bytes before reporting a later EOF.
            if output and String(error) == "incomplete frame":
                self.incomplete_pending = True
                return output^
            raise
        return output^
