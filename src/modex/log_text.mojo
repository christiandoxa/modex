"""Transcript text visibility and safety projections."""

from .log_redaction import redact_log_text
from .text import is_whitespace


comptime SAFE_TEXT_MAX_BYTES = 65_536
comptime SAFE_TEXT_TRUNCATION = " …[truncated]"
comptime OPERATION_MAX_CHARS = 192
comptime TOOL_NAME_MAX_CHARS = 96
comptime BINARY_SAMPLE_MAX_CHARS = 4096


def safe_text(text: String) -> String:
    var redacted = redact_log_text(text)
    var normalized = String()
    for character in redacted.codepoints():
        var code = Int(character)
        if is_control(code) and code != 9 and code != 10 and code != 13:
            normalized += " "
        else:
            normalized += chr(code)
    if normalized.byte_length() <= SAFE_TEXT_MAX_BYTES:
        return normalized^
    var output = String()
    var used = 0
    var budget = SAFE_TEXT_MAX_BYTES - 16
    for character in normalized.codepoints():
        var value = chr(Int(character))
        if used + value.byte_length() > budget:
            break
        output += value
        used += value.byte_length()
    var truncated = output + SAFE_TEXT_TRUNCATION
    return truncated^


def visible_message(text: String) -> String:
    return visible_lines(text, False)


def visible_tool_output(text: String) -> String:
    var normalized = strip_ansi_and_newlines(text)
    return visible_lines(normalized, True)


def tool_name(text: String) -> String:
    var redacted = redact_log_text(text)
    var output = String()
    var count = 0
    for character in redacted.codepoints():
        if count == TOOL_NAME_MAX_CHARS:
            break
        var code = Int(character)
        if is_tool_name_byte(code):
            output += chr(code)
        else:
            output += "_"
        count += 1
    return "tool" if not output else output^


def operation_value(text: String) -> String:
    var redacted = redact_log_text(text)
    var output = String()
    var count = 0
    var visible = False
    var truncated = False
    for character in redacted.codepoints():
        var code = Int(character)
        if is_control(code):
            return ""
        if not is_whitespace(code):
            visible = True
        if count < OPERATION_MAX_CHARS:
            output += chr(code)
        else:
            truncated = True
        count += 1
    if not visible:
        return ""
    if truncated:
        output += "…"
    return output^


def visible_lines(text: String, tool: Bool) -> String:
    var source = text
    if tool:
        source = trim_unicode(text)
        if not source:
            return ""
        if source.find("\n") < 0 and binary_like(source, False):
            return ""

    var output = String()
    var line_start = 0
    var has_visible = False
    var last_blank = False
    for index in range(source.byte_length() + 1):
        if index < source.byte_length() and source.as_bytes()[index] != 10:
            continue
        var line_end = index
        var visible_end = trim_right_bytes(source, line_start, line_end)
        if visible_end == line_start:
            if has_visible and not last_blank:
                output += "\n"
                last_blank = True
        else:
            var line = String(source[byte=line_start:visible_end])
            if tool and binary_like(line, True):
                pass
            elif not tool and is_attachment_line(line):
                pass
            else:
                if has_visible:
                    output += "\n"
                output += line
                has_visible = True
                last_blank = False
        line_start = index + 1
    var visible_end = output.byte_length()
    while visible_end > 0 and output.as_bytes()[visible_end - 1] == 10:
        visible_end -= 1
    var result = String(output[byte=0:visible_end])
    return result^


def trim_right_bytes(text: String, start: Int, end: Int) -> Int:
    var offset = start
    var last_nonspace = start
    for character in text[byte=start:end].codepoints():
        var code = Int(character)
        var width = chr(code).byte_length()
        if not is_whitespace(code):
            last_nonspace = offset + width
        offset += width
    return last_nonspace


def trim_unicode(text: String) -> String:
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
    var trimmed = String(text[byte=start:end])
    return trimmed^


def is_attachment_line(line: String) -> Bool:
    return line.find("/.prodex/profiles/.prodex-overlay-") >= 0 and line.find("/attachments/") >= 0


