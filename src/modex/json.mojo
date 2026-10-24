"""RFC 8259 JSON decoding without application dependencies."""

from std.collections import List, Span
from std.math import isfinite

comptime JSON_NULL = 0
comptime JSON_BOOL = 1
comptime JSON_NUMBER = 2
comptime JSON_STRING = 3
comptime JSON_ARRAY = 4
comptime JSON_OBJECT = 5


@fieldwise_init
struct JsonNode(Copyable):
    var kind: Int
    var text: String
    var children: List[Int]
    var names: List[String]


struct JsonDocument:
    var source: String
    var nodes: List[JsonNode]
    var position: Int
    var root: Int

    def __init__(out self, var source: String) raises:
        self.source = source^
        self.nodes = List[JsonNode]()
        self.position = 0
        self.root = -1
        self.root = self._value(0)
        self._whitespace()
        if self.position != self.source.byte_length():
            raise Error("trailing data after JSON value")

    def get(self, parent: Int, name: StringSlice) -> Int:
        if parent < 0 or self.nodes[parent].kind != JSON_OBJECT:
            return -1
        for index in range(len(self.nodes[parent].names) - 1, -1, -1):
            if self.nodes[parent].names[index] == name:
                return self.nodes[parent].children[index]
        return -1

    def string(self, index: Int) -> String:
        if index < 0 or self.nodes[index].kind != JSON_STRING:
            return ""
        return self.nodes[index].text

    def _peek(self) -> Int:
        if self.position >= self.source.byte_length():
            return -1
        return Int(self.source.as_bytes()[self.position])

    def _whitespace(mut self):
        while self._peek() == 32 or self._peek() == 9 or self._peek() == 10 or self._peek() == 13:
            self.position += 1

    def _expect(mut self, byte: Int) raises:
        if self._peek() != byte:
            raise Error("unexpected JSON token")
        self.position += 1

    def _hex4(mut self) raises -> Int:
        var value = 0
        for _ in range(4):
            var byte = self._peek()
            var digit = -1
            if 48 <= byte <= 57:
                digit = byte - 48
            elif 65 <= byte <= 70:
                digit = byte - 55
            elif 97 <= byte <= 102:
                digit = byte - 87
            if digit < 0:
                raise Error("invalid JSON Unicode escape")
            value = value * 16 + digit
            self.position += 1
        return value

    def _string(mut self) raises -> String:
        self._expect(34)
        var decoded = List[UInt8]()
        while True:
            var byte = self._peek()
            self.position += 1
            if byte == 34:
                return String(from_utf8=Span(decoded))
            if byte < 32:
                raise Error("unterminated JSON string or unescaped control byte")
            if byte != 92:
                decoded.append(UInt8(byte))
                continue
            var escape = self._peek()
            self.position += 1
            if escape == 34 or escape == 92 or escape == 47:
                decoded.append(UInt8(escape))
            elif escape == 98:
                decoded.append(8)
            elif escape == 102:
                decoded.append(12)
            elif escape == 110:
                decoded.append(10)
            elif escape == 114:
                decoded.append(13)
            elif escape == 116:
                decoded.append(9)
            elif escape == 117:
                var codepoint = self._hex4()
                if 0xD800 <= codepoint <= 0xDBFF:
                    self._expect(92)
                    self._expect(117)
                    var low = self._hex4()
                    if not 0xDC00 <= low <= 0xDFFF:
                        raise Error("invalid JSON Unicode surrogate pair")
                    codepoint = 0x10000 + (codepoint - 0xD800) * 1024 + low - 0xDC00
                elif 0xDC00 <= codepoint <= 0xDFFF:
                    raise Error("unpaired JSON Unicode surrogate")
                var character = chr(codepoint)
                decoded.extend(character.as_bytes())
            else:
                raise Error("invalid JSON string escape")

    def _number(mut self) raises -> String:
        var start = self.position
        if self._peek() == 45:
            self.position += 1
        if self._peek() == 48:
            self.position += 1
        elif 49 <= self._peek() <= 57:
            while 48 <= self._peek() <= 57:
                self.position += 1
        else:
            raise Error("invalid JSON number")
        if self._peek() == 46:
            self.position += 1
            if not 48 <= self._peek() <= 57:
                raise Error("invalid JSON fraction")
            while 48 <= self._peek() <= 57:
                self.position += 1
        if self._peek() == 101 or self._peek() == 69:
            self.position += 1
            if self._peek() == 43 or self._peek() == 45:
                self.position += 1
            if not 48 <= self._peek() <= 57:
                raise Error("invalid JSON exponent")
            while 48 <= self._peek() <= 57:
                self.position += 1
        var text = String(self.source[byte=start:self.position])
        if not isfinite(atof(text)):
            raise Error("JSON number is out of range")
        return text^

    def _value(mut self, depth: Int) raises -> Int:
        self._whitespace()
        var byte = self._peek()
        var kind = JSON_NULL
        var text = String()
        var children = List[Int]()
        var names = List[String]()
        if byte == 123 or byte == 91:
            # serde_json's default recursion guard allows at most 127 containers.
            if depth >= 127:
                raise Error("JSON recursion limit exceeded")
            kind = JSON_OBJECT if byte == 123 else JSON_ARRAY
            var closing = 125 if byte == 123 else 93
            self.position += 1
            self._whitespace()
            if self._peek() != closing:
                while True:
                    if kind == JSON_OBJECT:
                        names.append(self._string())
                        self._whitespace()
                        self._expect(58)
                    children.append(self._value(depth + 1))
                    self._whitespace()
                    if self._peek() != 44:
                        break
                    self.position += 1
                    self._whitespace()
            self._expect(closing)
        elif byte == 34:
            kind = JSON_STRING
            text = self._string()
        elif byte == 45 or 48 <= byte <= 57:
            kind = JSON_NUMBER
            text = self._number()
        else:
            var literal: String
            if byte == 110:
                literal = "null"
            elif byte == 116:
                literal = "true"
                kind = JSON_BOOL
            elif byte == 102:
                literal = "false"
                kind = JSON_BOOL
            else:
                raise Error("expected a JSON value")
            for literal_byte in literal.as_bytes():
                self._expect(Int(literal_byte))
            text = literal^
        var index = len(self.nodes)
        self.nodes.append(JsonNode(kind, text^, children^, names^))
        return index


