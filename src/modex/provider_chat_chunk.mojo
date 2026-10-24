"""Chat-compatible provider choice and embedded-error decoding."""

from .json import JSON_ARRAY, JSON_NULL, JSON_NUMBER, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json, serialize_number


def chat_first_choice(doc: JsonDocument) -> Int:
    var choices = doc.get(doc.root, "choices")
    if choices < 0 or doc.nodes[choices].kind != JSON_ARRAY or not doc.nodes[choices].children:
        return -1
    return doc.nodes[choices].children[0]


def chat_choice_metadata(doc: JsonDocument, choice: Int) raises -> String:
    _check_choice(doc, choice)
    var logprobs = doc.get(choice, "logprobs")
    var value = serialize_json(doc, logprobs) if logprobs >= 0 and doc.nodes[logprobs].kind != JSON_NULL else String("null")
    return '{"finish_reason":' + _string_member(doc, choice, "finish_reason", True) + ',"logprobs":' + value + "}"


def chat_choice_delta(doc: JsonDocument, choice: Int) raises -> String:
    _check_choice(doc, choice)
    var delta = doc.get(choice, "delta")
    return ('{"annotations":' + _array_member(doc, delta, "annotations")
            + ',"content":' + _string_member(doc, delta, "content")
            + ',"reasoning_content":' + _string_member(doc, delta, "reasoning_content")
            + ',"refusal":' + _string_member(doc, delta, "refusal")
            + ',"tool_calls":' + _array_member(doc, delta, "tool_calls") + "}")


def chat_stream_error(doc: JsonDocument) -> String:
    var error = doc.get(doc.root, "error")
    if error < 0:
        return "null"
    var code = String("provider_stream_error")
    var message = String("Provider stream returned an embedded error")
    if doc.nodes[error].kind == JSON_STRING:
        message = doc.nodes[error].text
    elif doc.nodes[error].kind == JSON_OBJECT:
        var kind = doc.get(error, "type")
        if kind < 0:
            kind = doc.get(error, "code")
        if kind >= 0 and doc.nodes[kind].kind == JSON_STRING:
            code = doc.nodes[kind].text
        elif kind >= 0 and doc.nodes[kind].kind == JSON_NUMBER:
            # The frozen kernel sees serde's normalized number spelling.
            var number = serialize_number(doc.nodes[kind].text)
            var negative = number.startswith("-")
            var digits = String(number[byte=1:]) if negative else number
            var limit = "9223372036854775808" if negative else "9223372036854775807"
            if number.find(".") < 0 and number.find("e") < 0 and (digits.byte_length() < 19 or (digits.byte_length() == 19 and digits <= limit)):
                code = number^
        var detail = doc.get(error, "message")
        if detail < 0:
            detail = doc.get(error, "detail")
        if detail >= 0 and doc.nodes[detail].kind == JSON_STRING:
            message = doc.nodes[detail].text
    return '{"code":' + quote_json(code) + ',"message":' + quote_json(message) + "}"


def _check_choice(doc: JsonDocument, choice: Int) raises:
    if choice >= 0 and doc.nodes[choice].kind != JSON_OBJECT:
        raise Error("chat stream choice is not an object")


def _string_member(doc: JsonDocument, parent: Int, name: StringSlice, keep_empty: Bool = False) -> String:
    var node = doc.get(parent, name)
    # The delta kernel drops empty strings; finish_reason retains them.
    if node >= 0 and doc.nodes[node].kind == JSON_STRING and (keep_empty or doc.nodes[node].text):
        return quote_json(doc.nodes[node].text)
    return "null"


def _array_member(doc: JsonDocument, parent: Int, name: StringSlice) -> String:
    var node = doc.get(parent, name)
    if node >= 0 and doc.nodes[node].kind == JSON_ARRAY:
        return serialize_json(doc, node)
    return "[]"