def strip_ansi_and_newlines(text: String) -> String:
    var output = String()
    var bytes = text.as_bytes()
    var index = 0
    while index < text.byte_length():
        var value = Int(bytes[index])
        index += 1
        if value == 27:
            if index == text.byte_length():
                break
            var escape = Int(bytes[index])
            index += 1
            if escape == 91:
                while index < text.byte_length():
                    var part = Int(bytes[index])
                    index += 1
                    if 64 <= part <= 126:
                        break
            elif escape == 93:
                var previous = 0
                while index < text.byte_length():
                    var part = Int(bytes[index])
                    index += 1
                    if part == 7 or (previous == 27 and part == 92):
                        break
                    previous = part
            else:
                index += utf8_width(escape) - 1
            continue
        if value == 13:
            if index < text.byte_length() and bytes[index] == 10:
                index += 1
            output += "\n"
            continue
        var width = utf8_width(value)
        output += text[byte=index - 1:min(index - 1 + width, text.byte_length())]
        index += width - 1
    return output^


def binary_like(text: String, line: Bool) -> Bool:
    var suspicious = 0
    var replacements = 0
    var controls = 0
    var readable_ascii = 0
    var non_ascii = 0
    var whitespace = 0
    var total = 0
    for character in text.codepoints():
        if total == BINARY_SAMPLE_MAX_CHARS:
            break
        var code = Int(character)
        var space = is_whitespace(code)
        var control = is_control(code)
        var ascii = code <= 127
        var alnum = is_alphanumeric(code)
        var readable = ascii and (alnum or space or common_punctuation(code))
        var strange = code == 0xFFFD or (control and code != 10 and code != 13 and code != 9) or (not ascii and not alnum and not space and not common_punctuation(code))
        if strange:
            suspicious += 1
        if code == 0xFFFD:
            replacements += 1
        if control and code != 10 and code != 13 and code != 9:
            controls += 1
        if readable:
            readable_ascii += 1
        if not ascii:
            non_ascii += 1
        if space:
            whitespace += 1
        total += 1
    if total <= 0:
        return False
    if line:
        var mojibake = total >= 24 and non_ascii >= 8 and non_ascii * 100 >= total * 20 and readable_ascii * 100 <= total * 55 and whitespace * 6 <= total
        return replacements > 0 or controls > 0 or mojibake or suspicious * 5 >= total or suspicious >= 6
    return replacements >= 3 or controls > 0 or suspicious * 4 > total or suspicious >= 8


def common_punctuation(code: Int) -> Bool:
    return code == 46 or code == 44 or code == 58 or code == 59 or code == 33 or code == 63 or code == 45 or code == 95 or code == 47 or code == 92 or code == 40 or code == 41 or code == 91 or code == 93 or code == 123 or code == 125 or code == 60 or code == 62 or code == 34 or code == 39 or code == 64 or code == 35 or code == 36 or code == 37 or code == 94 or code == 38 or code == 42 or code == 43 or code == 61 or code == 124 or code == 126 or code == 96


def is_alphanumeric(code: Int) -> Bool:
    if 48 <= code <= 57 or 65 <= code <= 90 or 97 <= code <= 122:
        return True
    # shortcut: common Unicode letter and number blocks only; update when Mojo stdlib exposes Unicode categories.
    return 0x00C0 <= code <= 0x02FF or 0x0370 <= code <= 0x052F or 0x0531 <= code <= 0x0588 or 0x05D0 <= code <= 0x05EA or 0x0620 <= code <= 0x06FF or 0x0710 <= code <= 0x08FF or 0x0900 <= code <= 0x1FFF or 0x2C00 <= code <= 0x2DFF or 0x3040 <= code <= 0x30FF or 0x3100 <= code <= 0x312F or 0x3130 <= code <= 0x318F or 0x31A0 <= code <= 0x31BF or 0x3400 <= code <= 0x4DBF or 0x4E00 <= code <= 0x9FFF or 0xA000 <= code <= 0xA4CF or 0xAC00 <= code <= 0xD7AF or 0xF900 <= code <= 0xFAFF or 0xFF10 <= code <= 0xFF19 or 0xFF21 <= code <= 0xFF3A or 0xFF41 <= code <= 0xFF5A


def is_tool_name_byte(code: Int) -> Bool:
    return 48 <= code <= 57 or 65 <= code <= 90 or 97 <= code <= 122 or code == 95 or code == 45 or code == 46 or code == 58


def is_control(code: Int) -> Bool:
    return code <= 31 or 127 <= code <= 159


def utf8_width(first: Int) -> Int:
    if first >= 240:
        return 4
    if first >= 224:
        return 3
    if first >= 194:
        return 2
    return 1
