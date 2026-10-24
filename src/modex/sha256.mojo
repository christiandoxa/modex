"""Streaming SHA-256 as specified by NIST FIPS 180-4."""

from std.collections import List
from std.collections import ImmSpan

comptime K = [
    UInt32(0x428a2f98), UInt32(0x71374491), UInt32(0xb5c0fbcf), UInt32(0xe9b5dba5), UInt32(0x3956c25b), UInt32(0x59f111f1), UInt32(0x923f82a4), UInt32(0xab1c5ed5),
    UInt32(0xd807aa98), UInt32(0x12835b01), UInt32(0x243185be), UInt32(0x550c7dc3), UInt32(0x72be5d74), UInt32(0x80deb1fe), UInt32(0x9bdc06a7), UInt32(0xc19bf174),
    UInt32(0xe49b69c1), UInt32(0xefbe4786), UInt32(0x0fc19dc6), UInt32(0x240ca1cc), UInt32(0x2de92c6f), UInt32(0x4a7484aa), UInt32(0x5cb0a9dc), UInt32(0x76f988da),
    UInt32(0x983e5152), UInt32(0xa831c66d), UInt32(0xb00327c8), UInt32(0xbf597fc7), UInt32(0xc6e00bf3), UInt32(0xd5a79147), UInt32(0x06ca6351), UInt32(0x14292967),
    UInt32(0x27b70a85), UInt32(0x2e1b2138), UInt32(0x4d2c6dfc), UInt32(0x53380d13), UInt32(0x650a7354), UInt32(0x766a0abb), UInt32(0x81c2c92e), UInt32(0x92722c85),
    UInt32(0xa2bfe8a1), UInt32(0xa81a664b), UInt32(0xc24b8b70), UInt32(0xc76c51a3), UInt32(0xd192e819), UInt32(0xd6990624), UInt32(0xf40e3585), UInt32(0x106aa070),
    UInt32(0x19a4c116), UInt32(0x1e376c08), UInt32(0x2748774c), UInt32(0x34b0bcb5), UInt32(0x391c0cb3), UInt32(0x4ed8aa4a), UInt32(0x5b9cca4f), UInt32(0x682e6ff3),
    UInt32(0x748f82ee), UInt32(0x78a5636f), UInt32(0x84c87814), UInt32(0x8cc70208), UInt32(0x90befffa), UInt32(0xa4506ceb), UInt32(0xbef9a3f7), UInt32(0xc67178f2),
]

def rotr(x: UInt32, n: Int) -> UInt32:
    return (x >> UInt32(n)) | (x << UInt32(32 - n))

struct SHA256(Copyable):
    var state: List[UInt32]
    var pending: List[UInt8]
    var length: UInt64

    def __init__(out self):
        self.state = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
        self.pending = []
        self.length = 0

    def block(mut self, data: ImmSpan[UInt8, _], offset: Int):
        var w = List[UInt32](capacity=64)
        for i in range(16):
            var p = offset + i * 4
            w.append((UInt32(data[p]) << 24) | (UInt32(data[p + 1]) << 16) | (UInt32(data[p + 2]) << 8) | UInt32(data[p + 3]))
        for i in range(16, 64):
            var x = w[i - 15]
            var y = w[i - 2]
            var s0 = rotr(x, 7) ^ rotr(x, 18) ^ (x >> 3)
            var s1 = rotr(y, 17) ^ rotr(y, 19) ^ (y >> 10)
            w.append(w[i - 16] + s0 + w[i - 7] + s1)
        var constants = materialize[K]()
        var a = self.state[0]
        var b = self.state[1]
        var c = self.state[2]
        var d = self.state[3]
        var e = self.state[4]
        var f = self.state[5]
        var g = self.state[6]
        var h = self.state[7]
        for i in range(64):
            var s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
            var ch = (e & f) ^ ((~e) & g)
            var t1 = h + s1 + ch + constants[i] + w[i]
            var s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
            var maj = (a & b) ^ (a & c) ^ (b & c)
            var t2 = s0 + maj
            h = g; g = f; f = e; e = d + t1
            d = c; c = b; b = a; a = t1 + t2
        self.state[0] = self.state[0] + a
        self.state[1] = self.state[1] + b
        self.state[2] = self.state[2] + c
        self.state[3] = self.state[3] + d
        self.state[4] = self.state[4] + e
        self.state[5] = self.state[5] + f
        self.state[6] = self.state[6] + g
        self.state[7] = self.state[7] + h

    def update(mut self, data: ImmSpan[UInt8, _]) raises:
        # FIPS 180-4 encodes the message length in a 64-bit bit count.
        if self.length > 0x1fffffffffffffff or UInt64(len(data)) > 0x1fffffffffffffff - self.length:
            raise Error("SHA-256 message exceeds the 64-bit bit-length limit")
        self.length += UInt64(len(data))
        var i = 0
        while i < len(data) and self.pending:
            self.pending.append(data[i]); i += 1
            if len(self.pending) == 64:
                var full = self.pending.copy()
                self.block(full, 0)
                self.pending.clear()
        while i + 64 <= len(data):
            self.block(data[i:i + 64], 0)
            i += 64
        while i < len(data):
            self.pending.append(data[i]); i += 1

    def hex_digest(self) raises -> String:
        var tail = self.pending.copy()
        tail.append(0x80)
        while len(tail) % 64 != 56: tail.append(0)
        var bit_length = self.length * 8
        for shift in range(8): tail.append(UInt8(bit_length >> UInt64(56 - shift * 8)))
        var copy = SHA256()
        copy.state = self.state.copy()
        var pos = 0
        while pos < len(tail):
            copy.block(tail, pos)
            pos += 64
        var out = String()
        comptime digits = "0123456789abcdef"
        for word in copy.state:
            for shift in range(7, -1, -1):
                var nibble = Int((word >> UInt32(shift * 4)) & 15)
                out += chr(Int(digits.as_bytes()[nibble]))
        return out

def hash_file(path: String, max_bytes: Int = 536870912) raises -> String:
    if max_bytes < 0: raise Error("file size limit cannot be negative")
    var file = open(path, "r")
    var hash = SHA256()
    var total = 0
    while True:
        var chunk = file.read_bytes(65536)
        if not chunk: break
        total += len(chunk)
        if total > max_bytes: raise Error("file exceeds SHA-256 size limit")
        hash.update(chunk)
    return hash.hex_digest()
