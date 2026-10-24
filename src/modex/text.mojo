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


def character_width(code: Int) raises -> Int:
    # Unicode 16.0 EastAsianWidth.txt defines the wide ranges used here.
    if (code == 0xAD or 0x300 <= code <= 0x36F or 0x483 <= code <= 0x489
        or 0x302A <= code <= 0x302F or code == 0x3099 or code == 0x309A):
        return 0
    if (0x20 <= code <= 0x7E or 0xA0 <= code <= 0x2FF
        or 0x370 <= code <= 0x482 or 0x48A <= code <= 0x52F
        or 0x1E00 <= code <= 0x1FFF):
        return 1
    if code == 0x303F:
        return 1
    if (0x3000 <= code <= 0x3029 or 0x3030 <= code <= 0x303E
        or 0x3041 <= code <= 0x3096 or 0x309B <= code <= 0x30FF
        or 0x31F0 <= code <= 0x31FF or 0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF or 0xAC00 <= code <= 0xD7A3
        or 0xF900 <= code <= 0xFAFF or 0xFF01 <= code <= 0xFF60
        or 0xFFE0 <= code <= 0xFFE6 or 0x20000 <= code <= 0x2FFFD
        or 0x30000 <= code <= 0x3FFFD):
        return 2
    # shortcut: other scripts, emoji sequences and controls need their remaining width rules before rendering.
    raise Error("session text rendering for this Unicode or control character is not implemented")


def text_width(value: String) raises -> Int:
    var width = 0
    for character in value.codepoints():
        width += character_width(Int(character))
    return width


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
    return fitted + String(" ") * (width - text_width(fitted))


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
        var cells = text_width(piece)
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
