"""Local epoch rendering using OS TZif data through official file APIs."""

from std.collections import List, Optional, Span
from std.os import getenv
from std.os.path import exists


def unsigned_be(bytes: List[UInt8], position: Int, width: Int) raises -> UInt64:
    if position < 0 or width < 1 or width > 8 or position > len(bytes) - width:
        raise Error("truncated time-zone data")
    var value = UInt64(0)
    for index in range(width):
        value = (value << 8) | UInt64(bytes[position + index])
    return value


def signed_be(bytes: List[UInt8], position: Int, width: Int) raises -> Int:
    var value = unsigned_be(bytes, position, width)
    if width == 8:
        return Int(value)
    if value & (UInt64(1) << UInt64(width * 8 - 1)):
        return Int(value) - (1 << (width * 8))
    return Int(value)


@fieldwise_init
struct ZoneType(Copyable):
    var offset: Int
    var name: String


def is_leap_year(year: Int) -> Bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def civil_days(year: Int, month: Int, day: Int) -> Int:
    var adjusted = year - (1 if month <= 2 else 0)
    var era = adjusted // 400
    var year_of_era = adjusted - era * 400
    var month_index = month + (-3 if month > 2 else 9)
    var day_of_year = (153 * month_index + 2) // 5 + day - 1
    return era * 146097 + year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year - 719468


