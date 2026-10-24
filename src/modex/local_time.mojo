"""Local epoch rendering using OS TZif data through official file APIs."""

from std.collections import List, Span
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


struct TimeZone:
    var transitions: List[Int]
    var transition_types: List[Int]
    var types: List[ZoneType]
    var needs_future_rules: Bool

    def __init__(out self, bytes: List[UInt8]) raises:
        self.transitions = List[Int]()
        self.transition_types = List[Int]()
        self.types = List[ZoneType]()
        self.needs_future_rules = False
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
            self.needs_future_rules = "," in footer

    def at(self, epoch: Int) raises -> ZoneType:
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
        # shortcut: recurring TZif footer rules remain a gap; reject future DST dates until those rules are implemented.
        if self.needs_future_rules and (not self.transitions or epoch > self.transitions[len(self.transitions) - 1]):
            raise Error("future recurring time-zone rules are not implemented")
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
    var local = epoch + zone.offset
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
    if zone_name.startswith(":"):
        var unprefixed = String(zone_name[byte=1:])
        zone_name = unprefixed^
    var path = zone_name if zone_name.startswith("/") else "/usr/share/zoneinfo/" + zone_name
    if not exists(path):
        raise Error("POSIX time-zone strings are not implemented")
    with open(path, "r") as file:
        var bytes = file.read_bytes(1024 * 1024 + 1)
        if len(bytes) > 1024 * 1024:
            raise Error("time-zone data exceeds safe size limit")
        var zone = TimeZone(bytes)
        return calendar_time(epoch, zone.at(epoch))
