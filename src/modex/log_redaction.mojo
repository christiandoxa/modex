"""Fail closed on common credential forms before rendering detached logs."""

from .text import is_whitespace


def redact_log_text(text: String) -> String:
    var output = String()
    var index = 0
    while index < text.byte_length():
        var scheme_length = authorization_scheme_length(text, index)
        if scheme_length and (index == 0 or not is_ascii_alphanumeric(Int(text.as_bytes()[index - 1]))) and index + scheme_length < text.byte_length() and is_ascii_space(Int(text.as_bytes()[index + scheme_length])):
            var token_start = index + scheme_length
            while token_start < text.byte_length() and is_ascii_space(Int(text.as_bytes()[token_start])):
                token_start += 1
            var token_end = token_start
            while token_end < text.byte_length() and not is_secret_end(Int(text.as_bytes()[token_end])):
                token_end += 1
            if token_end > token_start:
                output += text[byte=index:token_start] + "<redacted>"
                index = token_end
                continue
        var api_length = api_prefix_length(text, index)
        if api_length and (index == 0 or not is_ascii_alphanumeric(Int(text.as_bytes()[index - 1]))):
            var token_end = index + api_length
            while token_end < text.byte_length() and is_secret_byte(Int(text.as_bytes()[token_end])):
                token_end += 1
            if token_end >= index + api_length + 8:
                output += canonical_api_prefix(text, index, api_length) + "<redacted>"
                index = token_end
                continue
        if text[byte=index:].startswith("Cookie: ") or text[byte=index:].startswith("cookie: "):
            output += text[byte=index:index + 8] + "<redacted>"
            index += 8
            while index < text.byte_length() and text.as_bytes()[index] != 10:
                index += 1
            continue
        if sensitive_assignment(text, index):
            var assignment_start = index
            var value_start = index
            while value_start < text.byte_length() and text.as_bytes()[value_start] != 61 and text.as_bytes()[value_start] != 58:
                value_start += 1
            if value_start < text.byte_length():
                value_start += 1
                output += text[byte=index:value_start]
                index = value_start
                var whitespace_start = index
                while index < text.byte_length():
                    var width = whitespace_width(text, index)
                    if not width:
                        break
                    index += width
                output += text[byte=whitespace_start:index]
                if assignment_has_cookie_key(text, assignment_start):
                    while index < text.byte_length() and text.as_bytes()[index] != 10:
                        index += 1
                    output += "<redacted>"
                    continue
                if index < text.byte_length() and (text.as_bytes()[index] == 34 or text.as_bytes()[index] == 39):
                    var quote = Int(text.as_bytes()[index])
                    output += chr(quote)
                    index += 1
                    while index < text.byte_length() and Int(text.as_bytes()[index]) != quote:
                        if text.as_bytes()[index] == 92 and index + 1 < text.byte_length():
                            index += 2
                        else:
                            index += 1
                    if index < text.byte_length():
                        index += 1
                    output += "<redacted>" + chr(quote)
                    continue
                var scheme_length = authorization_scheme_length(text, index)
                if scheme_length and index + scheme_length < text.byte_length() and is_ascii_space(Int(text.as_bytes()[index + scheme_length])):
                    var token_start = index + scheme_length
                    while token_start < text.byte_length() and is_ascii_space(Int(text.as_bytes()[token_start])):
                        token_start += 1
                    var token_end = token_start
                    while token_end < text.byte_length() and not is_secret_end(Int(text.as_bytes()[token_end])):
                        token_end += 1
                    if token_end > token_start:
                        output += text[byte=index:token_start] + "<redacted>"
                        index = token_end
                        continue
                while index < text.byte_length() and not is_secret_end(Int(text.as_bytes()[index])):
                    index += 1
                output += "<redacted>"
                continue
        var width = utf8_character_width(Int(text.as_bytes()[index]))
        output += text[byte=index:min(index + width, text.byte_length())]
        index += width
    return output^


def api_prefix_length(text: String, index: Int) -> Int:
    if starts_ascii_case_insensitive(text, index, "sk-proj-") or starts_ascii_case_insensitive(text, index, "sk-live-"):
        return 8
    if starts_ascii_case_insensitive(text, index, "sk-ant-"):
        return 7
    if starts_ascii_case_insensitive(text, index, "sk_test_") or starts_ascii_case_insensitive(text, index, "sk_live_"):
        return 8
    if starts_ascii_case_insensitive(text, index, "sk-") or starts_ascii_case_insensitive(text, index, "sk_"):
        return 3
    return 0


