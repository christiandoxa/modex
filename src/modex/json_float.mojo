"""Parse a validated JSON number using the runtime log formatter's scaling order."""

from std.math import isfinite


def json_float(text: String) raises -> Float64:
    if not text:
        raise Error("empty JSON number")
    var bytes = text.as_bytes()
    var index = 0
    var negative = False
    if bytes[index] == 45:
        negative = True
        index += 1
    var significand = UInt64(0)
    var fractional_digits = 0
    var after_decimal = False
    var digits = 0
    var overflow = False
    while index < len(bytes) and bytes[index] != 101 and bytes[index] != 69:
        var byte = Int(bytes[index])
        if byte == 46:
            after_decimal = True
        else:
            var digit = UInt64(byte - 48)
            if significand > (UInt64.MAX - digit) // 10:
                overflow = True
            elif not overflow:
                significand = significand * 10 + digit
            digits += 1
            if after_decimal:
                fractional_digits += 1
        index += 1
    if digits == 0:
        raise Error("JSON number has no digits")

    var exponent = 0
    # Larger exponents cannot cancel the literal's digits into a finite nonzero value.
    var exponent_limit = len(bytes) + 1000
    if index < len(bytes):
        index += 1
        var exponent_negative = False
        if index < len(bytes) and (bytes[index] == 43 or bytes[index] == 45):
            exponent_negative = bytes[index] == 45
            index += 1
        while index < len(bytes):
            var digit = Int(bytes[index]) - 48
            if exponent > (exponent_limit - digit) // 10:
                exponent = exponent_limit
            else:
                exponent = exponent * 10 + digit
            index += 1
        if exponent_negative:
            exponent = -exponent

    if overflow:
        var fallback = atof(text)
        if not isfinite(fallback):
            raise Error("JSON number is out of range")
        return fallback
    var decimal_exponent = exponent - fractional_digits
    var value = Float64(significand)
    if decimal_exponent > 0:
        while decimal_exponent > 0:
            var power = min(decimal_exponent, 308)
            value *= atof("1e" + String(power))
            decimal_exponent -= power
    elif decimal_exponent < 0:
        while decimal_exponent < 0 and value != 0:
            var power = min(-decimal_exponent, 308)
            value /= atof("1e" + String(power))
            decimal_exponent += power
    value = -value if negative else value
    if not isfinite(value):
        raise Error("JSON number is out of range")
    return value
