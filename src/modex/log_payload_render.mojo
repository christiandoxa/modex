"""Structured display for readable JSON upstream payloads."""

from std.collections import List

from .json import JSON_ARRAY, JSON_BOOL, JSON_OBJECT, JSON_NUMBER, JSON_STRING, JsonDocument, serialize_json
from .log_text import trim_unicode
from .text import wrap_text


def payload_lines(payload: String, width: Int) raises -> List[String]:
    var document: JsonDocument
    try:
        document = JsonDocument(payload)
    except:
        return wrap_text(payload, max(width - 4, 20))
    var kinds = List[Int]()
    var records = List[String]()
    var root = document.root
    if document.nodes[root].kind == JSON_OBJECT:
        var summary = summary_line(document, root)
        if summary:
            kinds.append(0)
            records.append(summary^)
        var metadata = metadata_line(document, root)
        if metadata:
            kinds.append(0)
            records.append(metadata^)
        var instructions = document.get(root, "instructions")
        if instructions >= 0 and document.nodes[instructions].kind == JSON_STRING:
            kinds.append(1)
            records.append("instructions:")
            kinds.append(2)
            records.append(document.nodes[instructions].text)
        var input = document.get(root, "input")
        if input >= 0 and document.nodes[input].kind == JSON_ARRAY:
            for index in range(len(document.nodes[input].children)):
                var item = document.nodes[input].children[index]
                var pair = input_item(document, item, index)
                kinds.append(1)
                records.append(pair[0])
                kinds.append(2)
                records.append(pair[1])
        elif input >= 0:
            kinds.append(1)
            records.append("input:")
            kinds.append(2)
            records.append(value_text(document, input))
        var tools = document.get(root, "tools")
        if tools >= 0 and document.nodes[tools].kind == JSON_ARRAY:
            kinds.append(0)
            records.append(tools_line(document, tools))
    if len(records) == 0:
        return wrap_text(pretty_json(document, root, 0), max(width - 4, 20))
    var lines = List[String]()
    for index in range(len(records)):
        var wrapped = wrap_text(records[index], max(width - 4, 20))
        if kinds[index] == 2:
            for line in wrapped:
                lines.append("  " + line)
        elif kinds[index] == 1:
            lines.append(records[index])
        else:
            lines.extend(wrapped^)
    return lines^


def summary_line(doc: JsonDocument, root: Int) -> String:
    var output = String()
    for key in ["model", "stream", "store", "tool_choice", "parallel_tool_calls", "prompt_cache_key"]:
        var node = doc.get(root, key)
        if node < 0:
            continue
        var kind = doc.nodes[node].kind
        if kind != JSON_STRING and kind != JSON_BOOL and kind != JSON_NUMBER:
            continue
        if output:
            output += " "
        output += key + "="
        if kind == JSON_STRING:
            var value = doc.nodes[node].text
            var count = 0
            var clipped = String()
            var length = 0
            for _ in value.codepoints():
                length += 1
            var limit = 77 if value.byte_length() > 80 else length
            for ch in value.codepoints():
                if count == limit:
                    break
                clipped += chr(Int(ch))
                count += 1
            output += clipped + "..." if value.byte_length() > 80 else value
        else:
            output += serialize_json(doc, node)
    var reasoning = doc.get(root, "reasoning")
    var effort = doc.get(reasoning, "effort")
    if effort >= 0 and doc.nodes[effort].kind == JSON_STRING:
        if output: output += " "
        output += "effort=" + doc.nodes[effort].text
    var input = doc.get(root, "input")
    var compaction = doc.get(root, "compaction") >= 0
    if input >= 0 and doc.nodes[input].kind == JSON_ARRAY:
        var images = 0
        var audio = 0
        for item in doc.nodes[input].children:
            images += Int(has_type(doc, item, "input_image"))
            audio += Int(has_type(doc, item, "input_audio"))
            var item_type = doc.get(item, "type")
            compaction = compaction or (item_type >= 0 and doc.nodes[item_type].kind == JSON_STRING and doc.nodes[item_type].text == "compaction")
        if output: output += " "
        output += "input_items=" + String(len(doc.nodes[input].children))
        if images: output += " images=" + String(images)
        if audio: output += " audio=" + String(audio)
    var tools = doc.get(root, "tools")
    if tools >= 0 and doc.nodes[tools].kind == JSON_ARRAY:
        if output: output += " "
        output += "tools=" + String(len(doc.nodes[tools].children))
    if doc.get(root, "previous_response_id") >= 0:
        if output: output += " "
        output += "continuation=previous_response"
    if compaction:
        if output: output += " "
        output += "compaction=yes"
    return output^