def canonical_api_prefix(text: String, index: Int, length: Int) -> String:
    if starts_ascii_case_insensitive(text, index, "sk-live-"):
        return "sk-live-"
    if starts_ascii_case_insensitive(text, index, "sk_test_"):
        return "sk_test_"
    if starts_ascii_case_insensitive(text, index, "sk_live_"):
        return "sk_live_"
    if length == 7:
        return "sk-ant-"
    if starts_ascii_case_insensitive(text, index, "sk-proj-"):
        return "sk-proj-"
    if starts_ascii_case_insensitive(text, index, "sk_"):
        return "sk_"
    return "sk-"


def sensitive_assignment(text: String, start: Int) -> Bool:
    if start > 0 and is_key_byte(Int(text.as_bytes()[start - 1])):
        return False
    var end = start
    while end < text.byte_length() and is_key_byte(Int(text.as_bytes()[end])):
        end += 1
    if end == start:
        return False
    var key = String(text[byte=start:end]).lower()
    if end < text.byte_length() and (text.as_bytes()[end] == 34 or text.as_bytes()[end] == 39):
        end += 1
    while end < text.byte_length():
        var width = whitespace_width(text, end)
        if not width:
            break
        end += width
    if end < text.byte_length() and (text.as_bytes()[end] == 61 or text.as_bytes()[end] == 58):
        var normalized = String()
        for value in key.as_bytes():
            if is_ascii_alphanumeric(Int(value)):
                normalized += chr(Int(value))
        return contains_key(normalized, "authorization") or contains_key(normalized, "apikey") or contains_key(normalized, "authkey") or contains_key(normalized, "cookie") or contains_key(normalized, "token") or contains_key(normalized, "secret") or contains_key(normalized, "password") or contains_key(normalized, "credential") or contains_key(normalized, "email") or contains_key(normalized, "githublogin") or contains_key(normalized, "profilearn") or contains_key(normalized, "profilenameupstream") or contains_key(normalized, "starturl") or contains_key(normalized, "accountid")
    return False


def contains_key(key: String, part: String) -> Bool:
    return key.find(part) >= 0


def assignment_has_cookie_key(text: String, start: Int) -> Bool:
    var end = start
    while end < text.byte_length() and is_key_byte(Int(text.as_bytes()[end])):
        end += 1
    var key = String(text[byte=start:end]).lower()
    var normalized = String()
    for value in key.as_bytes():
        if is_ascii_alphanumeric(Int(value)):
            normalized += chr(Int(value))
    return contains_key(normalized, "cookie")


def authorization_scheme_length(text: String, index: Int) -> Int:
    if starts_ascii_case_insensitive(text, index, "Bearer"):
        return 6
    if starts_ascii_case_insensitive(text, index, "Basic"):
        return 5
    if starts_ascii_case_insensitive(text, index, "Token"):
        return 5
    return 0


def starts_ascii_case_insensitive(text: String, index: Int, prefix: String) -> Bool:
    if index + prefix.byte_length() > text.byte_length():
        return False
    for offset in range(prefix.byte_length()):
        var value = Int(text.as_bytes()[index + offset])
        var expected = Int(prefix.as_bytes()[offset])
        if 65 <= value <= 90:
            value += 32
        if 65 <= expected <= 90:
            expected += 32
        if value != expected:
            return False
    return True


def is_key_byte(value: Int) -> Bool:
    return 48 <= value <= 57 or 65 <= value <= 90 or 97 <= value <= 122 or value == 95 or value == 45


def is_secret_byte(value: Int) -> Bool:
    return is_ascii_alphanumeric(value) or value == 46 or value == 95 or value == 37 or value == 43 or value == 45 or value == 64


def is_secret_end(value: Int) -> Bool:
    return is_ascii_space(value) or value == 34 or value == 39 or value == 44 or value == 125 or value == 93 or value == 41 or value == 59 or value == 38


def is_ascii_alphanumeric(value: Int) -> Bool:
    return 48 <= value <= 57 or 65 <= value <= 90 or 97 <= value <= 122


def is_ascii_space(value: Int) -> Bool:
    return value == 32 or value == 9 or value == 10 or value == 11 or value == 12 or value == 13


def utf8_character_width(first: Int) -> Int:
    if first >= 240:
        return 4
    if first >= 224:
        return 3
    if first >= 194:
        return 2
    return 1


def whitespace_width(text: String, index: Int) -> Int:
    for character in text[byte=index:].codepoints():
        var code = Int(character)
        return chr(code).byte_length() if is_whitespace(code) else 0
    return 0