def serialize_number(text: String) -> String:
    if text.find(".") < 0 and text.find("e") < 0 and text.find("E") < 0:
        if text.startswith("-"):
            var digits = String(text[byte=1:])
            if text != "-0" and (digits.byte_length() < 19 or (digits.byte_length() == 19 and digits <= "9223372036854775808")):
                return text
        elif text.byte_length() < 20 or (text.byte_length() == 20 and text <= "18446744073709551615"):
            return text
    try:
        return String(atof(text))
    except:
        return text


def serialize_json(document: JsonDocument, node: Int, indent: Int = -1, depth: Int = 0) -> String:
    ref value = document.nodes[node]
    if value.kind == JSON_STRING:
        return quote_json(value.text)
    if value.kind == JSON_NUMBER:
        return serialize_number(value.text)
    if value.kind != JSON_ARRAY and value.kind != JSON_OBJECT:
        return value.text
    var fields = List[Tuple[String, Int]]()
    if value.kind == JSON_OBJECT:
        for index in range(len(value.children)):
            fields.append((value.names[index], value.children[index]))
        sort(Span(fields), lambda (left: Tuple[String, Int], right: Tuple[String, Int]) -> Bool:
             left[0] < right[0] or (left[0] == right[0] and left[1] < right[1]))
    var children = List[Int]()
    var names = List[String]()
    if value.kind == JSON_ARRAY:
        children = value.children.copy()
    else:
        for index in range(len(fields)):
            if index + 1 < len(fields) and fields[index][0] == fields[index + 1][0]:
                continue
            names.append(fields[index][0])
            children.append(fields[index][1])
    var output = "[" if value.kind == JSON_ARRAY else "{"
    for index in range(len(children)):
        if index:
            output += ","
        if indent >= 0:
            output += "\n" + String(" ") * (indent * (depth + 1))
        if value.kind == JSON_OBJECT:
            output += quote_json(names[index]) + (": " if indent >= 0 else ":")
        output += serialize_json(document, children[index], indent, depth + 1)
    if children and indent >= 0:
        output += "\n" + String(" ") * (indent * depth)
    return output + ("]" if value.kind == JSON_ARRAY else "}")


def quote_json(text: StringSlice) -> String:
    var result = String("\"")
    comptime HEX = StaticString("0123456789abcdef")
    for character in text.codepoints():
        var code = Int(character)
        if code == 34:
            result += "\\\""
        elif code == 92:
            result += "\\\\"
        elif code == 8:
            result += "\\b"
        elif code == 12:
            result += "\\f"
        elif code == 10:
            result += "\\n"
        elif code == 13:
            result += "\\r"
        elif code == 9:
            result += "\\t"
        elif code < 32:
            result += "\\u00"
            result += HEX[byte=code // 16]
            result += HEX[byte=code % 16]
        else:
            result += chr(code)
    result += "\""
    return result^
