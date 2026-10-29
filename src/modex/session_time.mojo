from std.collections import List, Optional


def integer_timestamp(text: StringSlice) -> Optional[Int]:
    if not text:
        return None
    var bytes = text.as_bytes()
    var position = 1 if bytes[0] == 45 or bytes[0] == 43 else 0
    if position == len(bytes):
        return None
    var negative = bytes[0] == 45
    var limit = UInt64(9223372036854775808 if negative else 9223372036854775807)
    var value = UInt64(0)
    while position < len(bytes):
        var byte = bytes[position]
        if byte < 48 or byte > 57:
            return None
        var digit = UInt64(byte - 48)
        if value > (limit - digit) // 10:
            return None
        value = value * 10 + digit
        position += 1
    if negative:
        if value == 9223372036854775808:
            return -9223372036854775807 - 1
        return -Int(value)
    return Int(value)


def timestamp_key(text: String) -> Optional[Int]:
    if text.byte_length() < 20:
        return integer_timestamp(text)
    var bytes = text.as_bytes()
    if bytes[4] != 45 or bytes[7] != 45 or (bytes[10] != 84 and bytes[10] != 116 and bytes[10] != 32) or bytes[13] != 58 or bytes[16] != 58:
        return integer_timestamp(text)
    var parts: List[Int] = []
    for bounds in [(0, 4), (5, 7), (8, 10), (11, 13), (14, 16), (17, 19)]:
        for index in range(bounds[0], bounds[1]):
            if bytes[index] < 48 or bytes[index] > 57:
                return None
        var value = integer_timestamp(text[byte=bounds[0]:bounds[1]])
        if not value:
            return None
        parts.append(value.value())
    var year = parts[0]
    var month = parts[1]
    var day = parts[2]
    var hour = parts[3]
    var minute = parts[4]
    var second = parts[5]
    var days: List[Int] = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        days[1] = 29
    if month < 1 or month > 12 or day < 1 or day > days[month - 1] or hour > 23 or minute > 59 or second > 60 or hour < 0 or minute < 0 or second < 0:
        return None
    var zone = 19
    if bytes[zone] == 46:
        zone += 1
        var start = zone
        while zone < len(bytes) and bytes[zone] >= 48 and bytes[zone] <= 57:
            zone += 1
        if zone == start:
            return None
    var offset = 0
    if zone < len(bytes) and (bytes[zone] == 90 or bytes[zone] == 122):
        if zone + 1 != len(bytes):
            return None
    elif zone + 6 == len(bytes) and (bytes[zone] == 43 or bytes[zone] == 45) and bytes[zone + 3] == 58:
        for index in [zone + 1, zone + 2, zone + 4, zone + 5]:
            if bytes[index] < 48 or bytes[index] > 57:
                return None
        var zone_hour = integer_timestamp(text[byte=zone + 1:zone + 3])
        var zone_minute = integer_timestamp(text[byte=zone + 4:zone + 6])
        if not zone_hour or not zone_minute:
            return None
        if not 0 <= zone_hour.value() <= 23 or not 0 <= zone_minute.value() <= 59:
            return None
        offset = zone_hour.value() * 3600 + zone_minute.value() * 60
        if bytes[zone] == 45:
            offset = -offset
    else:
        return None
    # Gregorian dates are converted through the Julian day number.
    var adjusted_year = year + 4800 - (1 if month <= 2 else 0)
    var adjusted_month = month + (12 if month <= 2 else 0) - 3
    var julian = day + (153 * adjusted_month + 2) // 5 + 365 * adjusted_year + adjusted_year // 4 - adjusted_year // 100 + adjusted_year // 400 - 32045
    return (julian - 2440588) * 86400 + hour * 3600 + minute * 60 + min(second, 59) - offset