def metadata_line(doc: JsonDocument, root: Int) -> String:
    var metadata = doc.get(root, "client_metadata")
    var output = String()
    for key in ["session_id", "thread_id", "turn_id", "context_window_id", "x-codex-window-id", "x-codex-installation-id"]:
        var node = doc.get(metadata, key)
        if node < 0 or doc.nodes[node].kind != JSON_STRING:
            continue
        if not output:
            output = "client_metadata:"
        output += " "
        if key == "context_window_id":
            var value = doc.nodes[node].text
            var end = 4
            if value.byte_length() > 4 and (Int(value.as_bytes()[4]) & 0xC0) == 0x80:
                end = value.byte_length()
            if value.byte_length() < 4:
                end = value.byte_length()
            output += "ctx=" + value[byte=0:end]
        else:
            output += key + "=" + doc.nodes[node].text
    return output^


def has_type(doc: JsonDocument, item: Int, wanted: String) -> Bool:
    var kind = doc.get(item, "type")
    if kind >= 0 and doc.nodes[kind].kind == JSON_STRING and doc.nodes[kind].text == wanted:
        return True
    var content = doc.get(item, "content")
    if content >= 0 and doc.nodes[content].kind == JSON_ARRAY:
        for child in doc.nodes[content].children:
            var child_type = doc.get(child, "type")
            if child_type >= 0 and doc.nodes[child_type].kind == JSON_STRING and doc.nodes[child_type].text == wanted:
                return True
    return False


def input_item(doc: JsonDocument, item: Int, index: Int) -> Tuple[String, String]:
    var type_node = doc.get(item, "type")
    var item_type = doc.nodes[type_node].text if type_node >= 0 and doc.nodes[type_node].kind == JSON_STRING else ""
    var call = item_type == "function_call"
    var output = item_type == "function_call_output"
    var header = "input[" + String(index) + "]"
    var body: String
    if call or output:
        if call:
            var name = doc.get(item, "name")
            header += " tool-call:" + (doc.nodes[name].text if name >= 0 and doc.nodes[name].kind == JSON_STRING else "tool")
            var argument = doc.get(item, "arguments")
            body = value_text(doc, argument) if argument >= 0 else ""
            if argument >= 0 and doc.nodes[argument].kind == JSON_STRING:
                body = pretty_json_if_json(doc.nodes[argument].text)
        else:
            header += " tool-output"
            var value = doc.get(item, "output")
            body = value_text(doc, value) if value >= 0 else ""
            if value >= 0 and doc.nodes[value].kind == JSON_STRING:
                body = pretty_json_if_json(doc.nodes[value].text)
    elif doc.nodes[item].kind == JSON_OBJECT:
        var role = doc.get(item, "role")
        if role < 0: role = type_node
        header += " " + (doc.nodes[role].text if role >= 0 and doc.nodes[role].kind == JSON_STRING else "message") + ":"
        var content = doc.get(item, "content")
        var text = doc.get(item, "text")
        if content >= 0 and nonblank(doc, content):
            body = content_text(doc, content)
        elif text >= 0 and doc.nodes[text].kind == JSON_STRING:
            body = doc.nodes[text].text
        else:
            body = pretty_json(doc, item, 0)
    else:
        header += ":"
        body = pretty_json(doc, item, 0)
    if call or output:
        header += ":"
    return (header^, body^)


def nonblank(doc: JsonDocument, node: Int) -> Bool:
    var kind = doc.nodes[node].kind
    if kind == JSON_STRING:
        return trim_unicode(doc.nodes[node].text) != ""
    if kind == JSON_ARRAY:
        for child in doc.nodes[node].children:
            if nonblank(doc, child): return True
        return False
    if kind == JSON_OBJECT:
        for key in ["text", "content", "input_text", "output_text"]:
            var child = doc.get(node, key)
            if child >= 0: return nonblank(doc, child)
    return True


def content_text(doc: JsonDocument, node: Int) -> String:
    var kind = doc.nodes[node].kind
    if kind == JSON_STRING: return doc.nodes[node].text
    if kind == JSON_ARRAY:
        var result = String()
        var first = True
        for child in doc.nodes[node].children:
            if nonblank(doc, child):
                if not first: result += "\n"
                result += content_text(doc, child)
                first = False
        return result^
    if kind == JSON_OBJECT:
        for key in ["text", "content", "input_text", "output_text"]:
            var child = doc.get(node, key)
            if child >= 0: return content_text(doc, child)
    return pretty_json(doc, node, 0)


def tools_line(doc: JsonDocument, tools: Int) -> String:
    var output = "tools: " + String(len(doc.nodes[tools].children))
    var first = True
    for item in doc.nodes[tools].children:
        var name = doc.get(item, "name")
        if name < 0:
            var function = doc.get(item, "function")
            name = doc.get(function, "name")
        if name >= 0 and doc.nodes[name].kind == JSON_STRING:
            output += (" " if first else ", ") + doc.nodes[name].text
            first = False
    return output^


def value_text(doc: JsonDocument, node: Int) -> String:
    if doc.nodes[node].kind == JSON_STRING:
        return doc.nodes[node].text
    return pretty_json(doc, node, 0)


def pretty_json_if_json(value: String) -> String:
    try:
        var doc = JsonDocument(value)
        return pretty_json(doc, doc.root, 0)
    except:
        return value


def pretty_json(doc: JsonDocument, node: Int, depth: Int) -> String:
    return serialize_json(doc, node, 2, depth)
