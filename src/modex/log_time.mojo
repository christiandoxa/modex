"""Format recognized log timestamps in the process local time zone."""

from .local_time import civil_days, format_local_epoch
from .session_time import timestamp_key
from .text import is_whitespace


@fieldwise_init
struct CustomTimestampParser:
    var source: String
    var position: Int

    def peek(self) -> Int:
        return Int(self.source.as_bytes()[self.position]) if self.position < self.source.byte_length() else -1

    def digits(mut self, maximum: Int) raises -> Int:
        self.whitespace()
        var value = 0
        var count = 0
        while 48 <= self.peek() <= 57:
            if count == maximum:
                break
            value = value * 10 + self.peek() - 48
            self.position += 1
            count += 1
        if count == 0:
            raise Error("missing timestamp digits")
        return value

    def year_digits(mut self, signed: Bool) raises -> Int:
        self.whitespace()
        var value = 0
        var count = 0
        while 48 <= self.peek() <= 57:
            if not signed and count == 4: break
            var digit = self.peek() - 48
            if value > (1_000_000 - digit) // 10:
                raise Error("timestamp year is out of range")
            value = value * 10 + digit
            self.position += 1
            count += 1
        if count == 0: raise Error("missing timestamp year")
        return value

    def two_digits(mut self) raises -> Int:
        self.whitespace()
        var first = self.peek()
        if first < 48 or first > 57: raise Error("invalid timestamp offset")
        self.position += 1
        var second = self.peek()
        if second < 48 or second > 57: raise Error("invalid timestamp offset")
        self.position += 1
        return (first - 48) * 10 + second - 48

    def expect(mut self, byte: Int) raises:
        if self.peek() != byte:
            raise Error("invalid timestamp separator")
        self.position += 1

    def whitespace(mut self):
        if self.position >= self.source.byte_length(): return
        for character in self.source[byte=self.position:].codepoints():
            var codepoint = Int(character)
            if not is_whitespace(codepoint): break
            self.position += chr(codepoint).byte_length()


def parse_custom_timestamp(source: String) raises -> Tuple[Int, String, Bool]:
    var parser = CustomTimestampParser(source, 0)
    parser.whitespace()
    var negative = False
    var signed_year = False
    if parser.peek() == 43 or parser.peek() == 45:
        signed_year = True
        negative = parser.peek() == 45
        parser.position += 1
    var year = parser.year_digits(signed_year)
    if negative: year = -year
    parser.expect(45)
    var month = parser.digits(2)
    parser.expect(45)
    var day = parser.digits(2)
    parser.whitespace()
    var hour = parser.digits(2)
    parser.expect(58)
    var minute = parser.digits(2)
    parser.expect(58)
    var second = parser.digits(2)
    var fraction = String("000")
    if parser.peek() == 46:
        parser.position += 1
        var fraction_start = parser.position
        var digits = List[UInt8]()
        while 48 <= parser.peek() <= 57:
            if len(digits) < 3:
                digits.append(UInt8(parser.peek()))
            parser.position += 1
        if parser.position == fraction_start:
            raise Error("missing timestamp fraction")
        fraction = String(from_utf8=Span(digits))
        while fraction.byte_length() < 3: fraction += "0"
    parser.whitespace()
    var offset: Int
    if parser.peek() == 43 or parser.peek() == 45:
        var west = parser.peek() == 45
        parser.position += 1
        var offset_hour = parser.two_digits()
        parser.whitespace()
        if parser.peek() == 58:
            parser.position += 1
        var offset_minute = parser.two_digits()
        if offset_hour > 23 or offset_minute > 59:
            raise Error("invalid timestamp offset")
        offset = offset_hour * 3600 + offset_minute * 60
        if west: offset = -offset
    else:
        raise Error("invalid timestamp offset")
    if parser.peek() != -1:
        raise Error("trailing timestamp data")
    if month < 1 or month > 12 or day < 1 or day > month_days(year, month) or hour > 23 or minute > 59 or second > 60:
        raise Error("invalid timestamp fields")
    var epoch = civil_days(year, month, day) * 86400 + hour * 3600 + minute * 60 + min(second, 59) - offset
    return epoch, fraction, second == 60


