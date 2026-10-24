"""Text rules required by the frozen Rust-facing compatibility contracts."""

from std.collections import List
from std.os import getenv


def unsigned_value(text: String) raises -> UInt64:
    var bytes = text.as_bytes()
    var position = 1 if text.startswith("+") else 0
    if position == len(bytes):
        raise Error("cannot parse integer from empty string")
    var result = UInt64(0)
    while position < len(bytes):
        var byte = bytes[position]
        if byte < 48 or byte > 57:
            raise Error("invalid digit found in string")
        var digit = UInt64(byte - 48)
        if result > (UInt64.MAX - digit) // 10:
            raise Error("number too large to fit in target type")
        result = result * 10 + digit
        position += 1
    return result


def is_whitespace(code: Int) -> Bool:
    return 9 <= code <= 13 or code == 32 or code == 0x85 or code == 0xA0 or code == 0x1680 or 0x2000 <= code <= 0x200A or code == 0x2028 or code == 0x2029 or code == 0x202F or code == 0x205F or code == 0x3000


def trim_text(text: StringSlice) -> String:
    var start = -1
    var end = 0
    var offset = 0
    for character in text.codepoints():
        var code = Int(character)
        var width = chr(code).byte_length()
        if not is_whitespace(code):
            if start < 0:
                start = offset
            end = offset + width
        offset += width
    if start < 0:
        return ""
    return String(text[byte=start:end])


def cli_width() raises -> Int:
    var width: UInt64
    try:
        width = unsigned_value(trim_text(getenv("PRODEX_TERM_COLUMNS", "")))
    except:
        return 110
    if width > UInt64(Int.MAX):
        raise Error("session text width exceeds the supported range")
    return Int(width) if width else 110


def ascii_width(value: String) raises -> Int:
    # shortcut: only printable ASCII cell widths are implemented; add Unicode metrics before rendering other text.
    for byte in value.as_bytes():
        if byte < 32 or byte > 126:
            raise Error("session text rendering for Unicode or control characters is not implemented")
    return value.byte_length()


def fit_cell(value: String, width: Int) raises -> String:
    if ascii_width(value) <= width:
        return value
    if width <= 3:
        return String(".") * width
    return String(value[byte=:width - 3]) + "..."


def pad_cell(value: String, width: Int) raises -> String:
    var fitted = fit_cell(value, width)
    return fitted + String(" ") * (width - fitted.byte_length())


def section_header(title: String, width: Int) raises -> String:
    var prefix = String("[ ") + title + " ] "
    if width <= ascii_width(prefix):
        return fit_cell(prefix, width)
    return prefix + String("=") * (width - prefix.byte_length())


def wrap_text(value: String, width: Int) raises -> List[String]:
    if ascii_width(value) == 0:
        return [String("")]
    var lines = List[String]()
    var line = String()
    for word in value.split(" "):
        var offset = 0
        while offset < word.byte_length():
            var end = min(offset + width, word.byte_length())
            var piece = String(word[byte=offset:end])
            if line and line.byte_length() + 1 + piece.byte_length() > width:
                lines.append(line^)
                line = ""
            if line:
                line += " "
            line += piece
            offset = end
    if line or not lines:
        lines.append(line^)
    return lines^


def status_panel(title: String, message: String, width: Int) raises -> String:
    var label_width = min(10, min(max(1, width - 20), max(1, width // 4)))
    var value_width = max(1, width - max(label_width, 7) - 1)
    var output = section_header(title, width)
    var lines = wrap_text(message, value_width)
    for index in range(len(lines)):
        output += "\n"
        if index == 0:
            output += "Status:" + String(" ") * max(0, label_width - 7)
        else:
            output += String(" ") * label_width
        output += " " + lines[index]
    return output^
