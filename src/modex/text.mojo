"""Text rules required by the frozen Rust-facing compatibility contracts."""


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