def month_days(year: Int, month: Int) -> Int:
    if month == 2:
        return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    return 30 if month == 4 or month == 6 or month == 9 or month == 11 else 31


def is_digit(byte: Int) -> Bool:
    return 48 <= byte <= 57


def valid_rfc3339(text: String) -> Bool:
    var bytes = text.as_bytes()
    if len(bytes) < 20 or bytes[4] != 45 or bytes[7] != 45 or (bytes[10] != 84 and bytes[10] != 116 and bytes[10] != 32) or bytes[13] != 58 or bytes[16] != 58:
        return False
    for index in [0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18]:
        if not is_digit(Int(bytes[index])): return False
    var zone = 19
    if zone < len(bytes) and bytes[zone] == 46:
        zone += 1
        var start = zone
        while zone < len(bytes) and is_digit(Int(bytes[zone])): zone += 1
        if zone == start: return False
    if zone < len(bytes) and (bytes[zone] == 90 or bytes[zone] == 122):
        return zone + 1 == len(bytes)
    return zone + 6 == len(bytes) and (bytes[zone] == 43 or bytes[zone] == 45) and bytes[zone + 3] == 58 and is_digit(Int(bytes[zone + 1])) and is_digit(Int(bytes[zone + 2])) and is_digit(Int(bytes[zone + 4])) and is_digit(Int(bytes[zone + 5]))


def two_digits(text: String, start: Int) -> Int:
    var bytes = text.as_bytes()
    return (Int(bytes[start]) - 48) * 10 + Int(bytes[start + 1]) - 48


def local_offset(local: String, zone: Int) -> Tuple[String, Int]:
    var value = String(local[byte=zone + 1:])
    var bytes = value.as_bytes()
    if len(bytes) < 6 or (bytes[0] != 43 and bytes[0] != 45):
        return value, 0
    var seconds = two_digits(value, 1) * 3600 + two_digits(value, 4) * 60
    if len(bytes) >= 9 and bytes[6] == 58:
        seconds += two_digits(value, 7)
    if bytes[0] == 45: seconds = -seconds
    var minutes = (abs(seconds) + 30) // 60
    var rounded = String("-" if seconds < 0 else "+") + two_digits_text(minutes // 60) + ":" + two_digits_text(minutes % 60)
    return rounded, seconds


def two_digits_text(value: Int) -> String:
    return String(chr(48 + value // 10)) + String(chr(48 + value % 10))


def local_log_timestamp(value: String) -> String:
    var parsed = (0, String("000"), False)
    var parsed_valid = False
    if value.byte_length() >= 20:
        var bytes = value.as_bytes()
        if (bytes[10] == 84 or bytes[10] == 116 or bytes[10] == 32) and valid_rfc3339(value):
            var epoch = timestamp_key(value)
            if epoch:
                var fraction = String("000")
                if bytes[19] == 46:
                    var end = 20
                    while end < value.byte_length() and bytes[end] >= 48 and bytes[end] <= 57: end += 1
                    fraction = String(value[byte=20:min(23, end)])
                    while fraction.byte_length() < 3: fraction += "0"
                parsed = (epoch.value(), fraction, bytes[17] == 54 and bytes[18] == 48)
                parsed_valid = True
    if not parsed_valid:
        try:
            parsed = parse_custom_timestamp(value)
        except:
            return value.copy()
    var local: String
    try:
        local = format_local_epoch(parsed[0])
    except:
        return value.copy()
    var zone = local.rfind(" ")
    if zone < 0:
        return value.copy()
    var rounded_offset, offset_seconds = local_offset(local, zone)
    local = String(local[byte=0:zone + 1]) + rounded_offset
    if parsed[2] and offset_seconds % 60 != 0:
        try:
            local = format_local_epoch(parsed[0] + 1)
            zone = local.rfind(" ")
            var rounded = local_offset(local, zone)[0]
            local = String(local[byte=0:zone + 1]) + rounded
        except:
            return value.copy()
    var clock = String(local[byte=0:zone])
    if parsed[2] and offset_seconds % 60 == 0:
        var second = clock.rfind(":")
        if second >= 0:
            clock = String(clock[byte=0:second + 1]) + "60"
    return clock + "." + parsed[1] + String(local[byte=zone:])