def civil_fields(local: Int) -> Tuple[Int, Int, Int, Int]:
    var days = local // 86400
    var second = local % 86400
    var shifted = days + 719468
    var era = shifted // 146097
    var day_of_era = shifted - era * 146097
    var year_of_era = (day_of_era - day_of_era // 1460 + day_of_era // 36524 - day_of_era // 146096) // 365
    var year = year_of_era + era * 400
    var day_of_year = day_of_era - (365 * year_of_era + year_of_era // 4 - year_of_era // 100)
    var month_index = (5 * day_of_year + 2) // 153
    var day = day_of_year - (153 * month_index + 2) // 5 + 1
    var month = month_index + (3 if month_index < 10 else -9)
    if month <= 2:
        year += 1
    return year, month, day, second


@fieldwise_init
struct TransitionRule(Copyable):
    var kind: Int
    var day: Int
    var month: Int
    var week: Int
    var weekday: Int
    var seconds: Int

    def epoch(self, year: Int, previous_offset: Int) -> Int:
        var day_index = self.day
        if self.kind == 0:
            day_index -= 1
            if is_leap_year(year) and self.day >= 60:
                day_index += 1
        elif self.kind == 2:
            var start = civil_days(year, self.month, 1)
            var first_weekday = (start + 4) % 7
            var day = 1 + (self.weekday - first_weekday) % 7 + (self.week - 1) * 7
            var following = civil_days(year + 1, 1, 1) if self.month == 12 else civil_days(year, self.month + 1, 1)
            if start + day - 1 >= following:
                day -= 7
            day_index = start + day - 1 - civil_days(year, 1, 1)
        return (civil_days(year, 1, 1) + day_index) * 86400 + self.seconds - previous_offset


struct PosixZone(Copyable):
    var standard: ZoneType
    var daylight: Optional[ZoneType]
    var start: TransitionRule
    var end: TransitionRule

    def __init__(out self, text: String, extended: Bool = True) raises:
        var parser = ZoneParser(text, 0, extended)
        var name = parser.name()
        self.standard = ZoneType(-parser.clock(24), name^)
        self.daylight = None
        self.start = TransitionRule(1, 0, 0, 0, 0, 0)
        self.end = TransitionRule(1, 0, 0, 0, 0, 0)
        if parser.peek() != -1:
            var daylight_name = parser.name()
            var offset = self.standard.offset + 3600
            if parser.peek() != -1 and parser.peek() != 44:
                offset = -parser.clock(24)
            self.daylight = ZoneType(offset, daylight_name^)
            parser.expect(44)
            self.start = parser.rule()
            parser.expect(44)
            self.end = parser.rule()
        if parser.peek() != -1:
            raise Error("trailing POSIX time-zone data")

    def at(self, epoch: Int) -> ZoneType:
        if not self.daylight:
            return self.standard.copy()
        var year = civil_fields(epoch)[0]
        var latest = Int.MIN
        var daylight = False
        # Adjacent years cover rules that spill across New Year by up to seven days.
        for candidate in range(year - 1, year + 2):
            var start = self.start.epoch(candidate, self.standard.offset)
            var end = self.end.epoch(candidate, self.daylight.value().offset)
            if start <= epoch and start >= latest:
                latest = start
                daylight = True
            if end <= epoch and end > latest:
                latest = end
                daylight = False
        return self.daylight.value().copy() if daylight else self.standard.copy()


@fieldwise_init
struct ZoneParser:
    var text: String
    var position: Int
    var extended: Bool

    def peek(self) -> Int:
        return Int(self.text.as_bytes()[self.position]) if self.position < self.text.byte_length() else -1

    def expect(mut self, byte: Int) raises:
        if self.peek() != byte:
            raise Error("invalid POSIX time-zone separator")
        self.position += 1

    def number(mut self, maximum: Int) raises -> Int:
        var start = self.position
        var value = 0
        while self.peek() >= 48 and self.peek() <= 57:
            var digit = self.peek() - 48
            if value > (maximum - digit) // 10:
                raise Error("POSIX time-zone number is out of range")
            value = value * 10 + digit
            self.position += 1
        if self.position == start or value > maximum:
            raise Error("invalid POSIX time-zone number")
        return value

    def name(mut self) raises -> String:
        var quoted = self.peek() == 60
        if quoted:
            self.position += 1
        var start = self.position
        while True:
            var byte = self.peek()
            var allowed = (65 <= byte <= 90 or 97 <= byte <= 122)
            if quoted:
                allowed = allowed or 48 <= byte <= 57 or byte == 43 or byte == 45
            if not allowed:
                break
            self.position += 1
        if self.position - start < 3:
            raise Error("POSIX time-zone name is too short")
        var name = String(self.text[byte=start:self.position])
        if quoted:
            self.expect(62)
        return name^

    def clock(mut self, maximum_hour: Int) raises -> Int:
        var sign = 1
        if self.peek() == 45 or self.peek() == 43:
            if self.peek() == 45:
                sign = -1
            self.position += 1
        var hour = self.number(maximum_hour)
        var minute = 0
        var second = 0
        if self.peek() == 58:
            self.position += 1
            minute = self.number(59)
            if self.peek() == 58:
                self.position += 1
                second = self.number(59)
        return sign * (hour * 3600 + minute * 60 + second)

    def rule(mut self) raises -> TransitionRule:
        var kind = 1
        var day = 0
        var month = 0
        var week = 0
        var weekday = 0
        if self.peek() == 74:
            self.position += 1
            kind = 0
            day = self.number(365)
            if day < 1:
                raise Error("invalid Julian transition day")
        elif self.peek() == 77:
            self.position += 1
            kind = 2
            month = self.number(12)
            self.expect(46)
            week = self.number(5)
            self.expect(46)
            weekday = self.number(6)
            if month < 1 or week < 1:
                raise Error("invalid monthly transition rule")
        else:
            day = self.number(365)
        var seconds = 7200
        if self.peek() == 47:
            self.position += 1
            if not self.extended and (self.peek() == 43 or self.peek() == 45):
                raise Error("signed transition time requires extended TZif rules")
            seconds = self.clock(167 if self.extended else 24)
        return TransitionRule(kind, day, month, week, weekday, seconds)


struct TimeZone:
    var transitions: List[Int]
    var transition_types: List[Int]
    var types: List[ZoneType]
    var future: Optional[PosixZone]

    def __init__(out self, bytes: List[UInt8]) raises:
        self.transitions = List[Int]()
        self.transition_types = List[Int]()
        self.types = List[ZoneType]()
        self.future = None
        var header = 0
        var width = 4
        var counts = zone_header(bytes, 0)
        var size = block_size(counts, width)
        var version = bytes[4]
        if version == 50 or version == 51 or version == 52:
            header = 44 + size
            counts = zone_header(bytes, header)
            if bytes[header + 4] != version:
                raise Error("inconsistent time-zone header versions")
            width = 8
            size = block_size(counts, width)
        elif version != 0:
            raise Error("unsupported time-zone data version")
        var start = header + 44
        var end = start + size
        if end > len(bytes):
            raise Error("truncated time-zone block")
        if counts[2] != 0:
            raise Error("leap-second time-zone data is not implemented")
        var time_count = counts[3]
        var type_count = counts[4]
        var char_count = counts[5]
        var indexes = start + time_count * width
        var definitions = indexes + time_count
        var names = definitions + type_count * 6
        for index in range(type_count):
            var offset = signed_be(bytes, definitions + index * 6, 4)
            var daylight = Int(bytes[definitions + index * 6 + 4])
            var name_index = Int(bytes[definitions + index * 6 + 5])
            if offset == -2147483648 or daylight > 1 or name_index >= char_count:
                raise Error("invalid time-zone type")
            var name_end = names + name_index
            while name_end < names + char_count and bytes[name_end] != 0:
                name_end += 1
            if name_end == names + char_count:
                raise Error("unterminated time-zone designation")
            var name = String(from_utf8=Span(bytes)[names + name_index:name_end])
            self.types.append(ZoneType(offset, name^))
        for index in range(time_count):
            var timestamp = signed_be(bytes, start + index * width, width)
            var type_index = Int(bytes[indexes + index])
            if type_index >= type_count or (index > 0 and timestamp <= self.transitions[index - 1]):
                raise Error("invalid time-zone transition")
            self.transitions.append(timestamp)
            self.transition_types.append(type_index)
        var indicators = names + char_count
        for index in range(counts[1]):
            if bytes[indicators + index] > 1:
                raise Error("invalid standard/wall time-zone indicator")
        for index in range(counts[0]):
            var indicator = bytes[indicators + counts[1] + index]
            if indicator > 1 or (indicator == 1 and (counts[1] == 0 or bytes[indicators + index] != 1)):
                raise Error("invalid UT/local time-zone indicator")
        if width == 8:
            var footer = String(from_utf8=Span(bytes)[end:])
            if not footer.startswith("\n") or not footer.endswith("\n"):
                raise Error("invalid time-zone footer")
            if "\x00" in footer or footer.count("\n") != 2:
                raise Error("invalid time-zone footer encoding")
            var rule = String(footer[byte=1:footer.byte_length() - 1])
            if rule:
                self.future = PosixZone(rule, extended=version >= 51)

    def at(self, epoch: Int) raises -> ZoneType:
        if self.future and (not self.transitions or epoch >= self.transitions[len(self.transitions) - 1]):
            return self.future.value().at(epoch)
        var selected = 0
        var low = 0
        var high = len(self.transitions)
        while low < high:
            var middle = low + (high - low) // 2
            if self.transitions[middle] <= epoch:
                low = middle + 1
            else:
                high = middle
        if low > 0:
            selected = self.transition_types[low - 1]
        return self.types[selected].copy()


def zone_header(bytes: List[UInt8], start: Int) raises -> List[Int]:
    if start < 0 or start > len(bytes) - 44:
        raise Error("truncated time-zone header")
    if bytes[start] != 84 or bytes[start + 1] != 90 or bytes[start + 2] != 105 or bytes[start + 3] != 102:
        raise Error("invalid time-zone magic")
    var counts = List[Int]()
    for index in range(6):
        var count = unsigned_be(bytes, start + 20 + index * 4, 4)
        if count > UInt64(len(bytes)):
            raise Error("time-zone count exceeds input size")
        counts.append(Int(count))
    if counts[4] < 1 or counts[4] > 256 or counts[5] < 1 or (counts[0] != 0 and counts[0] != counts[4]) or (counts[1] != 0 and counts[1] != counts[4]):
        raise Error("invalid time-zone header counts")
    return counts^


def block_size(counts: List[Int], width: Int) -> Int:
    return counts[3] * (width + 1) + counts[4] * 6 + counts[5] + counts[2] * (width + 4) + counts[0] + counts[1]


def two_digits(value: Int) -> String:
    return ("0" if value < 10 else "") + String(value)


def calendar_time(epoch: Int, zone: ZoneType) -> String:
    # These UTC bounds match Chrono 0.4.44's NaiveDate MIN and MAX.
    if epoch < -8_334_601_228_800 or epoch > 8_210_266_876_799:
        return String(epoch)
    var year, month, day, second = civil_fields(epoch + zone.offset)
    var year_text = String(abs(year))
    while year_text.byte_length() < 4:
        year_text = "0" + year_text
    if year < 0:
        year_text = "-" + year_text
    elif year > 9999:
        year_text = "+" + year_text
    var offset = abs(zone.offset)
    var zone_text = String("-" if zone.offset < 0 else "+") + two_digits(offset // 3600) + ":" + two_digits((offset // 60) % 60)
    if offset % 60:
        zone_text += ":" + two_digits(offset % 60)
    return year_text + "-" + two_digits(month) + "-" + two_digits(day) + " " + two_digits(second // 3600) + ":" + two_digits((second // 60) % 60) + ":" + two_digits(second % 60) + " " + zone_text


def format_local_epoch(epoch: Int) raises -> String:
    if epoch < -8_334_601_228_800 or epoch > 8_210_266_876_799:
        return String(epoch)
    var zone_name = getenv("TZ", ":/etc/localtime")
    if zone_name == "UTC" or zone_name == "UTC0" or zone_name == "" or zone_name == "GMT" or zone_name == "GMT0":
        return calendar_time(epoch, ZoneType(0, "GMT" if zone_name.startswith("GMT") else "UTC"))
    var file_only = zone_name.startswith(":")
    if file_only:
        var unprefixed = String(zone_name[byte=1:])
        zone_name = unprefixed^
    var path = zone_name if zone_name.startswith("/") else "/usr/share/zoneinfo/" + zone_name
    if not exists(path):
        if not file_only:
            try:
                var zone = PosixZone(zone_name, extended=False)
                return calendar_time(epoch, zone.at(epoch))
            except:
                pass
        # The release's local-time backend falls back to UTC for invalid TZ values.
        return calendar_time(epoch, ZoneType(0, "UTC"))
    with open(path, "r") as file:
        var bytes = file.read_bytes(1024 * 1024 + 1)
        if len(bytes) > 1024 * 1024:
            raise Error("time-zone data exceeds safe size limit")
        var zone = TimeZone(bytes)
        return calendar_time(epoch, zone.at(epoch))
