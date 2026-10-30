"""Buffered DeepSeek chat completions translated into Responses JSON."""

from std.time.time import _realtime_nanoseconds

from .json import JSON_ARRAY, JSON_NULL, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json
from .json_float import json_float
from .provider_chat_items import wrap_tool_arguments
from .provider_chat_metadata import merge_chat_metadata
from .provider_chat_usage import chat_usage, json_unsigned
from .text import trim_text
from .uuid7 import new_uuid7


def deepseek_buffered_response(
    source: String,
    fallback_created_at: UInt64,
    fallback_response_id: String,
    request_metadata: String = "null",
) raises -> String:
    if source.byte_length() > 4194304:
        raise Error("buffered response exceeded safe size limit (4194304)")
    var doc: JsonDocument
    try:
        doc = JsonDocument(source)
    except:
        raise Error("failed to parse DeepSeek chat response JSON")
    if doc.nodes[doc.root].kind != JSON_OBJECT:
        raise Error("DeepSeek chat response is not an object")
    var choice = _first_choice(doc)
    if choice >= 0 and doc.nodes[choice].kind != JSON_OBJECT:
        raise Error("DeepSeek chat response choice is not an object")
    var id = _string_member(doc, doc.root, "id")
    var response_id = id.value() if id else fallback_response_id
    var created = json_unsigned(doc, doc.get(doc.root, "created"))
    var created_at = created.value() if created else UInt64(max(0, _realtime_nanoseconds() // 1000000000))
    var model = _string_member(doc, doc.root, "model")

    var output = "["
    var output_count = 0
    var message = doc.get(choice, "message")
    var content = _string_member(doc, message, "content")
    if content and content.value().byte_length() > 0:
        output += '{"type":"message","role":"assistant","content":[{"type":"output_text","text":'
        output += quote_json(content.value()) + "}]}"
        output_count += 1

    var tools = _tool_outputs(doc, message)
    if tools[0]:
        if output_count:
            output += ","
        output += tools[0].value()
    output += "]"

    var result = '{"id":' + quote_json(response_id) + ',"object":"response","created_at":'
    result += String(created_at) + ',"model":' + quote_json(model.value() if model else "deepseek-chat")
    result += ',"output":' + output
    if tools[1]:
        result += ',"status":"failed","error":{"code":"invalid_tool_call_arguments","message":'
        result += quote_json(tools[1].value()) + "}"

    var usage = doc.get(doc.root, "usage")
    if usage >= 0:
        result += ',"usage":' + chat_usage(doc, usage, "deepseek")

    var provider_metadata = _provider_metadata(doc, choice, message)
    var request = JsonDocument(request_metadata)
    var has_request_metadata = request.nodes[request.root].kind == JSON_OBJECT
    if provider_metadata != "{}" or has_request_metadata:
        result += ',"metadata":' + merge_chat_metadata(provider_metadata, request_metadata)
    result += "}"

    var normalized = JsonDocument(result)
    return serialize_json(normalized, normalized.root)


def deepseek_buffered_assistant_messages(source: String) raises -> String:
    var doc = JsonDocument(source)
    var choice = _first_choice(doc)
    if choice >= 0 and doc.nodes[choice].kind != JSON_OBJECT:
        raise Error("DeepSeek chat response choice is not an object")
    var message = doc.get(choice, "message")
    var content = _string_member(doc, message, "content")
    var reasoning = _string_member(doc, message, "reasoning_content")
    var calls = doc.get(message, "tool_calls")
    if (not content or content.value().byte_length() == 0) and (not reasoning or reasoning.value().byte_length() == 0) and calls < 0:
        return "[]"
    var result = '[{"role":"assistant","content":'
    result += quote_json(content.value()) if content else String('""' if calls >= 0 else "null")
    if reasoning and reasoning.value().byte_length() > 0:
        result += ',"reasoning_content":' + quote_json(reasoning.value())
    if calls >= 0:
        if doc.nodes[calls].kind == JSON_ARRAY:
            for call in doc.nodes[calls].children:
                var function = doc.get(call, "function")
                var name = doc.string(doc.get(function, "name"))
                var arguments = doc.get(function, "arguments")
                if arguments >= 0 and doc.nodes[arguments].kind == JSON_STRING and (name == "shell" or name == "exec" or name == "functions.exec_command"):
                    doc.nodes[arguments].text = wrap_tool_arguments("exec", doc.nodes[arguments].text)
        result += ',"tool_calls":' + serialize_json(doc, calls)
    var normalized = JsonDocument(result + "}]")
    return serialize_json(normalized, normalized.root)


def _first_choice(doc: JsonDocument) -> Int:
    var choices = doc.get(doc.root, "choices")
    if choices < 0 or doc.nodes[choices].kind != JSON_ARRAY or not doc.nodes[choices].children:
        return -1
    return doc.nodes[choices].children[0]


def _string_member(doc: JsonDocument, parent: Int, name: StringSlice) -> Optional[String]:
    var node = doc.get(parent, name)
    if node >= 0 and doc.nodes[node].kind == JSON_STRING:
        return Optional[String](doc.nodes[node].text)
    return Optional[String]()


def _provider_metadata(doc: JsonDocument, choice: Int, message: Int) raises -> String:
    var fields = String()
    var count = 0
    var logprobs = doc.get(choice, "logprobs")
    if logprobs >= 0 and doc.nodes[logprobs].kind != JSON_NULL:
        fields += '"logprobs":' + serialize_json(doc, logprobs)
        count += 1
    var finish_reason = _string_member(doc, choice, "finish_reason")
    if finish_reason:
        if count:
            fields += ","
        fields += '"finish_reason":' + quote_json(finish_reason.value())
        count += 1
    var reasoning = _string_member(doc, message, "reasoning_content")
    if reasoning and trim_text(reasoning.value()).byte_length() > 0:
        if count:
            fields += ","
        fields += '"reasoning_content":' + quote_json(reasoning.value())
        count += 1
    var refusal = _string_member(doc, message, "refusal")
    if refusal and trim_text(refusal.value()).byte_length() > 0:
        if count:
            fields += ","
        fields += '"refusal":' + quote_json(refusal.value())
        count += 1
    var annotations = doc.get(message, "annotations")
    if annotations >= 0 and doc.nodes[annotations].kind == JSON_ARRAY and doc.nodes[annotations].children:
        if count:
            fields += ","
        fields += '"annotations":' + serialize_json(doc, annotations)
        count += 1
    var fingerprint = _string_member(doc, doc.root, "system_fingerprint")
    if fingerprint and trim_text(fingerprint.value()).byte_length() > 0:
        if count:
            fields += ","
        fields += '"system_fingerprint":' + quote_json(fingerprint.value())
        count += 1
    if count == 0:
        return "{}"
    return '{"deepseek":{' + fields + "}}"


def _tool_outputs(doc: JsonDocument, message: Int) raises -> Tuple[Optional[String], Optional[String]]:
    var tool_calls = doc.get(message, "tool_calls")
    if tool_calls < 0 or doc.nodes[tool_calls].kind != JSON_ARRAY:
        return (Optional[String](), Optional[String]())

    var output = String()
    var output_count = 0
    for node in doc.nodes[tool_calls].children:
        var function = doc.get(node, "function")
        if function < 0 or doc.nodes[function].kind != JSON_OBJECT:
            return (Optional[String](output) if output_count else Optional[String](), Optional[String]("DeepSeek returned a tool call without a function object"))
        var name = _string_member(doc, function, "name")
        if name and name.value().byte_length() > 4194304:
            return (Optional[String](output) if output_count else Optional[String](), Optional[String]("DeepSeek returned a tool call name exceeding the supported size"))
        if not name or trim_text(name.value()).byte_length() == 0:
            return (Optional[String](output) if output_count else Optional[String](), Optional[String]("DeepSeek returned a tool call without a function name"))
        var arguments = _string_member(doc, function, "arguments")
        var argument_text = arguments.value() if arguments else String("{}")
        var id = _string_member(doc, node, "id")
        var parse_error = _tool_arguments_error(name.value(), argument_text, id.value() if id else String("call_0"))
        if parse_error:
            return (Optional[String](output) if output_count else Optional[String](), Optional[String](parse_error.value()))
        var call_id = id.value() if id else "call_deepseek_" + new_uuid7()
        var signature = _thought_signature(doc, node)
        var item = _tool_item(call_id, name.value(), argument_text, signature)
        if output_count:
            output += ","
        output += item
        output_count += 1
    return (Optional[String](output) if output_count else Optional[String](), Optional[String]())


def _thought_signature(doc: JsonDocument, tool_call: Int) -> Optional[String]:
    var extra = doc.get(tool_call, "extra_content")
    var google = doc.get(extra, "google")
    var signature = _string_member(doc, google, "thought_signature")
    if signature and trim_text(signature.value()).byte_length() > 0:
        return signature
    return Optional[String]()


def _tool_item(call_id: String, name: String, arguments: String, signature: Optional[String]) raises -> String:
    if name == "tool_search":
        var parsed = JsonDocument(arguments)
        return '{"type":"tool_search_call","call_id":' + quote_json(call_id) + ',"execution":"client","arguments":' + serialize_json(parsed, parsed.root) + "}"
    if name == "apply_patch":
        return '{"type":"custom_tool_call","call_id":' + quote_json(call_id) + ',"name":"apply_patch","input":' + quote_json(arguments) + "}"

    var output_arguments = arguments
    if name == "shell" or name == "exec" or name == "functions.exec_command":
        output_arguments = wrap_tool_arguments("exec", arguments)
    var parts = _split_deepseek_name(name)
    var item = '{"type":"function_call","call_id":' + quote_json(call_id) + ',"name":' + quote_json(parts[1])
    if parts[0]:
        item += ',"namespace":' + quote_json(parts[0].value())
    item += ',"arguments":' + quote_json(output_arguments)
    if signature:
        item += ',"gemini_thought_signature":' + quote_json(signature.value())
    return item + "}"


def _split_deepseek_name(name: String) -> Tuple[Optional[String], String]:
    for separator in ["__", ".", "/"]:
        var split = name.find(separator)
        if split < 0:
            continue
        var namespace = trim_text(String(name[byte=:split]))
        var local = trim_text(String(name[byte=split + separator.byte_length():]))
        if namespace and local:
            return (Optional[String](namespace), local)
    return (Optional[String](), trim_text(name))


def _tool_arguments_error(name: String, arguments: String, call_id: String) raises -> Optional[String]:
    if not trim_text(arguments) and name != "tool_search":
        return Optional[String]()
    var structural = BufferedJSONDiagnostic(arguments)
    var accepted = structural.fragment(0)
    structural.whitespace()
    accepted = accepted and structural.position == arguments.byte_length()
    # The frozen kernel accepts structural fragments before Serde checks tool-search output.
    if accepted and name != "tool_search":
        return Optional[String]()
    var source = arguments
    var prefix = "DeepSeek returned malformed JSON arguments for tool call `" + name + "`: "
    if accepted:
        source = '{"type":"tool_search_call","call_id":' + quote_json(call_id) + ',"execution":"client","arguments":' + arguments + "}"
        prefix = "DeepSeek Mojo returned invalid response tool-call JSON: "
    try:
        var parsed = JsonDocument(source)
    except:
        var diagnostic = BufferedJSONDiagnostic(source)
        _ = diagnostic.value(0)
        if not diagnostic.message:
            diagnostic.whitespace()
            _ = diagnostic.fail("trailing characters", True)
        var detail = diagnostic.message + " at " + _line_column(source, diagnostic.error_offset)
        return Optional[String](prefix + detail)
    return Optional[String]()


struct BufferedJSONDiagnostic:
    var source: String
    var position: Int
    var error_offset: Int
    var message: String

    def __init__(out self, source: String):
        self.source = source
        self.position = 0
        self.error_offset = 0
        self.message = ""

    def peek(self) -> Int:
        return Int(self.source.as_bytes()[self.position]) if self.position < self.source.byte_length() else -1

    def whitespace(mut self):
        while _is_json_space(self.peek()):
            self.position += 1

    def fail(mut self, message: String, peek: Bool = False) -> Bool:
        if self.message:
            return False
        self.message = message
        self.error_offset = self.position + (1 if peek and self.peek() >= 0 else 0)
        return False

    def fragment(mut self, depth: Int) raises -> Bool:
        if depth > 256:
            return False
        self.whitespace()
        var opening = self.peek()
        if opening < 0:
            return False
        if opening == 34:
            self.position += 1
            while self.peek() >= 0:
                var byte = self.peek()
                self.position += 1
                if byte == 34:
                    return True
                if byte < 32:
                    return False
                if byte == 92:
                    if self.peek() < 0:
                        return False
                    self.position += 1
            return False
        if opening == 91 or opening == 123:
            var object = opening == 123
            var closing = 125 if object else 93
            self.position += 1
            self.whitespace()
            if self.peek() == closing:
                self.position += 1
                return True
            while self.peek() >= 0:
                if object:
                    if self.peek() != 34 or not self.fragment(0):
                        return False
                    self.whitespace()
                    if self.peek() != 58:
                        return False
                    self.position += 1
                if not self.fragment(depth + 1):
                    return False
                self.whitespace()
                if self.peek() == closing:
                    self.position += 1
                    return True
                if self.peek() != 44:
                    return False
                self.position += 1
                self.whitespace()
            return False
        var start = self.position
        while self.peek() >= 0 and not _is_json_space(self.peek()) and self.peek() != 44 and self.peek() != 93 and self.peek() != 125:
            self.position += 1
        return self.position > start

    def value(mut self, depth: Int) raises -> Bool:
        self.whitespace()
        var byte = self.peek()
        if byte < 0:
            return self.fail("EOF while parsing a value")
        if byte == 123 or byte == 91:
            if depth >= 127:
                return self.fail("recursion limit exceeded", True)
            return self.container(byte == 123, depth + 1)
        if byte == 34:
            return self.string()
        if byte == 45 or 48 <= byte <= 57:
            return self.number()
        var literal = String("null" if byte == 110 else "true" if byte == 116 else "false" if byte == 102 else "")
        if not literal:
            return self.fail("expected value", True)
        for expected in literal.as_bytes():
            var actual = self.peek()
            if actual < 0:
                return self.fail("EOF while parsing a value")
            self.position += 1
            if actual != Int(expected):
                return self.fail("expected ident")
        return True

    def container(mut self, object: Bool, depth: Int) raises -> Bool:
        self.position += 1
        var closing = 125 if object else 93
        var first = True
        while True:
            self.whitespace()
            if self.peek() == closing:
                self.position += 1
                return True
            if self.peek() < 0:
                return self.fail("EOF while parsing an object" if object else "EOF while parsing a list")
            if not first:
                if self.peek() != 44:
                    return self.fail("expected `,` or `}`" if object else "expected `,` or `]`", True)
                self.position += 1
                self.whitespace()
                if self.peek() == closing:
                    return self.fail("trailing comma", True)
                if self.peek() < 0:
                    return self.fail("EOF while parsing a value")
            first = False
            if object:
                if self.peek() != 34:
                    return self.fail("key must be a string", True)
                if not self.string():
                    return False
                self.whitespace()
                if self.peek() < 0:
                    return self.fail("EOF while parsing an object")
                if self.peek() != 58:
                    return self.fail("expected `:`", True)
                self.position += 1
            if not self.value(depth):
                return False

    def string(mut self) -> Bool:
        self.position += 1
        while True:
            var byte = self.peek()
            if byte < 0:
                return self.fail("EOF while parsing a string")
            self.position += 1
            if byte == 34:
                return True
            if byte < 32:
                return self.fail("control character (\\u0000-\\u001F) found while parsing a string")
            if byte != 92:
                continue
            byte = self.peek()
            if byte < 0:
                return self.fail("EOF while parsing a string")
            self.position += 1
            if byte == 34 or byte == 92 or byte == 47 or byte == 98 or byte == 102 or byte == 110 or byte == 114 or byte == 116:
                continue
            if byte != 117:
                return self.fail("invalid escape")
            var code = self.hex4()
            if code < 0:
                return False
            if 0xDC00 <= code <= 0xDFFF:
                return self.fail("lone leading surrogate in hex escape")
            if 0xD800 <= code <= 0xDBFF:
                for expected in [92, 117]:
                    byte = self.peek()
                    if byte < 0:
                        return self.fail("EOF while parsing a string")
                    self.position += 1
                    if byte != expected:
                        return self.fail("unexpected end of hex escape")
                code = self.hex4()
                if code < 0:
                    return False
                if not 0xDC00 <= code <= 0xDFFF:
                    return self.fail("lone leading surrogate in hex escape")

    def hex4(mut self) -> Int:
        if self.source.byte_length() - self.position < 4:
            self.position = self.source.byte_length()
            _ = self.fail("EOF while parsing a string")
            return -1
        var value = 0
        var valid = True
        for _ in range(4):
            var byte = self.peek()
            var digit = byte - 48 if 48 <= byte <= 57 else byte - 55 if 65 <= byte <= 70 else byte - 87 if 97 <= byte <= 102 else -1
            valid = valid and digit >= 0
            value = value * 16 + max(0, digit)
            self.position += 1
        if not valid:
            _ = self.fail("invalid escape")
            return -1
        return value

    def number(mut self) raises -> Bool:
        var start = self.position
        if self.peek() == 45:
            self.position += 1
        var byte = self.peek()
        if byte < 0:
            return self.fail("EOF while parsing a value")
        self.position += 1
        if byte == 48:
            if 48 <= self.peek() <= 57:
                return self.fail("invalid number", True)
        elif 49 <= byte <= 57:
            while 48 <= self.peek() <= 57:
                self.position += 1
        else:
            return self.fail("invalid number")
        if self.peek() == 46:
            self.position += 1
            if not 48 <= self.peek() <= 57:
                return self.fail("EOF while parsing a value" if self.peek() < 0 else "invalid number", True)
            while 48 <= self.peek() <= 57:
                self.position += 1
        if self.peek() == 101 or self.peek() == 69:
            self.position += 1
            if self.peek() == 43 or self.peek() == 45:
                self.position += 1
            if self.peek() < 0:
                return self.fail("EOF while parsing a value")
            byte = self.peek()
            self.position += 1
            if not 48 <= byte <= 57:
                return self.fail("invalid number")
            while 48 <= self.peek() <= 57:
                self.position += 1
        try:
            _ = json_float(String(self.source[byte=start:self.position]))
        except:
            return self.fail("number out of range")
        return True


def _line_column(source: String, offset: Int) -> String:
    var line = 1
    var column = 0
    for index in range(offset):
        var byte = Int(source.as_bytes()[index])
        if byte == 10:
            line += 1
            column = 0
        else:
            column += 1
    return "line " + String(line) + " column " + String(column)


def _is_json_space(byte: Int) -> Bool:
    return byte == 32 or byte == 9 or byte == 10 or byte == 13
