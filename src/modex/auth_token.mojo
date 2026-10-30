"""Per-launch bearer tokens for the private Super loopback relay."""

from std.collections import List


comptime LOCAL_CLIENT_TOKEN_BYTES = 32
comptime LOCAL_CLIENT_TOKEN_HEX_BYTES = LOCAL_CLIENT_TOKEN_BYTES * 2


def new_local_client_token() raises -> String:
    var random: List[UInt8]
    with open("/dev/urandom", "r") as source:
        random = source.read_bytes(LOCAL_CLIENT_TOKEN_BYTES)
    if len(random) != LOCAL_CLIENT_TOKEN_BYTES:
        raise Error("could not read secure randomness for local authorization")
    var token = String()
    for byte in random:
        token += _hex_byte(byte)
    return token^


def valid_local_client_token(token: String) -> Bool:
    if token.byte_length() != LOCAL_CLIENT_TOKEN_HEX_BYTES:
        return False
    for byte in token.as_bytes():
        var value = Int(byte)
        if not (48 <= value <= 57 or 97 <= value <= 102):
            return False
    return True


def constant_time_local_client_token_equal(expected: String, actual: String) -> Bool:
    if not valid_local_client_token(expected) or actual.byte_length() != LOCAL_CLIENT_TOKEN_HEX_BYTES:
        return False
    var difference: UInt8 = 0
    for index in range(LOCAL_CLIENT_TOKEN_HEX_BYTES):
        difference = difference | (expected.as_bytes()[index] ^ actual.as_bytes()[index])
    return difference == 0


def _hex_byte(value: UInt8) -> String:
    return _hex_digit(Int(value >> 4)) + _hex_digit(Int(value & 15))


def _hex_digit(value: Int) -> String:
    if value < 10:
        return String(chr(48 + value))
    return String(chr(87 + value))
