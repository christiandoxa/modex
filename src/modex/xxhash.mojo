"""Incremental seed-zero XXH64 for the Zstandard frame checksum."""

from std.collections import List

comptime P1 = UInt64(11400714785074694791)
comptime P2 = UInt64(14029467366897019727)
comptime P3 = UInt64(1609587929392839161)
comptime P4 = UInt64(9650029242287828579)
comptime P5 = UInt64(2870177450012600261)


def rotate(value: UInt64, bits: Int) -> UInt64:
    return (value << UInt64(bits)) | (value >> UInt64(64 - bits))


def little(data: List[UInt8], position: Int, count: Int) -> UInt64:
    var value = UInt64(0)
    for index in range(count):
        value |= UInt64(data[position + index]) << UInt64(index * 8)
    return value


def round_lane(accumulator: UInt64, lane: UInt64) -> UInt64:
    return rotate(accumulator + lane * P2, 31) * P1


struct Xxh64(Copyable):
    var lanes: List[UInt64]
    var pending: List[UInt8]
    var length: UInt64

    def __init__(out self):
        self.lanes = [P1 + P2, P2, UInt64(0), UInt64(0) - P1]
        self.pending = []
        self.length = 0

    def stripe(mut self, data: List[UInt8], position: Int):
        for index in range(4):
            self.lanes[index] = round_lane(self.lanes[index], little(data, position + index * 8, 8))

    def update(mut self, data: List[UInt8]):
        self.length += UInt64(len(data))
        var position = 0
        if self.pending:
            while len(self.pending) < 32 and position < len(data):
                self.pending.append(data[position])
                position += 1
            if len(self.pending) == 32:
                var pending = self.pending.copy()
                self.stripe(pending, 0)
                self.pending.clear()
        while position + 32 <= len(data):
            self.stripe(data, position)
            position += 32
        while position < len(data):
            self.pending.append(data[position])
            position += 1

    def digest(self) -> UInt64:
        var result = P5
        if self.length >= 32:
            result = rotate(self.lanes[0], 1) + rotate(self.lanes[1], 7) + rotate(self.lanes[2], 12) + rotate(self.lanes[3], 18)
            for lane in self.lanes:
                result = (result ^ round_lane(0, lane)) * P1 + P4
        result += self.length
        var position = 0
        while position + 8 <= len(self.pending):
            result = rotate(result ^ round_lane(0, little(self.pending, position, 8)), 27) * P1 + P4
            position += 8
        if position + 4 <= len(self.pending):
            result = rotate(result ^ (little(self.pending, position, 4) * P1), 23) * P2 + P3
            position += 4
        while position < len(self.pending):
            result = rotate(result ^ (UInt64(self.pending[position]) * P5), 11) * P1
            position += 1
        result ^= result >> 33
        result *= P2
        result ^= result >> 29
        result *= P3
        return result ^ (result >> 32)
