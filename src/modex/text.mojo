"""Text rules required by the frozen Rust-facing compatibility contracts."""

from std.collections import List
from std.os import getenv

from .unicode_width import character_width, text_width


def unsigned_value(text: String) raises -> UInt64:
    var bytes = text.as_bytes()
    var position = 1 if text.startswith("+") else 0
    if position == len(bytes):
        raise Error("invalid digit found in string" if position else "cannot parse integer from empty string")
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


def ascii_lower(value: String) -> String:
    var result = String()
    for character in value.codepoints():
        var code = Int(character)
        result += chr(code + 32 if 65 <= code <= 90 else code)
    return result^


def cli_width() raises -> Int:
    var width: UInt64
    try:
        width = unsigned_value(trim_text(getenv("PRODEX_TERM_COLUMNS", "")))
    except:
        return 110
    if width > UInt64(Int.MAX):
        raise Error("session text width exceeds the supported range")
    return Int(width) if width else 110


def fit_cell(value: String, width: Int) raises -> String:
    if width == 0:
        return ""
    if text_width(value) <= width:
        return value
    if width <= 3:
        return String(".") * width
    var output = String()
    var used = 0
    for character in value.codepoints():
        var cells = character_width(Int(character))
        if used + cells > width - 3:
            break
        output += chr(Int(character))
        used += cells
    return output + "..."


def pad_cell(value: String, width: Int) raises -> String:
    var fitted = fit_cell(value, width)
    return fitted + String(" ") * max(0, width - text_width(fitted))


def section_header(title: String, width: Int) raises -> String:
    var prefix = String("[ ") + title + " ] "
    var visible = text_width(prefix)
    if width <= visible:
        return fit_cell(prefix, width)
    return prefix + String("=") * (width - visible)


def wrap_text(value: String, width: Int) raises -> List[String]:
    var paragraphs = value.split("\n")
    var lines = List[String]()
    for index in range(len(paragraphs)):
        if index == len(paragraphs) - 1 and index > 0 and not paragraphs[index]:
            break
        lines.extend(wrap_paragraph(String(paragraphs[index]), width))
    return lines^


def wrap_paragraph(value: String, width: Int) raises -> List[String]:
    var words = List[String]()
    var word = String()
    for character in value.codepoints():
        if is_whitespace(Int(character)):
            if word:
                words.append(word^)
                word = ""
        else:
            word += chr(Int(character))
    if word:
        words.append(word^)
    var maximum = max(1, width)
    var pieces = List[String]()
    for word in words:
        var piece = String()
        var cells = 0
        for character in word.codepoints():
            var next_cells = character_width(Int(character))
            if piece and cells > 0 and cells + next_cells > maximum:
                pieces.append(piece^)
                piece = ""
                cells = 0
            piece += chr(Int(character))
            cells += next_cells
            if cells >= maximum:
                pieces.append(piece^)
                piece = ""
                cells = 0
        if piece:
            pieces.append(piece^)
    var lines = List[String]()
    var line = String()
    var used = 0
    for piece in pieces:
        var cells = 0
        for character in piece.codepoints():
            cells += character_width(Int(character))
        if line and used + 1 + cells > maximum:
            lines.append(line^)
            line = ""
            used = 0
        if line:
            line += " "
            used += 1
        line += piece
        used += cells
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
