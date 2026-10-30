"""Bounded local fallback for Responses compact requests."""

from std.collections import List, Span

from .json import JSON_ARRAY, JSON_BOOL, JSON_NULL, JSON_NUMBER, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json
from .text import is_whitespace, trim_text

comptime LOCAL_COMPACT_MAX_SNIPPETS = 24
comptime LOCAL_COMPACT_MAX_SNIPPET_BYTES = 768
comptime LOCAL_COMPACT_TEXT_BYTES = LOCAL_COMPACT_MAX_SNIPPET_BYTES + 1
comptime LOCAL_COMPACT_MAX_SUMMARY_BYTES = 24 * 1024
comptime LOCAL_COMPACT_SUMMARY_PREFIX = "Another language model started to solve this problem and produced a summary of its thinking process. You also have access to the state of the tools that were used by that language model. Use this to build on the work that has already been done and avoid duplicating work. Here is the summary produced by the other language model, use the information in this summary to assist with your own analysis:"


def _compact_has_text(text: String) -> Bool:
    for character in text.codepoints():
        if not is_whitespace(Int(character)):
            return True
    return False


def _compact_prefix(text: String, maximum: Int) -> String:
    if text.byte_length() <= maximum:
        return text
    var bytes = text.as_bytes()
    var end = maximum
    while end > 0 and (Int(bytes[end]) & 192) == 128:
        end -= 1
    return String(text[byte=:end])


def _compact_append_text(mut output: List[UInt8], text: String, maximum: Int):
    var available = maximum - len(output)
    if available <= 0:
        return
    var bytes = text.as_bytes()
    var take = min(len(bytes), available)
    if take < len(bytes):
        while take > 0 and (Int(bytes[take]) & 192) == 128:
            take -= 1
    for index in range(take):
        output.append(bytes[index])


def _compact_rollback(mut output: List[UInt8], length: Int):
    while len(output) > length:
        _ = output.pop()


def _compact_extract(mut output: List[UInt8], doc: JsonDocument, node: Int, depth: Int, maximum: Int) -> Int:
    if node < 0 or depth > 256:
        return 0
    var kind = doc.nodes[node].kind
    if kind == JSON_STRING:
        var text = doc.nodes[node].text
        var has_text = _compact_has_text(text)
        if has_text or depth == 0:
            _compact_append_text(output, text, maximum)
        return 1 if has_text else 2
    if kind == JSON_NULL:
        return 0
    if kind == JSON_BOOL or kind == JSON_NUMBER:
        _compact_append_text(output, serialize_json(doc, node), maximum)
        return 1
    if kind == JSON_ARRAY:
        var found = False
        for child in doc.nodes[node].children:
            if found and len(output) >= maximum:
                return 1
            var before = len(output)
            if found:
                _compact_append_text(output, "\n", maximum)
            var result = _compact_extract(output, doc, child, depth + 1, maximum)
            if result != 1:
                _compact_rollback(output, before)
            else:
                found = True
        return 1 if found else 0
    if kind != JSON_OBJECT:
        return 0

    for key in ["text", "output", "input", "query", "command", "commands"]:
        var before = len(output)
        var result = _compact_extract(output, doc, doc.get(node, key), depth + 1, maximum)
        if result == 1:
            return 1
        _compact_rollback(output, before)

    var fields = List[Tuple[String, Int]]()
    for index in range(len(doc.nodes[node].children)):
        fields.append((doc.nodes[node].names[index], doc.nodes[node].children[index]))
    sort(Span(fields), lambda (left: Tuple[String, Int], right: Tuple[String, Int]) -> Bool:
         left[0] < right[0] or (left[0] == right[0] and left[1] < right[1]))
    var found = False
    for index in range(len(fields)):
        if index + 1 < len(fields) and fields[index][0] == fields[index + 1][0]:
            continue
        if found and len(output) >= maximum:
            return 1
        var before = len(output)
        if found:
            _compact_append_text(output, "\n", maximum)
        var result = _compact_extract(output, doc, fields[index][1], depth + 1, maximum)
        if result != 1:
            _compact_rollback(output, before)
        else:
            found = True
    return 1 if found else 0


def _compact_text(doc: JsonDocument, node: Int, maximum: Int = LOCAL_COMPACT_TEXT_BYTES) -> Tuple[Int, String]:
    var output = List[UInt8]()
    var result = _compact_extract(output, doc, node, 0, maximum)
    if result == 0:
        return 0, String()
    try:
        return result, String(from_utf8=Span(output))
    except:
        return 0, String()


def _compact_field(doc: JsonDocument, item: Int, field: String) -> Tuple[Int, String]:
    return _compact_text(doc, doc.get(item, field))


def _compact_optional_string(doc: JsonDocument, item: Int, field: String) -> Tuple[Bool, String]:
    var node = doc.get(item, field)
    if node >= 0 and doc.nodes[node].kind == JSON_STRING:
        return True, _compact_prefix(doc.nodes[node].text, LOCAL_COMPACT_TEXT_BYTES)
    return False, String()


def _compact_trimmed_model(text: String) -> String:
    var start = -1
    var offset = 0
    for character in text.codepoints():
        var width = chr(Int(character)).byte_length()
        if not is_whitespace(Int(character)):
            start = offset
            break
        offset += width
    if start < 0:
        return ""
    var bytes = text.as_bytes()
    var end = min(text.byte_length(), start + LOCAL_COMPACT_MAX_SUMMARY_BYTES + 1)
    if end < text.byte_length():
        while end > start and (Int(bytes[end]) & 192) == 128:
            end -= 1
    var prefix = String(text[byte=start:end])
    return trim_text(prefix) if end == text.byte_length() else prefix^


