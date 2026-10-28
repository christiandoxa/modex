"""Bounded streaming validation for passthrough SSE response identifiers."""

from std.collections import List
from std.math import isfinite

from .json_float import json_float
from .text import is_whitespace


comptime _STRING = 1
comptime _NUMBER = 2
comptime _LITERAL = 3
comptime _ARRAY = 1
comptime _OBJECT = 2
comptime _ROOT = 1
comptime _RESPONSE = 2
comptime _MESSAGE = 3
comptime _RESPONSE_ID = 1
comptime _ROOT_ID = 2
comptime _ROOT_RESPONSE_ID = 3
comptime _ROOT_RESPONSE_ID_CAMEL = 4
comptime _MESSAGE_ID = 5
comptime _IDENTIFIER_LIMIT = 1024
# shortcut: numeric counters saturate at 1e9; use wider order tracking if multi-gigabyte numeric tokens become supported.


@fieldwise_init
struct _ObserverJSONFrame(Copyable):
    var kind: Int
    var state: Int
    var path: Int
    var key: String
    var key_valid: Bool


struct _ObserverJSON:
    var frames: List[_ObserverJSONFrame]
    var valid: Bool
    var root_started: Bool
    var root_complete: Bool
    var mode: Int
    var string_is_key: Bool
    var string_target: Int
    var key: String
    var key_too_long: Bool
    var identifier: String
    var pending_whitespace: String
    var pending_whitespace_too_long: Bool
    var identifier_started: Bool
    var identifier_too_long: Bool
    var unicode_escape: Int
    var unicode_digits: Int
    var high_surrogate: Int
    var pending_surrogate: Int
    var utf8_remaining: Int
    var utf8_codepoint: Int
    var utf8_minimum: Int
    var literal: String
    var literal_position: Int
    var number: String
    var number_too_long: Bool
    var number_state: Int
    var number_negative: Bool
    var number_after_decimal: Bool
    var number_in_exponent: Bool
    var number_exponent_negative: Bool
    var number_exponent_value: Int
    var number_fractional_digits: Int
    var number_significand: UInt64
    var number_significand_overflow: Bool
    var number_significant_started: Bool
    var number_significant_digits: Int
    var number_preview: String
    var response_id_seen: Bool
    var response_id_string: Bool
    var response_id: String
    var root_id_seen: Bool
    var root_id_string: Bool
    var root_id: String
    var root_response_id_seen: Bool
    var root_response_id_string: Bool
    var root_response_id: String
    var root_response_id_camel_seen: Bool
    var root_response_id_camel_string: Bool
    var root_response_id_camel: String
    var message_id_seen: Bool
    var message_id_string: Bool
    var message_id: String

    def __init__(out self):
        self.frames = List[_ObserverJSONFrame]()
        self.valid = True
        self.root_started = False
        self.root_complete = False
        self.mode = 0
        self.string_is_key = False
        self.string_target = 0
        self.key = ""
        self.key_too_long = False
        self.identifier = ""
        self.pending_whitespace = ""
        self.pending_whitespace_too_long = False
        self.identifier_started = False
        self.identifier_too_long = False
        self.unicode_escape = 0
        self.unicode_digits = 0
        self.high_surrogate = 0
        self.pending_surrogate = 0
        self.utf8_remaining = 0
        self.utf8_codepoint = 0
        self.utf8_minimum = 0
        self.literal = ""
        self.literal_position = 0
        self.number = ""
        self.number_too_long = False
        self.number_state = 0
        self.number_negative = False
        self.number_after_decimal = False
        self.number_in_exponent = False
        self.number_exponent_negative = False
        self.number_exponent_value = 0
        self.number_fractional_digits = 0
        self.number_significand = 0
        self.number_significand_overflow = False
        self.number_significant_started = False
        self.number_significant_digits = 0
        self.number_preview = ""
        self.response_id_seen = False
        self.response_id_string = False
        self.response_id = ""
        self.root_id_seen = False
        self.root_id_string = False
        self.root_id = ""
        self.root_response_id_seen = False
        self.root_response_id_string = False
        self.root_response_id = ""
        self.root_response_id_camel_seen = False
        self.root_response_id_camel_string = False
        self.root_response_id_camel = ""
        self.message_id_seen = False
        self.message_id_string = False
        self.message_id = ""

    def feed(mut self, byte: UInt8):
        if not self.valid:
            return
        if self.mode == _STRING:
            self._string_byte(byte)
        elif self.mode == _NUMBER:
            self._number_byte(byte)
        elif self.mode == _LITERAL:
            self._literal_byte(byte)
        else:
            self._normal_byte(byte)

    def finish(mut self) -> String:
        if not self.valid:
            return ""
        if self.mode == _NUMBER:
            self._finish_number()
        if not self.valid or self.mode != 0 or not self.root_started or not self.root_complete or self.frames:
            return ""
        if self.response_id_seen and self.response_id_string:
            return self.response_id
        if self.root_id_seen and self.root_id_string:
            return self.root_id
        if self.root_response_id_seen and self.root_response_id_string:
            return self.root_response_id
        if self.root_response_id_camel_seen and self.root_response_id_camel_string:
            return self.root_response_id_camel
        if self.message_id_seen and self.message_id_string:
            return self.message_id
        return ""

    def _normal_byte(mut self, byte: UInt8):
        var value = Int(byte)
        if value == 32 or value == 9 or value == 10 or value == 13:
            return
        if self.frames:
            var index = len(self.frames) - 1
            var frame = self.frames[index].copy()
            if frame.kind == _OBJECT:
                if frame.state == 0 or frame.state == 4:
                    if value == 34:
                        self._start_key()
                    elif value == 125 and frame.state == 0:
                        self._close_container(_OBJECT)
                    else:
                        self.valid = False
                elif frame.state == 1:
                    if value == 58:
                        self.frames[index].state = 2
                    else:
                        self.valid = False
                elif frame.state == 2:
                    self._start_value(value)
                else:
                    if value == 44:
                        self.frames[index].state = 4
                    elif value == 125:
                        self._close_container(_OBJECT)
                    else:
                        self.valid = False
            else:
                if frame.state == 0 or frame.state == 2:
                    if value == 93 and frame.state == 0:
                        self._close_container(_ARRAY)
                    else:
                        self._start_value(value)
                elif value == 44:
                    self.frames[index].state = 2
                elif value == 93:
                    self._close_container(_ARRAY)
                else:
                    self.valid = False
            return
        if self.root_started:
            self.valid = False
        else:
            self._start_value(value)

    def _start_key(mut self):
        self.string_is_key = True
        self.string_target = 0
        self.key = ""
        self.key_too_long = False
        self.identifier = ""
        self.pending_whitespace = ""
        self.pending_whitespace_too_long = False
        self.identifier_started = False
        self.identifier_too_long = False
        self.utf8_remaining = 0
        self.mode = _STRING

    def _start_value(mut self, first: Int):
        var value_kind: Int
        if first == 34:
            value_kind = 3
        elif first == 123:
            value_kind = _OBJECT
        elif first == 91:
            value_kind = _ARRAY
        elif first == 45 or 48 <= first <= 57:
            value_kind = 4
        elif first == 110 or first == 116 or first == 102:
            value_kind = 5
        else:
            self.valid = False
            return

        var target = 0
        var child_path = 0
        if self.frames:
            var parent_index = len(self.frames) - 1
            var parent = self.frames[parent_index].copy()
            if parent.kind == _OBJECT:
                if parent.state != 2:
                    self.valid = False
                    return
                if parent.path == _ROOT and parent.key_valid:
                    if parent.key == "response":
                        self._clear_response_id()
                        if value_kind == _OBJECT:
                            child_path = _RESPONSE
                    elif parent.key == "message":
                        self._clear_message_id()
                        if value_kind == _OBJECT:
                            child_path = _MESSAGE
                    elif parent.key == "id":
                        target = _ROOT_ID
                    elif parent.key == "response_id":
                        target = _ROOT_RESPONSE_ID
                    elif parent.key == "responseId":
                        target = _ROOT_RESPONSE_ID_CAMEL
                elif parent.path == _RESPONSE and parent.key_valid and parent.key == "id":
                    target = _RESPONSE_ID
                elif parent.path == _MESSAGE and parent.key_valid and parent.key == "id":
                    target = _MESSAGE_ID
                if target:
                    self._begin_identifier_slot(target, value_kind == 3)
                self.frames[parent_index].state = 3
                self.frames[parent_index].key = ""
                self.frames[parent_index].key_valid = False
            else:
                if parent.state != 0 and parent.state != 2:
                    self.valid = False
                    return
                self.frames[parent_index].state = 1
        else:
            if self.root_started:
                self.valid = False
                return
            self.root_started = True
            if value_kind == _OBJECT:
                child_path = _ROOT

        if value_kind == 3:
            self.string_is_key = False
            self.string_target = target
            self.key = ""
            self.key_too_long = False
            self.identifier = ""
            self.pending_whitespace = ""
            self.pending_whitespace_too_long = False
            self.identifier_started = False
            self.identifier_too_long = False
            self.utf8_remaining = 0
            self.mode = _STRING
        elif value_kind == _OBJECT or value_kind == _ARRAY:
            if len(self.frames) >= 127:
                self.valid = False
                return
            self.frames.append(_ObserverJSONFrame(value_kind, 0, child_path, "", False))
        elif value_kind == 4:
            self.mode = _NUMBER
            self._start_number(first)
            if first == 45:
                self.number_state = 0
            elif first == 48:
                self.number_state = 1
            else:
                self.number_state = 2
        else:
            self.mode = _LITERAL
            self.literal = "null" if first == 110 else "true" if first == 116 else "false"
            self.literal_position = 1
            if self.literal.byte_length() == 1:
                self.mode = 0
                self._complete_scalar()

    def _close_container(mut self, kind: Int):
        if not self.frames:
            self.valid = False
            return
        var frame = self.frames[len(self.frames) - 1].copy()
        if frame.kind != kind or (frame.kind == _OBJECT and frame.state != 0 and frame.state != 3) or (frame.kind == _ARRAY and frame.state != 0 and frame.state != 1):
            self.valid = False
            return
        _ = self.frames.pop()
        if not self.frames:
            self.root_complete = True

    def _complete_scalar(mut self):
        if not self.frames:
            self.root_complete = True

    def _begin_identifier_slot(mut self, slot: Int, is_string: Bool):
        if slot == _RESPONSE_ID:
            self.response_id_seen = True
            self.response_id_string = is_string
            self.response_id = ""
        elif slot == _ROOT_ID:
            self.root_id_seen = True
            self.root_id_string = is_string
            self.root_id = ""
        elif slot == _ROOT_RESPONSE_ID:
            self.root_response_id_seen = True
            self.root_response_id_string = is_string
            self.root_response_id = ""
        elif slot == _ROOT_RESPONSE_ID_CAMEL:
            self.root_response_id_camel_seen = True
            self.root_response_id_camel_string = is_string
            self.root_response_id_camel = ""
        elif slot == _MESSAGE_ID:
            self.message_id_seen = True
            self.message_id_string = is_string
            self.message_id = ""

    def _clear_response_id(mut self):
        self.response_id_seen = False
        self.response_id_string = False
        self.response_id = ""

    def _clear_message_id(mut self):
        self.message_id_seen = False
        self.message_id_string = False
        self.message_id = ""

    def _emit_codepoint(mut self, codepoint: Int):
        if self.string_is_key:
            var encoded = chr(codepoint)
            if not self.key_too_long:
                if self.key.byte_length() + encoded.byte_length() <= 16:
                    self.key += encoded
                else:
                    self.key_too_long = True
            return
        if self.string_target == 0 or self.identifier_too_long:
            return
        var encoded = chr(codepoint)
        if is_whitespace(codepoint):
            if self.identifier_started:
                if self.identifier.byte_length() + self.pending_whitespace.byte_length() + encoded.byte_length() <= _IDENTIFIER_LIMIT:
                    self.pending_whitespace += encoded
                else:
                    self.pending_whitespace = ""
                    self.pending_whitespace_too_long = True
            return
        if not self.identifier_started:
            self.identifier_started = True
            self.identifier += encoded
            return
        if self.pending_whitespace_too_long:
            self.identifier_too_long = True
            return
        if self.identifier.byte_length() + self.pending_whitespace.byte_length() + encoded.byte_length() > _IDENTIFIER_LIMIT:
            self.identifier_too_long = True
            self.identifier = ""
            self.pending_whitespace = ""
            return
        self.identifier += self.pending_whitespace + encoded
        self.pending_whitespace = ""

    def _string_byte(mut self, byte: UInt8):
        var value = Int(byte)
        if self.utf8_remaining > 0:
            if value < 128 or value > 191:
                self.valid = False
                return
            self.utf8_codepoint = self.utf8_codepoint * 64 + value - 128
            self.utf8_remaining -= 1
            if self.utf8_remaining == 0:
                if self.utf8_codepoint < self.utf8_minimum or self.utf8_codepoint > 0x10FFFF or 0xD800 <= self.utf8_codepoint <= 0xDFFF:
                    self.valid = False
                else:
                    self._emit_codepoint(self.utf8_codepoint)
            return
        if self.unicode_escape == 1:
            var digit = _hex_digit(value)
            if digit < 0:
                self.valid = False
                return
            self.high_surrogate = self.high_surrogate * 16 + digit
            self.unicode_digits += 1
            if self.unicode_digits == 4:
                if 0xD800 <= self.high_surrogate <= 0xDBFF:
                    self.pending_surrogate = self.high_surrogate
                    self.unicode_escape = 2
                elif 0xDC00 <= self.high_surrogate <= 0xDFFF:
                    self.valid = False
                else:
                    self._emit_codepoint(self.high_surrogate)
                    self.unicode_escape = 0
            return
        if self.unicode_escape == 2:
            if value != 92:
                self.valid = False
            else:
                self.unicode_escape = 3
            return
        if self.unicode_escape == 3:
            if value != 117:
                self.valid = False
            else:
                self.unicode_escape = 4
                self.unicode_digits = 0
                self.high_surrogate = 0
            return
        if self.unicode_escape == 4:
            var digit = _hex_digit(value)
            if digit < 0:
                self.valid = False
                return
            self.high_surrogate = self.high_surrogate * 16 + digit
            self.unicode_digits += 1
            if self.unicode_digits == 4:
                if not 0xDC00 <= self.high_surrogate <= 0xDFFF:
                    self.valid = False
                else:
                    var codepoint = 0x10000 + (self.pending_surrogate - 0xD800) * 1024 + self.high_surrogate - 0xDC00
                    self._emit_codepoint(codepoint)
                    self.unicode_escape = 0
                    self.high_surrogate = 0
                    self.pending_surrogate = 0
            return
        if self.unicode_escape == 5:
            if value == 34 or value == 92 or value == 47:
                self._emit_codepoint(value)
            elif value == 98:
                self._emit_codepoint(8)
            elif value == 102:
                self._emit_codepoint(12)
            elif value == 110:
                self._emit_codepoint(10)
            elif value == 114:
                self._emit_codepoint(13)
            elif value == 116:
                self._emit_codepoint(9)
            elif value == 117:
                self.unicode_escape = 1
                self.unicode_digits = 0
                self.high_surrogate = 0
            else:
                self.valid = False
            if value != 117:
                self.unicode_escape = 0
            return
        if value == 34:
            self._end_string()
        elif value == 92:
            self.unicode_escape = 5
        elif value < 32:
            self.valid = False
        elif value < 128:
            self._emit_codepoint(value)
        elif 194 <= value <= 223:
            self.utf8_remaining = 1
            self.utf8_codepoint = value - 192
            self.utf8_minimum = 128
        elif 224 <= value <= 239:
            self.utf8_remaining = 2
            self.utf8_codepoint = value - 224
            self.utf8_minimum = 2048
        elif 240 <= value <= 244:
            self.utf8_remaining = 3
            self.utf8_codepoint = value - 240
            self.utf8_minimum = 65536
        else:
            self.valid = False

    def _end_string(mut self):
        self.mode = 0
        if self.string_is_key:
            var index = len(self.frames) - 1
            self.frames[index].key = self.key
            self.frames[index].key_valid = not self.key_too_long
            self.frames[index].state = 1
        else:
            if self.string_target == _RESPONSE_ID:
                self.response_id = "" if self.identifier_too_long else self.identifier
            elif self.string_target == _ROOT_ID:
                self.root_id = "" if self.identifier_too_long else self.identifier
            elif self.string_target == _ROOT_RESPONSE_ID:
                self.root_response_id = "" if self.identifier_too_long else self.identifier
            elif self.string_target == _ROOT_RESPONSE_ID_CAMEL:
                self.root_response_id_camel = "" if self.identifier_too_long else self.identifier
            elif self.string_target == _MESSAGE_ID:
                self.message_id = "" if self.identifier_too_long else self.identifier
            self._complete_scalar()
        self.string_target = 0
        self.string_is_key = False
        self.pending_whitespace = ""
        self.pending_whitespace_too_long = False
        self.unicode_escape = 0
        self.utf8_remaining = 0

    def _literal_byte(mut self, byte: UInt8):
        if self.literal_position >= self.literal.byte_length() or byte != self.literal.as_bytes()[self.literal_position]:
            self.valid = False
            return
        self.literal_position += 1
        if self.literal_position == self.literal.byte_length():
            self.mode = 0
            self._complete_scalar()

    def _number_byte(mut self, byte: UInt8):
        var value = Int(byte)
        var delimiter = value == 32 or value == 9 or value == 10 or value == 13 or value == 44 or value == 93 or value == 125
        var consume = False
        if self.number_state == 0:
            if value == 48:
                self.number_state = 1
                consume = True
            elif 49 <= value <= 57:
                self.number_state = 2
                consume = True
        elif self.number_state == 1:
            if value == 46:
                self.number_state = 3
                consume = True
            elif value == 101 or value == 69:
                self.number_state = 5
                consume = True
            elif delimiter:
                self._finish_number()
                self._normal_byte(byte)
                return
        elif self.number_state == 2:
            if 48 <= value <= 57:
                consume = True
            elif value == 46:
                self.number_state = 3
                consume = True
            elif value == 101 or value == 69:
                self.number_state = 5
                consume = True
            elif delimiter:
                self._finish_number()
                self._normal_byte(byte)
                return
        elif self.number_state == 3:
            if 48 <= value <= 57:
                self.number_state = 4
                consume = True
        elif self.number_state == 4:
            if 48 <= value <= 57:
                consume = True
            elif value == 101 or value == 69:
                self.number_state = 5
                consume = True
            elif delimiter:
                self._finish_number()
                self._normal_byte(byte)
                return
        elif self.number_state == 5:
            if value == 43 or value == 45:
                self.number_state = 6
                consume = True
            elif 48 <= value <= 57:
                self.number_state = 7
                consume = True
        elif self.number_state == 6:
            if 48 <= value <= 57:
                self.number_state = 7
                consume = True
        else:
            if 48 <= value <= 57:
                consume = True
            elif delimiter:
                self._finish_number()
                self._normal_byte(byte)
                return
        if not consume:
            self.valid = False
            return
        if self.number.byte_length() < 256:
            self.number += chr(value)
        else:
            self.number_too_long = True
        self._track_number_byte(value)

    def _start_number(mut self, first: Int):
        self.number = chr(first)
        self.number_too_long = False
        self.number_negative = first == 45
        self.number_after_decimal = False
        self.number_in_exponent = False
        self.number_exponent_negative = False
        self.number_exponent_value = 0
        self.number_fractional_digits = 0
        self.number_significand = 0
        self.number_significand_overflow = False
        self.number_significant_started = False
        self.number_significant_digits = 0
        self.number_preview = ""
        if 48 <= first <= 57:
            self._track_number_digit(first)

    def _track_number_byte(mut self, value: Int):
        if value == 46:
            self.number_after_decimal = True
        elif value == 101 or value == 69:
            self.number_in_exponent = True
        elif self.number_in_exponent and value == 45:
            self.number_exponent_negative = True
        elif self.number_in_exponent and value == 43:
            self.number_exponent_negative = False
        elif 48 <= value <= 57:
            if self.number_in_exponent:
                if self.number_exponent_value < 1000000000:
                    self.number_exponent_value = min(1000000000, self.number_exponent_value * 10 + value - 48)
            else:
                self._track_number_digit(value)

    def _track_number_digit(mut self, value: Int):
        var digit = UInt64(value - 48)
        if not self.number_significand_overflow:
            if self.number_significand > (UInt64.MAX - digit) // 10:
                self.number_significand_overflow = True
            else:
                self.number_significand = self.number_significand * 10 + digit
        if self.number_after_decimal and self.number_fractional_digits < 1000000000:
            self.number_fractional_digits += 1
        if self.number_significant_started or digit != 0:
            self.number_significant_started = True
            if self.number_significant_digits < 1000000000:
                self.number_significant_digits += 1
            if self.number_preview.byte_length() < 64:
                self.number_preview += chr(value)

    def _finish_number(mut self):
        if self.number_state != 1 and self.number_state != 2 and self.number_state != 4 and self.number_state != 7:
            self.valid = False
            return
        if self.number_too_long:
            if not self._long_number_is_finite():
                self.valid = False
                return
        else:
            try:
                _ = json_float(self.number)
            except:
                self.valid = False
                return
        self.mode = 0
        self._complete_scalar()

    def _long_number_is_finite(self) -> Bool:
        if not self.number_significant_started:
            return True
        try:
            var exponent = self.number_exponent_value
            if self.number_exponent_negative:
                exponent = -exponent
            if not self.number_significand_overflow:
                var decimal_exponent = exponent - self.number_fractional_digits
                var value = Float64(self.number_significand)
                if decimal_exponent > 308:
                    return False
                if decimal_exponent < -308:
                    return True
                while decimal_exponent > 0:
                    var power = min(decimal_exponent, 308)
                    value *= atof("1e" + String(power))
                    decimal_exponent -= power
                while decimal_exponent < 0 and value != 0:
                    var power = min(-decimal_exponent, 308)
                    value /= atof("1e" + String(power))
                    decimal_exponent += power
                return isfinite(value)
            var omitted = self.number_significant_digits - self.number_preview.byte_length()
            var decimal_exponent = exponent - self.number_fractional_digits + omitted
            var normalized = ("-" if self.number_negative else "") + self.number_preview + "e" + String(decimal_exponent)
            return isfinite(atof(normalized))
        except:
            return False


