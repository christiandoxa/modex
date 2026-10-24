"""One-off native UCD audit; not part of the product build or runtime."""

from std.collections import List
from modex.unicode_properties import is_alphanumeric


def hex_value(value: StringSlice) raises -> Int:
    var result = 0
    for byte in value.as_bytes():
        var digit = Int(byte)
        if 48 <= digit <= 57:
            digit -= 48
        elif 65 <= digit <= 70:
            digit -= 55
        elif 97 <= digit <= 102:
            digit -= 87
        else:
            raise Error("invalid hexadecimal digit")
        result = result * 16 + digit
    return result


def set_range(mut values: List[UInt8], start: Int, end: Int):
    assert 0 <= start <= end <= 0x10FFFF
    for code in range(start, end + 1):
        if not (0xD800 <= code <= 0xDFFF):
            values[code] = 1


def main() raises:
    var selected = List[UInt8](length=0x110000, fill=0)
    var dcp = open("tests/fixtures/unicode17/DerivedCoreProperties.txt", "r")
    for line in dcp.read().split("\n"):
        var record = line.split("#", maxsplit=1)[0].strip()
        if not record:
            continue
        var fields = record.split(";")
        if len(fields) < 2 or String(fields[1].strip()) != "Alphabetic":
            continue
        var bounds = fields[0].strip().split("..")
        var start = hex_value(bounds[0])
        var end = start if len(bounds) == 1 else hex_value(bounds[1])
        set_range(selected, start, end)

    var data = open("tests/fixtures/unicode17/UnicodeData.txt", "r")
    var range_start = -1
    var range_numeric = False
    for line in data.read().split("\n"):
        if not line:
            continue
        var fields = line.split(";")
        var code = hex_value(fields[0])
        var name = String(fields[1])
        var category = String(fields[2])
        if name.endswith(", First>"):
            range_start = code
            range_numeric = category.startswith("N")
        elif name.endswith(", Last>"):
            assert range_start >= 0
            if range_numeric:
                set_range(selected, range_start, code)
            range_start = -1
            range_numeric = False
        elif category.startswith("N"):
            set_range(selected, code, code)
    assert range_start == -1

    var intervals = List[Int]()
    var code = 0
    var scalar_count = 0
    while code < 0x110000:
        if selected[code] == 0 or 0xD800 <= code <= 0xDFFF:
            code += 1
            continue
        var start = code
        scalar_count += 1
        while code + 1 < 0x110000 and selected[code + 1] != 0 and not (0xD7FF <= code < 0xE000):
            code += 1
            scalar_count += 1
        intervals.append(start)
        intervals.append(code)
        code += 1
    assert len(intervals) == 1688
    assert scalar_count == 149106
    for index in range(2, len(intervals), 2):
        assert intervals[index - 1] + 1 < intervals[index]
    for value in range(0x110000):
        assert is_alphanumeric(value) == (selected[value] != 0 and not (0xD800 <= value <= 0xDFFF))
    print("intervals:", len(intervals) // 2, "scalars:", scalar_count)
    for index in range(len(intervals)):
        if index % 8 == 0:
            print("    ", end="")
        print(String(intervals[index]), end="")
        if index % 2 == 0:
            print(", ", end="")
        else:
            print(",", end="")
            if index % 8 == 7 or index == len(intervals) - 1:
                print()
            else:
                print(" ", end="")