def _compact_truncate(text: String, maximum: Int) -> String:
    if text.byte_length() <= maximum:
        return text
    var suffix = String("\n[truncated]")
    if maximum <= suffix.byte_length():
        return String(suffix[byte=:maximum])
    var bytes = text.as_bytes()
    var end = maximum - suffix.byte_length()
    while end > 0 and (Int(bytes[end]) & 192) == 128:
        end -= 1
    return String(text[byte=:end]) + suffix


def _compact_snippet(doc: JsonDocument, item: Int) -> String:
    if item < 0 or doc.nodes[item].kind != JSON_OBJECT:
        return ""
    var (has_type, item_type) = _compact_optional_string(doc, item, "type")
    var snippet: String

    if has_type and item_type == "message":
        var content = _compact_field(doc, item, "content")
        var message_status = content[0]
        var message_text = content[1]
        if message_status == 0:
            var text_node = doc.get(item, "text")
            if text_node >= 0 and doc.nodes[text_node].kind == JSON_STRING:
                var text = _compact_text(doc, text_node)
                message_status = text[0]
                message_text = text[1]
        var role = _compact_optional_string(doc, item, "role")
        snippet = (role[1] if role[0] else "unknown") + " message"
        if message_status == 1:
            snippet += ": " + message_text
        else:
            snippet += " with no text content"
    elif has_type and item_type == "function_call":
        var name = _compact_optional_string(doc, item, "name")
        var call_id = _compact_optional_string(doc, item, "call_id")
        var arguments = _compact_field(doc, item, "arguments")
        snippet = "tool call " + (name[1] if name[0] else "function") + " (" + (call_id[1] if call_id[0] else "unknown") + "): " + arguments[1]
    elif has_type and item_type == "custom_tool_call":
        var name = _compact_optional_string(doc, item, "name")
        var call_id = _compact_optional_string(doc, item, "call_id")
        var tool_input = _compact_field(doc, item, "input")
        snippet = "custom tool call " + (name[1] if name[0] else "custom_tool") + " (" + (call_id[1] if call_id[0] else "unknown") + "): " + tool_input[1]
    elif has_type and (item_type == "function_call_output" or item_type == "custom_tool_call_output"):
        var call_id = _compact_optional_string(doc, item, "call_id")
        var tool_output = _compact_field(doc, item, "output")
        snippet = "tool output " + (call_id[1] if call_id[0] else "unknown") + ": " + tool_output[1]
    elif has_type and item_type == "local_shell_call":
        var call_id = _compact_optional_string(doc, item, "call_id")
        var action = _compact_field(doc, item, "action")
        snippet = "local shell call " + (call_id[1] if call_id[0] else "unknown") + ": " + action[1]
    elif has_type and item_type == "web_search_call":
        var action = _compact_field(doc, item, "action")
        snippet = "web search: " + action[1]
    elif has_type and item_type == "reasoning":
        var summary = _compact_field(doc, item, "summary")
        if summary[0] != 1:
            return ""
        snippet = "reasoning summary: " + summary[1]
    else:
        var generic = _compact_text(doc, item)
        if generic[0] != 1:
            return ""
        snippet = (item_type if has_type else "item") + ": " + generic[1]
    return _compact_truncate(snippet, LOCAL_COMPACT_MAX_SNIPPET_BYTES)


def local_compact_summary(body: List[UInt8]) -> String:
    var source: String
    try:
        source = String(from_utf8=Span(body))
    except:
        return "Local Prodex compact fallback could not parse the compact request body."
    var doc: JsonDocument
    try:
        doc = JsonDocument(source)
    except:
        return "Local Prodex compact fallback could not parse the compact request body."

    var model_node = doc.get(doc.root, "model")
    var model = _compact_trimmed_model(doc.nodes[model_node].text) if model_node >= 0 and doc.nodes[model_node].kind == JSON_STRING else String()
    if not model:
        model = "unknown"
    var input = doc.get(doc.root, "input")
    var item_count = 0
    var snippets = List[String]()
    if input >= 0 and doc.nodes[input].kind == JSON_ARRAY:
        item_count = len(doc.nodes[input].children)
        for item in doc.nodes[input].children:
            var snippet = _compact_snippet(doc, item)
            if snippet:
                if len(snippets) == LOCAL_COMPACT_MAX_SNIPPETS:
                    _ = snippets.pop(0)
                snippets.append(snippet^)

    var summary = String("Local Prodex compact fallback summary.\n\nModel: ") + model
    summary += "\nOriginal input items: " + String(item_count)
    summary += "\nRetained recent items: " + String(len(snippets))
    summary += "\n\nRecent conversation and tool state:\n"
    if not snippets:
        summary += "- No parseable recent message or tool content was found.\n"
    else:
        for snippet in snippets:
            summary += "- " + snippet.replace("\n", "\n  ") + "\n"
    return _compact_truncate(summary, LOCAL_COMPACT_MAX_SUMMARY_BYTES)


def local_compact_response_body(summary: String) -> String:
    var text = LOCAL_COMPACT_SUMMARY_PREFIX + "\n\n" + trim_text(summary)
    return "{\"output\":[{\"type\":\"message\",\"role\":\"user\",\"content\":[{\"type\":\"input_text\",\"text\":" + quote_json(text) + "}]}]}"