def _hex_digit(value: Int) -> Int:
    if 48 <= value <= 57:
        return value - 48
    if 65 <= value <= 70:
        return value - 55
    if 97 <= value <= 102:
        return value - 87
    return -1


struct RuntimeSSEBindingObserver:
    var json: _ObserverJSON
    var failed: Bool
    var finished: Bool
    var pending_cr: Int
    var line_content: Bool
    var line_has_colon: Bool
    var line_is_data: Bool
    var line_field_length: Int
    var line_field_matches_data: Bool
    var line_value_prefix: Bool
    var line_prefix_bytes: List[UInt8]
    var line_utf8_remaining: Int
    var line_utf8_codepoint: Int
    var line_utf8_minimum: Int
    var event_has_data: Bool

    def __init__(out self):
        self.json = _ObserverJSON()
        self.failed = False
        self.finished = False
        self.pending_cr = 0
        self.line_content = False
        self.line_has_colon = False
        self.line_is_data = False
        self.line_field_length = 0
        self.line_field_matches_data = True
        self.line_value_prefix = True
        self.line_prefix_bytes = List[UInt8]()
        self.line_utf8_remaining = 0
        self.line_utf8_codepoint = 0
        self.line_utf8_minimum = 0
        self.event_has_data = False

    def consume(mut self, chunk: ImmSpan[UInt8, _]) raises -> List[String]:
        if self.finished:
            raise Error("runtime SSE binding observer is finished")
        var output = List[String]()
        if self.failed:
            return output^
        try:
            for byte in chunk:
                if byte == 10:
                    self.pending_cr = 0
                    self._end_line(output)
                elif byte == 13:
                    if self.pending_cr == Int.MAX:
                        raise Error("runtime SSE line is too long to observe")
                    self.pending_cr += 1
                else:
                    while self.pending_cr > 0:
                        self._line_byte(13)
                        self.pending_cr -= 1
                    self._line_byte(byte)
        except:
            self.failed = True
        return output^

    def is_failed(self) -> Bool:
        return self.failed

    def finish(mut self) raises -> List[String]:
        var output = List[String]()
        if self.finished:
            return output^
        self.finished = True
        if self.failed:
            return output^
        self.pending_cr = 0
        if self.line_content:
            self._end_line(output)
        self._dispatch_event(output)
        return output^

    def _line_byte(mut self, byte: UInt8) raises:
        var value = Int(byte)
        self.line_content = True
        if self.line_utf8_remaining > 0:
            if value < 128 or value > 191:
                raise Error("provider SSE line is not valid UTF-8")
            self.line_utf8_codepoint = self.line_utf8_codepoint * 64 + value - 128
            self.line_utf8_remaining -= 1
            if self.line_utf8_remaining == 0 and (self.line_utf8_codepoint < self.line_utf8_minimum or self.line_utf8_codepoint > 0x10FFFF or 0xD800 <= self.line_utf8_codepoint <= 0xDFFF):
                raise Error("provider SSE line is not valid UTF-8")
        elif value >= 128:
            if 194 <= value <= 223:
                self.line_utf8_remaining = 1
                self.line_utf8_codepoint = value - 192
                self.line_utf8_minimum = 128
            elif 224 <= value <= 239:
                self.line_utf8_remaining = 2
                self.line_utf8_codepoint = value - 224
                self.line_utf8_minimum = 2048
            elif 240 <= value <= 244:
                self.line_utf8_remaining = 3
                self.line_utf8_codepoint = value - 240
                self.line_utf8_minimum = 65536
            else:
                raise Error("provider SSE line is not valid UTF-8")

        if not self.line_has_colon:
            if value == 58:
                self.line_has_colon = True
                self.line_is_data = self.line_field_length == 4 and self.line_field_matches_data
                if self.line_is_data:
                    self._begin_data_line()
            else:
                if self.line_field_length < 4:
                    var expected = 100 if self.line_field_length == 0 else 97 if self.line_field_length == 1 or self.line_field_length == 3 else 116
                    self.line_field_matches_data = self.line_field_matches_data and value == expected
                if self.line_field_length < 5:
                    self.line_field_length += 1
        elif self.line_is_data:
            if self.line_value_prefix and value < 128 and is_whitespace(value):
                return
            elif self.line_value_prefix and value >= 128:
                self.line_prefix_bytes.append(byte)
                if self.line_utf8_remaining == 0:
                    if is_whitespace(self.line_utf8_codepoint):
                        self.line_prefix_bytes.clear()
                    else:
                        self.line_value_prefix = False
                        for prefix_byte in self.line_prefix_bytes:
                            self.json.feed(prefix_byte)
                        self.line_prefix_bytes.clear()
            else:
                self.line_value_prefix = False
                self.json.feed(byte)

    def _begin_data_line(mut self):
        if self.event_has_data:
            self.json.feed(10)
        self.event_has_data = True
        self.line_value_prefix = True
        self.line_prefix_bytes.clear()

    def _end_line(mut self, mut output: List[String]) raises:
        if self.line_utf8_remaining != 0:
            raise Error("provider SSE line is not valid UTF-8")
        if not self.line_content:
            self._dispatch_event(output)
        elif not self.line_has_colon and self.line_field_length == 4 and self.line_field_matches_data:
            self._begin_data_line()
        self.line_content = False
        self.line_has_colon = False
        self.line_is_data = False
        self.line_field_length = 0
        self.line_field_matches_data = True
        self.line_value_prefix = True
        self.line_prefix_bytes.clear()
        self.line_utf8_remaining = 0
        self.line_utf8_codepoint = 0
        self.line_utf8_minimum = 0

    def _dispatch_event(mut self, mut output: List[String]):
        if self.event_has_data:
            var response_id = self.json.finish()
            if response_id:
                output.append(response_id^)
        self.json = _ObserverJSON()
        self.event_has_data = False
