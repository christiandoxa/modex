"""Native TOML 1.1 document parsing for Modex configuration."""

from std.collections import List, Span
from std.math import isfinite

comptime TOML_STRING = 0
comptime TOML_INTEGER = 1
comptime TOML_FLOAT = 2
comptime TOML_BOOLEAN = 3
comptime TOML_DATETIME = 4
comptime TOML_OFFSET_DATETIME = TOML_DATETIME
comptime TOML_ARRAY = 5
comptime TOML_TABLE = 6
comptime TOML_LOCAL_DATE = 7
comptime TOML_LOCAL_TIME = 8
comptime TOML_LOCAL_DATETIME = 9
comptime TOML_MAX_NESTING = 80


@fieldwise_init
struct TOMLNode(Copyable):
    var kind: Int
    var text: String
    var children: List[Int]
    var names: List[String]


struct TOMLDocument:
    var source: String
    var nodes: List[TOMLNode]
    var position: Int
    var root: Int
    var current: Int

    def __init__(out self, var source: String) raises:
        self.source = source^
        self.nodes = List[TOMLNode]()
        self.position = 0
        self.root = -1
        self.current = -1
        self.root = self._container(TOML_TABLE)
        self.current = self.root
        while True:
            self._space_and_comments(True)
            if self._peek() < 0:
                break
            if self._peek() == 91:
                self._header()
            else:
                var keys = self._key_path()
                self._space()
                self._expect(61)
                self._space()
                var value = self._value(0)
                self._insert_path(self.current, keys, value)
            self._space()
            if self._peek() == 35:
                self._comment()
            if self._peek() == 13:
                self.position += 1
                if self._peek() != 10:
                    raise Error("TOML newline must be LF or CRLF")
                self.position += 1
            elif self._peek() == 10:
                self.position += 1
            elif self._peek() >= 0:
                raise Error("expected end of TOML line")

    def get(self, parent: Int, name: StringSlice) -> Int:
        if parent < 0 or self.nodes[parent].kind != TOML_TABLE:
            return -1
        for i in range(len(self.nodes[parent].names) - 1, -1, -1):
            if self.nodes[parent].names[i] == name:
                return self.nodes[parent].children[i]
        return -1

    def string(self, index: Int) -> String:
        if index < 0 or self.nodes[index].kind != TOML_STRING:
            return ""
        return self.nodes[index].text

    def _container(mut self, kind: Int) -> Int:
        var index = len(self.nodes)
        self.nodes.append(TOMLNode(kind, String(), List[Int](), List[String]()))
        return index

    def _peek(self) -> Int:
        if self.position >= self.source.byte_length():
            return -1
        return Int(self.source.as_bytes()[self.position])

    def _space(mut self):
        while self._peek() == 32 or self._peek() == 9:
            self.position += 1

    def _space_and_comments(mut self, lines: Bool) raises:
        while True:
            self._space()
            if self._peek() == 35:
                self._comment()
            elif lines and self._peek() == 13:
                self.position += 1
                if self._peek() != 10:
                    raise Error("TOML newline must be LF or CRLF")
                self.position += 1
            elif lines and self._peek() == 10:
                self.position += 1
            else:
                break

    def _comment(mut self) raises:
        while self._peek() >= 0 and self._peek() != 10 and self._peek() != 13:
            if (self._peek() < 32 and self._peek() != 9) or self._peek() == 127:
                raise Error("control character in TOML comment")
            self.position += 1

    def _expect(mut self, byte: Int) raises:
        if self._peek() != byte:
            raise Error("invalid TOML syntax")
        self.position += 1

    def _key_path(mut self) raises -> List[String]:
        var keys = List[String]()
        keys.append(self._key())
        self._space()
        while self._peek() == 46:
            self.position += 1
            self._space()
            keys.append(self._key())
            if len(keys) > TOML_MAX_NESTING:
                raise Error("TOML nesting limit exceeded")
            self._space()
        return keys^

    def _key(mut self) raises -> String:
        if self._peek() == 34 or self._peek() == 39:
            return self._quoted(self._peek(), False)
        var start = self.position
        while True:
            var b = self._peek()
            if (65 <= b <= 90) or (97 <= b <= 122) or (48 <= b <= 57) or b == 95 or b == 45:
                self.position += 1
            else:
                break
        if self.position == start:
            raise Error("invalid TOML key")
        return String(self.source[byte=start:self.position])

    def _header(mut self) raises:
        self._expect(91)
        var array = self._peek() == 91
        if array:
            self.position += 1
        self._space()
        var keys = self._key_path()
        self._space()
        self._expect(93)
        if array:
            self._expect(93)
        var target = self.root
        for i in range(len(keys)):
            var name = keys[i]
            var found = self.get(target, name)
            if found < 0:
                if array and i == len(keys) - 1:
                    var list = self._container(TOML_ARRAY)
                    self.nodes[list].text = "array_table"
                    self._put(target, name, list)
                    var table = self._container(TOML_TABLE)
                    self.nodes[table].text = "explicit"
                    self.nodes[list].children.append(table)
                    target = table
                else:
                    var table = self._container(TOML_TABLE)
                    if i == len(keys) - 1:
                        self.nodes[table].text = "explicit"
                    self._put(target, name, table)
                    target = table
            elif i == len(keys) - 1 and array:
                if self.nodes[found].kind != TOML_ARRAY or self.nodes[found].text != "array_table":
                    raise Error("TOML array table conflicts with a value")
                var table = self._container(TOML_TABLE)
                self.nodes[table].text = "explicit"
                self.nodes[found].children.append(table)
                target = table
            else:
                if self.nodes[found].kind == TOML_ARRAY and self.nodes[found].text == "array_table" and i < len(keys) - 1:
                    if len(self.nodes[found].children) == 0 or self.nodes[self.nodes[found].children[len(self.nodes[found].children) - 1]].kind != TOML_TABLE:
                        raise Error("TOML array table has no current table")
                    found = self.nodes[found].children[len(self.nodes[found].children) - 1]
                if self.nodes[found].kind != TOML_TABLE:
                    raise Error("TOML table conflicts with a value")
                if self.nodes[found].text == "inline":
                    raise Error("TOML inline table cannot be extended")
                if i == len(keys) - 1:
                    if self.nodes[found].text == "explicit" or self.nodes[found].text == "dotted":
                        raise Error("duplicate TOML table")
                    self.nodes[found].text = "explicit"
                target = found
        self.current = target

    def _put(mut self, table: Int, name: String, value: Int) raises:
        if self.get(table, name) >= 0:
            raise Error("duplicate TOML key")
        self.nodes[table].names.append(name.copy())
        self.nodes[table].children.append(value)

    def _seal_inline(mut self, table: Int):
        self.nodes[table].text = "inline"
        var descendants = self.nodes[table].children.copy()
        for child in descendants:
            self._seal_inline_value(child)

    def _seal_inline_value(mut self, node: Int):
        if self.nodes[node].kind == TOML_TABLE:
            self._seal_inline(node)
        elif self.nodes[node].kind == TOML_ARRAY:
            var descendants = self.nodes[node].children.copy()
            for child in descendants:
                self._seal_inline_value(child)

    def _insert_path(mut self, table: Int, keys: List[String], value: Int) raises:
        var target = table
        for i in range(len(keys) - 1):
            var found = self.get(target, keys[i])
            if found < 0:
                var nested = self._container(TOML_TABLE)
                self.nodes[nested].text = "dotted"
                self._put(target, keys[i], nested)
                target = nested
            elif self.nodes[found].kind == TOML_TABLE:
                if self.nodes[found].text == "inline":
                    raise Error("TOML inline table cannot be extended")
                if self.nodes[found].text == "explicit":
                    raise Error("TOML dotted key cannot extend a header-defined table")
                self.nodes[found].text = "dotted"
                target = found
            else:
                raise Error("TOML dotted key conflicts with a value")
        self._put(target, keys[len(keys) - 1], value)

    def _value(mut self, depth: Int) raises -> Int:
        if depth > TOML_MAX_NESTING:
            raise Error("TOML nesting limit exceeded")
        var b = self._peek()
        if b == 34 or b == 39:
            var value = self._quoted(b, True)
            var node = self._container(TOML_STRING)
            self.nodes[node].text = value^
            return node
        if b == 91:
            self.position += 1
            var array = self._container(TOML_ARRAY)
            self._space_and_comments(True)
            while self._peek() != 93:
                var child = self._value(depth + 1)
                self.nodes[array].children.append(child)
                self._space_and_comments(True)
                if self._peek() == 93:
                    break
                self._expect(44)
                self._space_and_comments(True)
            self._expect(93)
            return array
        if b == 123:
            self.position += 1
            var table = self._container(TOML_TABLE)
            self._space_and_comments(True)
            while self._peek() != 125:
                var keys = self._key_path()
                self._space_and_comments(True)
                self._expect(61)
                self._space_and_comments(True)
                self._insert_path(table, keys, self._value(depth + 1))
                self._space_and_comments(True)
                if self._peek() == 125:
                    break
                self._expect(44)
                self._space_and_comments(True)
            self._expect(125)
            self._seal_inline(table)
            return table
        return self._scalar()

    def _quoted(mut self, quote: Int, allow_multiline: Bool) raises -> String:
        self._expect(quote)
        var triple = allow_multiline and self._peek() == quote and self.position + 1 < self.source.byte_length() and Int(self.source.as_bytes()[self.position + 1]) == quote
        if triple:
            self.position += 1
            self._expect(quote)
            if self._peek() == 10 or self._peek() == 13:
                if self._peek() == 13:
                    self.position += 1
                    if self._peek() != 10: raise Error("invalid TOML multiline string newline")
                if self._peek() == 10: self.position += 1
        var out = List[UInt8]()
        while self._peek() >= 0:
            var b = self._peek()
            self.position += 1
            if b == quote:
                if not triple:
                    return String(from_utf8=Span(out))
                var quotes = 1
                while quotes < 5 and self._peek() == quote:
                    self.position += 1
                    quotes += 1
                if quotes >= 3:
                    for _ in range(quotes - 3): out.append(UInt8(quote))
                    return String(from_utf8=Span(out))
                for _ in range(quotes): out.append(UInt8(quote))
                continue
            if quote == 34 and b == 92:
                var e = self._peek()
                self.position += 1
                if e == 110: out.append(10)
                elif e == 114: out.append(13)
                elif e == 116: out.append(9)
                elif e == 98: out.append(8)
                elif e == 102: out.append(12)
                elif e == 101: out.append(27)
                elif e == 34 or e == 92: out.append(UInt8(e))
                elif e == 120 or e == 117 or e == 85:
                    var digits = 2 if e == 120 else 4 if e == 117 else 8
                    var codepoint = 0
                    for _ in range(digits):
                        var h = self._peek()
                        self.position += 1
                        var digit = -1
                        if 48 <= h <= 57: digit = h - 48
                        elif 65 <= h <= 70: digit = h - 55
                        elif 97 <= h <= 102: digit = h - 87
                        if digit < 0: raise Error("invalid TOML Unicode escape")
                        codepoint = codepoint * 16 + digit
                    if codepoint > 0x10FFFF or (0xD800 <= codepoint <= 0xDFFF):
                        raise Error("invalid TOML Unicode scalar")
                    out.extend(chr(codepoint).as_bytes())
                elif triple and (e == 32 or e == 9):
                    while self._peek() == 32 or self._peek() == 9: self.position += 1
                    if self._peek() == 13:
                        self.position += 1
                        if self._peek() != 10: raise Error("invalid TOML line continuation")
                        self.position += 1
                    elif self._peek() == 10:
                        self.position += 1
                    else:
                        raise Error("invalid TOML line continuation")
                    self._continuation_whitespace()
                elif triple and (e == 10 or e == 13):
                    if e == 13:
                        if self._peek() != 10: raise Error("invalid TOML line continuation")
                        self.position += 1
                    self._continuation_whitespace()
                else: raise Error("invalid TOML string escape")
            else:
                if not triple and (b == 10 or b == 13):
                    raise Error("newline in TOML basic string")
                if b == 13:
                    if not triple or self._peek() != 10:
                        raise Error("invalid carriage return in TOML string")
                    self.position += 1
                    out.append(10)
                    continue
                if (b < 32 and b != 9 and not (triple and b == 10)) or b == 127:
                    raise Error("control character in TOML string")
                out.append(UInt8(b))
        raise Error("unterminated TOML string")

    def _scalar(mut self) raises -> Int:
        var start = self.position
        while self._peek() >= 0 and self._peek() != 32 and self._peek() != 9 and self._peek() != 10 and self._peek() != 13 and self._peek() != 44 and self._peek() != 93 and self._peek() != 125 and self._peek() != 35:
            self.position += 1
        if self.position - start == 10 and self._peek() == 32 and self.position + 1 < self.source.byte_length() and 48 <= Int(self.source.as_bytes()[self.position + 1]) <= 57:
            self.position += 1
            while self._peek() >= 0 and self._peek() != 32 and self._peek() != 9 and self._peek() != 10 and self._peek() != 13 and self._peek() != 44 and self._peek() != 93 and self._peek() != 125 and self._peek() != 35:
                self.position += 1
        if self.position == start:
            raise Error("expected TOML value")
        var text = String(self.source[byte=start:self.position])
        var kind = TOML_INTEGER
        var based_integer = text.startswith("0x") or text.startswith("0o") or text.startswith("0b")
        if text == "true" or text == "false":
            kind = TOML_BOOLEAN
        elif self._looks_datetime(text):
            kind = self._validate_datetime(text)
        elif text == "inf" or text == "+inf" or text == "-inf" or text == "nan" or text == "+nan" or text == "-nan" or (not based_integer and (text.find(".") >= 0 or text.find("e") >= 0 or text.find("E") >= 0)):
            self._validate_float(text)
            if text != "inf" and text != "+inf" and text != "-inf" and text != "nan" and text != "+nan" and text != "-nan":
                var normalized = List[UInt8]()
                for b in text.as_bytes():
                    if Int(b) != 95: normalized.append(b)
                if not isfinite(atof(String(from_utf8=Span(normalized)))):
                    raise Error("TOML float is outside binary64 range")
            kind = TOML_FLOAT
        else:
            self._validate_integer(text)
        var node = self._container(kind)
        self.nodes[node].text = text^
        return node

    def _continuation_whitespace(mut self) raises:
        while self._peek() == 32 or self._peek() == 9 or self._peek() == 10 or self._peek() == 13:
            if self._peek() == 13:
                self.position += 1
                if self._peek() != 10:
                    raise Error("TOML newline must be LF or CRLF")
            self.position += 1

    def _validate_integer(mut self, text: String) raises:
        var bytes = text.as_bytes()
        var start = 0
        if Int(bytes[0]) == 43 or Int(bytes[0]) == 45:
            start = 1
        var radix = 10
        if len(bytes) >= start + 2 and Int(bytes[start]) == 48:
            var marker = Int(bytes[start + 1])
            if marker == 120: radix = 16
            elif marker == 111: radix = 8
            elif marker == 98: radix = 2
            if radix != 10:
                if Int(bytes[0]) == 43 or Int(bytes[0]) == 45: raise Error("signed TOML base integer is invalid")
                start += 2
        if start == len(bytes):
            raise Error("invalid TOML integer")
        var digit_seen = False
        var previous_digit = False
        for i in range(start, len(bytes)):
            var b = Int(bytes[i])
            var digit = (48 <= b <= 57 and b - 48 < radix) or (radix == 16 and ((65 <= b <= 70) or (97 <= b <= 102)))
            if digit:
                digit_seen = True
                previous_digit = True
            elif b == 95 and previous_digit and i + 1 < len(bytes):
                previous_digit = False
            else:
                raise Error("invalid TOML integer")
        if not digit_seen or not previous_digit or (radix == 10 and len(bytes) - start > 1 and Int(bytes[start]) == 48):
            raise Error("invalid TOML integer")
        if radix == 10:
            var digits = String()
            for i in range(start, len(bytes)):
                if Int(bytes[i]) != 95:
                    digits += String(from_utf8=Span(bytes[i:i + 1]))
            var limit = "9223372036854775808" if Int(bytes[0]) == 45 else "18446744073709551615"
            if digits.byte_length() > limit.byte_length() or (digits.byte_length() == limit.byte_length() and digits > limit):
                raise Error("TOML integer is outside supported range")
        else:
            var value: UInt64 = 0
            for i in range(start, len(bytes)):
                var b = Int(bytes[i])
                if b == 95: continue
                var digit = b - 48 if 48 <= b <= 57 else b - 87 if b >= 97 else b - 55
                var max_value: UInt64 = 18446744073709551615
                if value > max_value // UInt64(radix) or value * UInt64(radix) > max_value - UInt64(digit):
                    raise Error("TOML integer is outside supported range")
                value = value * UInt64(radix) + UInt64(digit)

    def _valid_digit_run(self, text: String, start: Int, end: Int, no_leading_zero: Bool) -> Bool:
        if start >= end: return False
        var previous = False
        var digit_count = 0
        var first = -1
        for i in range(start, end):
            var b = Int(text.as_bytes()[i])
            if 48 <= b <= 57:
                if digit_count == 0: first = b
                digit_count += 1
                previous = True
            elif b == 95 and previous and i + 1 < end and 48 <= Int(text.as_bytes()[i + 1]) <= 57:
                previous = False
            else:
                return False
        return previous and digit_count > 0 and (not no_leading_zero or digit_count == 1 or first != 48)

    def _int_at(self, text: String, start: Int, count: Int) raises -> Int:
        if start < 0 or start + count > text.byte_length():
            raise Error("truncated TOML date-time")
        var value = 0
        for i in range(start, start + count):
            if i >= text.byte_length(): raise Error("invalid TOML date-time")
            var b = Int(text.as_bytes()[i])
            if b < 48 or b > 57: raise Error("invalid TOML date-time")
            value = value * 10 + b - 48
        return value

    def _validate_date(mut self, text: String, start: Int) raises -> Int:
        var year = self._int_at(text, start, 4)
        if Int(text.as_bytes()[start + 4]) != 45 or Int(text.as_bytes()[start + 7]) != 45: raise Error("invalid TOML date")
        var month = self._int_at(text, start + 5, 2)
        var day = self._int_at(text, start + 8, 2)
        if month < 1 or month > 12: raise Error("invalid TOML date")
        var days = 31
        if month == 4 or month == 6 or month == 9 or month == 11: days = 30
        elif month == 2:
            days = 28
            if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0): days = 29
        if day < 1 or day > days: raise Error("invalid TOML date")
        return start + 10

    def _validate_time(mut self, text: String, start: Int) raises -> Int:
        var hour = self._int_at(text, start, 2)
        if start + 2 >= text.byte_length(): raise Error("truncated TOML time")
        if Int(text.as_bytes()[start + 2]) != 58: raise Error("invalid TOML time")
        var minute = self._int_at(text, start + 3, 2)
        var pos = start + 5
        var second = 0
        var has_seconds = False
        if pos < text.byte_length() and Int(text.as_bytes()[pos]) == 58:
            second = self._int_at(text, pos + 1, 2)
            pos += 3
            has_seconds = True
        if hour > 23 or minute > 59 or second > 60 or (second == 60 and minute != 59): raise Error("invalid TOML time")
        if pos < text.byte_length() and Int(text.as_bytes()[pos]) == 46:
            if not has_seconds: raise Error("invalid TOML time fraction")
            var digits_start = pos + 1
            pos = digits_start
            while pos < text.byte_length() and 48 <= Int(text.as_bytes()[pos]) <= 57: pos += 1
            if pos == digits_start: raise Error("invalid TOML time fraction")
        return pos

    def _looks_datetime(self, text: String) -> Bool:
        if text.byte_length() >= 10 and Int(text.as_bytes()[4]) == 45 and Int(text.as_bytes()[7]) == 45: return True
        return text.byte_length() >= 5 and Int(text.as_bytes()[2]) == 58

    def _validate_datetime(mut self, text: String) raises -> Int:
        var has_date = text.byte_length() >= 10 and Int(text.as_bytes()[4]) == 45 and Int(text.as_bytes()[7]) == 45
        var pos: Int
        if has_date:
            pos = self._validate_date(text, 0)
            if pos == text.byte_length(): return TOML_LOCAL_DATE
            if Int(text.as_bytes()[pos]) != 84 and Int(text.as_bytes()[pos]) != 116 and Int(text.as_bytes()[pos]) != 32: raise Error("invalid TOML date-time separator")
            pos = self._validate_time(text, pos + 1)
        else:
            pos = self._validate_time(text, 0)
        if pos == text.byte_length(): return TOML_LOCAL_DATETIME if has_date else TOML_LOCAL_TIME
        if not has_date: raise Error("TOML local time cannot have an offset")
        if Int(text.as_bytes()[pos]) == 90 or Int(text.as_bytes()[pos]) == 122:
            pos += 1
        elif Int(text.as_bytes()[pos]) == 43 or Int(text.as_bytes()[pos]) == 45:
            var hour = self._int_at(text, pos + 1, 2)
            if pos + 3 >= text.byte_length(): raise Error("invalid TOML offset")
            if Int(text.as_bytes()[pos + 3]) != 58: raise Error("invalid TOML offset")
            var minute = self._int_at(text, pos + 4, 2)
            if hour > 23 or minute > 59: raise Error("invalid TOML offset")
            pos += 6
        else:
            raise Error("invalid TOML date-time offset")
        if pos != text.byte_length(): raise Error("invalid TOML date-time suffix")
        return TOML_DATETIME

    def _validate_float(mut self, text: String) raises:
        if text == "inf" or text == "+inf" or text == "-inf" or text == "nan" or text == "+nan" or text == "-nan": return
        var start = 1 if Int(text.as_bytes()[0]) == 43 or Int(text.as_bytes()[0]) == 45 else 0
        var exponent = -1
        for i in range(start, text.byte_length()):
            var byte = Int(text.as_bytes()[i])
            if byte == 101 or byte == 69:
                if exponent >= 0: raise Error("invalid TOML float")
                exponent = i
        var mantissa_end = exponent if exponent >= 0 else text.byte_length()
        var dot = -1
        for i in range(start, mantissa_end):
            if Int(text.as_bytes()[i]) == 46:
                if dot >= 0: raise Error("invalid TOML float")
                dot = i
        var integer_end = dot if dot >= 0 else mantissa_end
        if not self._valid_digit_run(text, start, integer_end, True):
            raise Error("invalid TOML float")
        if dot >= 0 and not self._valid_digit_run(text, dot + 1, mantissa_end, False):
            raise Error("invalid TOML float")
        if exponent >= 0:
            var exp_start = exponent + 1
            if exp_start < text.byte_length() and (Int(text.as_bytes()[exp_start]) == 43 or Int(text.as_bytes()[exp_start]) == 45): exp_start += 1
            if not self._valid_digit_run(text, exp_start, text.byte_length(), False):
                raise Error("invalid TOML float")
        elif dot < 0:
            raise Error("invalid TOML float")
