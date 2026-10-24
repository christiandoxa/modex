"""Zstandard entropy decoding from RFC 8878, sections 4.1 and 4.2."""

from std.collections import List


def highest_bit(value: Int) -> Int:
    var result = -1
    var remaining = value
    while remaining:
        remaining >>= 1
        result += 1
    return result


@fieldwise_init
struct ZstdBytes(Copyable):
    var data: List[UInt8]
    var position: Int

    def take(mut self, count: Int) raises -> List[UInt8]:
        if count < 0 or count > len(self.data) - self.position:
            raise Error("Data corruption detected")
        var result = List[UInt8](capacity=count)
        for index in range(count):
            result.append(self.data[self.position + index])
        self.position += count
        return result^

    def little(mut self, count: Int) raises -> Int:
        if count < 0 or count > 5 or count > len(self.data) - self.position:
            raise Error("Data corruption detected")
        var result = 0
        for index in range(count):
            result |= Int(self.data[self.position + index]) << (index * 8)
        self.position += count
        return result


@fieldwise_init
struct ForwardBits(Copyable):
    var data: List[UInt8]
    var position: Int

    def read(mut self, count: Int) raises -> Int:
        if count < 0 or count > 32 or self.position + count > len(self.data) * 8:
            raise Error("Data corruption detected")
        var value = 0
        for index in range(count):
            var bit = self.position + index
            value |= ((Int(self.data[bit // 8]) >> (bit % 8)) & 1) << index
        self.position += count
        return value


struct ReverseBits(Copyable):
    var data: List[UInt8]
    var position: Int

    def __init__(out self, var data: List[UInt8]) raises:
        if not data or data[len(data) - 1] == 0:
            raise Error("Data corruption detected")
        self.position = (len(data) - 1) * 8 + highest_bit(Int(data[len(data) - 1]))
        self.data = data^

    def peek(self, count: Int) raises -> Int:
        if count < 0 or count > 32:
            raise Error("Data corruption detected")
        var available = min(count, self.position)
        var value = 0
        for index in range(available):
            var bit = self.position - available + index
            value |= ((Int(self.data[bit // 8]) >> (bit % 8)) & 1) << index
        return value << (count - available)

    def read(mut self, count: Int) raises -> Int:
        if count > self.position:
            raise Error("Data corruption detected")
        var value = self.peek(count)
        self.position -= count
        return value


@fieldwise_init
struct FseEntry(Copyable):
    var symbol: Int
    var bits: Int
    var baseline: Int


@fieldwise_init
struct FseTable(Copyable):
    var log: Int
    var entries: List[FseEntry]


def fse_table(log: Int, counts: List[Int]) raises -> FseTable:
    var size = 1 << log
    var entries = List[FseEntry](length=size, fill=FseEntry(0, 0, 0))
    var next_state = List[Int](length=len(counts), fill=0)
    var high = size - 1
    var total = 0
    var present = 0
    for symbol in range(len(counts)):
        var count = counts[symbol]
        if count < -1:
            raise Error("Data corruption detected")
        if count:
            present += 1
        total += abs(count)
        next_state[symbol] = max(count, 1)
        if count == -1:
            if high < 0:
                raise Error("Data corruption detected")
            entries[high].symbol = symbol
            high -= 1
    if total != size or present < 2:
        raise Error("Data corruption detected")
    var position = 0
    var step = (size >> 1) + (size >> 3) + 3
    for symbol in range(len(counts)):
        for _ in range(max(0, counts[symbol])):
            entries[position].symbol = symbol
            position = (position + step) & (size - 1)
            while position > high:
                position = (position + step) & (size - 1)
    if position != 0:
        raise Error("Data corruption detected")
    for index in range(size):
        var symbol = entries[index].symbol
        var next = next_state[symbol]
        next_state[symbol] += 1
        var bits = log - highest_bit(next)
        entries[index].bits = bits
        entries[index].baseline = (next << bits) - size
    return FseTable(log, entries^)


def read_fse(mut reader: ZstdBytes, maximum_log: Int, maximum_symbols: Int) raises -> FseTable:
    var bits = ForwardBits(reader.data.copy(), reader.position * 8)
    var log = bits.read(4) + 5
    if log > maximum_log:
        raise Error("Data corruption detected")
    var remaining = (1 << log) + 1
    var threshold = 1 << log
    var count_bits = log + 1
    var counts = List[Int]()
    while remaining > 1:
        if len(counts) >= maximum_symbols:
            raise Error("Data corruption detected")
        var maximum = (threshold << 1) - 1 - remaining
        var count = bits.read(count_bits - 1)
        if count >= maximum:
            count += bits.read(1) << (count_bits - 1)
            if count >= threshold:
                count -= maximum
        count -= 1
        remaining -= abs(count)
        if remaining < 1:
            raise Error("Data corruption detected")
        counts.append(count)
        if count == 0:
            var repeats = 3
            while repeats == 3:
                repeats = bits.read(2)
                if len(counts) + repeats > maximum_symbols:
                    raise Error("Data corruption detected")
                for _ in range(repeats):
                    counts.append(0)
        while remaining < threshold:
            threshold >>= 1
            count_bits -= 1
    reader.position = (bits.position + 7) // 8
    return fse_table(log, counts)


@fieldwise_init
struct HuffmanEntry(Copyable):
    var symbol: UInt8
    var bits: Int


@fieldwise_init
struct HuffmanTable(Copyable):
    var log: Int
    var entries: List[HuffmanEntry]


def huffman_table(mut reader: ZstdBytes) raises -> HuffmanTable:
    var header = reader.little(1)
    var weights = List[Int]()
    if header >= 128:
        var count = header - 127
        for _ in range((count + 1) // 2):
            var pair = reader.little(1)
            weights.append(pair >> 4)
            if len(weights) < count:
                weights.append(pair & 15)
    else:
        var encoded = ZstdBytes(reader.take(header), 0)
        var table = read_fse(encoded, 6, 12)
        var bits = ReverseBits(encoded.take(len(encoded.data) - encoded.position))
        var state = bits.read(table.log)
        var other = bits.read(table.log)
        while True:
            if len(weights) >= 254:
                raise Error("Data corruption detected")
            var entry = table.entries[state].copy()
            weights.append(entry.symbol)
            if entry.bits > bits.position:
                weights.append(table.entries[other].symbol)
                break
            var next = entry.baseline + bits.read(entry.bits)
            state = other
            other = next
    var total = 0
    for weight in weights:
        if weight > 11:
            raise Error("Data corruption detected")
        if weight:
            total += 1 << (weight - 1)
    var log = highest_bit(total) + 1
    if log < 1 or log > 11:
        raise Error("Data corruption detected")
    var remainder = (1 << log) - total
    if remainder <= 0 or (remainder & (remainder - 1)) != 0:
        raise Error("Data corruption detected")
    weights.append(highest_bit(remainder) + 1)
    var entries = List[HuffmanEntry](length=1 << log, fill=HuffmanEntry(0, 0))
    var position = 0
    for weight in range(1, log + 1):
        for symbol in range(len(weights)):
            if weights[symbol] == weight:
                for _ in range(1 << (weight - 1)):
                    if position >= len(entries):
                        raise Error("Data corruption detected")
                    entries[position] = HuffmanEntry(UInt8(symbol), log + 1 - weight)
                    position += 1
    if position != len(entries):
        raise Error("Data corruption detected")
    return HuffmanTable(log, entries^)


def huffman_stream(table: HuffmanTable, var encoded: List[UInt8], count: Int) raises -> List[UInt8]:
    var bits = ReverseBits(encoded^)
    var output = List[UInt8](capacity=count)
    for _ in range(count):
        var entry = table.entries[bits.peek(table.log)].copy()
        _ = bits.read(entry.bits)
        output.append(entry.symbol)
    if bits.position != 0:
        raise Error("Data corruption detected")
    return output^
