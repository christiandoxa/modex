"""DeepSeek rate-limit response headers projected to Codex quota headers."""

from std.collections import List
from std.math import ceil, isfinite
from std.time.time import _realtime_nanoseconds

from .session_time import integer_timestamp, timestamp_key
from .log_time import valid_rfc3339
from .text import trim_text


def deepseek_codex_rate_limit_headers(headers: List[Tuple[String, String]]) -> List[Tuple[String, String]]:
    var now = _realtime_nanoseconds() // 1000000000
    var output = List[Tuple[String, String]]()
    _append_openai_limit(
        output, headers, "requests", "x-ratelimit-limit-requests",
        "x-ratelimit-remaining-requests", "x-ratelimit-reset-requests", now,
    )
    _append_openai_limit(
        output, headers, "tokens", "x-ratelimit-limit-tokens",
        "x-ratelimit-remaining-tokens", "x-ratelimit-reset-tokens", now,
    )
    return output^


def _append_openai_limit(
    mut output: List[Tuple[String, String]],
    headers: List[Tuple[String, String]],
    limit_id: String,
    limit_name: String,
    remaining_name: String,
    reset_name: String,
    now: Int,
):
    var limit = _header_float(headers, limit_name)
    var remaining = _header_float(headers, remaining_name)
    if not limit or not remaining or limit.value() <= 0.0:
        return
    var amount = (limit.value() - remaining.value()) / limit.value() * 100.0
    if amount < 0.0:
        amount = 0.0
    elif amount > 100.0:
        amount = 100.0
    var tenths = Int(amount * 10.0 + 0.5)
    var used = String(tenths // 10)
    if tenths % 10 != 0:
        used += "." + String(tenths % 10)
    output.append(("x-deepseek-" + limit_id + "-limit-name", "DeepSeek " + limit_id))
    output.append(("x-deepseek-" + limit_id + "-primary-used-percent", used))
    var reset = _header_value(headers, reset_name)
    if reset:
        var epoch = _reset_epoch(reset.value(), now)
        if epoch:
            output.append(("x-deepseek-" + limit_id + "-primary-reset-at", String(epoch.value())))


def _header_value(headers: List[Tuple[String, String]], expected: String) -> Optional[String]:
    for name, value in headers:
        if name.lower() == expected:
            for byte in value.as_bytes():
                if byte > 126 or byte < 32 and byte != 9:
                    return Optional[String]()
            return Optional[String](value)
    return Optional[String]()


def _header_float(headers: List[Tuple[String, String]], expected: String) -> Optional[Float64]:
    var value = _header_value(headers, expected)
    if not value:
        return Optional[Float64]()
    var text = trim_text(value.value())
    var bytes = text.as_bytes()
    var index = 0
    if index < len(bytes) and (bytes[index] == 43 or bytes[index] == 45):
        index += 1
    var digits = 0
    while index < len(bytes) and bytes[index] >= 48 and bytes[index] <= 57:
        index += 1
        digits += 1
    if index < len(bytes) and bytes[index] == 46:
        index += 1
        while index < len(bytes) and bytes[index] >= 48 and bytes[index] <= 57:
            index += 1
            digits += 1
    if digits == 0:
        return Optional[Float64]()
    if index < len(bytes) and (bytes[index] == 69 or bytes[index] == 101):
        index += 1
        if index < len(bytes) and (bytes[index] == 43 or bytes[index] == 45):
            index += 1
        var exponent_digits = 0
        while index < len(bytes) and bytes[index] >= 48 and bytes[index] <= 57:
            index += 1
            exponent_digits += 1
        if exponent_digits == 0:
            return Optional[Float64]()
    if index != len(bytes):
        return Optional[Float64]()
    try:
        var number = atof(text)
        if isfinite(number):
            return Optional[Float64](number)
    except:
        pass
    return Optional[Float64]()


def _reset_epoch(value: String, now: Int) -> Optional[Int]:
    var text = trim_text(value)
    if not text:
        return Optional[Int]()
    var rfc3339 = _rfc3339_epoch(text)
    if rfc3339:
        return rfc3339
    var numeric = integer_timestamp(text)
    if numeric:
        var number = numeric.value()
        if number > 10000000000:
            return Optional[Int](number // 1000)
        if number > now - 60:
            return Optional[Int](number)
        return Optional[Int](_saturating_add(now, max(number, 0)))
    var duration = _duration_seconds(text)
    if duration:
        return Optional[Int](_saturating_add(now, duration.value()))
    return Optional[Int]()


def _duration_seconds(value: String) -> Optional[Int]:
    var text = trim_text(value)
    var bytes = text.as_bytes()
    var number = String()
    var total: Float64 = 0.0
    var count = 0
    var index = 0
    while index < len(bytes):
        var byte = bytes[index]
        if (byte >= 48 and byte <= 57) or byte == 46:
            number += chr(Int(byte))
            index += 1
            continue
        if byte == 9 or byte == 10 or byte == 12 or byte == 13 or byte == 32:
            index += 1
            continue
        if not number:
            return Optional[Int]()
        var unit = 0
        if byte == 100:
            unit = 4
        elif byte == 104:
            unit = 3
        elif byte == 109:
            unit = 2
            if index + 1 < len(bytes) and bytes[index + 1] == 115:
                unit = 1
                index += 1
        elif byte != 115:
            return Optional[Int]()
        var amount: Float64
        try:
            amount = atof(number)
        except:
            return Optional[Int]()
        if amount < 0.0:
            return Optional[Int]()
        if unit == 1:
            total += amount / 1000.0
        elif unit == 2:
            total += amount * 60.0
        elif unit == 3:
            total += amount * 3600.0
        elif unit == 4:
            total += amount * 86400.0
        else:
            total += amount
        number = ""
        count += 1
        index += 1
    if number:
        var amount: Float64
        try:
            amount = atof(number)
        except:
            return Optional[Int]()
        if amount < 0.0:
            return Optional[Int]()
        total += amount
        count += 1
    if count == 0:
        return Optional[Int]()
    if not isfinite(total) or total >= Float64(Int.MAX):
        return Optional[Int](Int.MAX)
    return Optional[Int](Int(ceil(total)))


def _rfc3339_epoch(value: String) -> Optional[Int]:
    var bytes = value.as_bytes()
    if len(bytes) < 20:
        return Optional[Int]()
    if bytes[4] != 45 or bytes[7] != 45 or (bytes[10] != 84 and bytes[10] != 116) or bytes[13] != 58 or bytes[16] != 58 or not valid_rfc3339(value):
        return Optional[Int]()
    return timestamp_key(value)


def _saturating_add(left: Int, right: Int) -> Int:
    if right > 0 and left > Int.MAX - right:
        return Int.MAX
    if right < 0 and left < Int.MIN - right:
        return Int.MIN
    return left + right
