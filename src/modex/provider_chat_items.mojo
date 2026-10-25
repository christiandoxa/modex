"""Responses tool items emitted from chat-compatible provider calls."""

from std.collections import List

from .json import JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json
from .rtk_command import prefixed_noisy_command
from .text import trim_text


def tool_added_item(call_id: String, name: String) -> Optional[String]:
    if name == "tool_search":
        return Optional[String]()
    if name == "apply_patch":
        return Optional[String]('{"type":"custom_tool_call","call_id":' + quote_json(call_id) + ',"name":"apply_patch","input":""}')
    var (namespace, item_name) = _split_name(name)
    var item = '{"type":"function_call","call_id":' + quote_json(call_id) + ',"name":' + quote_json(item_name)
    if namespace:
        item += ',"namespace":' + quote_json(namespace)
    return Optional[String](item + "}")


def tool_output_item(call_id: String, name: String, arguments: String, signature: Optional[String]) raises -> String:
    if name == "tool_search":
        var args = String("{}")
        try:
            var doc = JsonDocument(arguments)
            args = serialize_json(doc, doc.root)
        except:
            pass
        return '{"type":"tool_search_call","call_id":' + quote_json(call_id) + ',"execution":"client","arguments":' + args + "}"
    if name == "apply_patch":
        var input = arguments
        try:
            var doc = JsonDocument(arguments)
            if doc.nodes[doc.root].kind == JSON_STRING:
                input = _patch_text(doc.nodes[doc.root].text)
            elif doc.nodes[doc.root].kind == JSON_OBJECT:
                var explicit = _first_string(doc, doc.root, ["input", "patch", "diff", "text"])
                if explicit:
                    input = _patch_text(explicit.value())
                else:
                    var path = _first_string(doc, doc.root, ["file_path", "path", "filename"])
                    var old = _first_string(doc, doc.root, ["old_string", "old", "search", "find"])
                    var replacement = _first_string(doc, doc.root, ["new_string", "new", "replace", "replacement", "content"])
                    var content = _first_string(doc, doc.root, ["content"])
                    var clean_path = trim_text(path.value()) if path else ""
                    if path and clean_path.byte_length() > 0 and replacement:
                        var before = old.value() if old else ""
                        var after = replacement.value() if replacement else ""
                        if not before:
                            input = _added_file(clean_path, after)
                        else:
                            input = "*** Begin Patch\n*** Update File: " + clean_path + "\n@@\n"
                            for line in _patch_lines(before):
                                input += "-" + line + "\n"
                            if after:
                                for line in _patch_lines(after):
                                    input += "+" + line + "\n"
                            input += "*** End Patch"
                    elif content:
                        input = _patch_text(content.value())
                    else:
                        input = serialize_json(doc, doc.root)
            else:
                input = serialize_json(doc, doc.root)
        except:
            pass
        return '{"type":"custom_tool_call","call_id":' + quote_json(call_id) + ',"name":"apply_patch","input":' + quote_json(input) + "}"
    var (namespace, item_name) = _split_name(name)
    var result = '{"type":"function_call","call_id":' + quote_json(call_id) + ',"name":' + quote_json(item_name) + ',"arguments":' + quote_json(arguments)
    if namespace:
        result += ',"namespace":' + quote_json(namespace)
    if signature and signature.value():
        result += ',"gemini_thought_signature":' + quote_json(signature.value())
    return result + "}"


def wrap_tool_arguments(name: String, arguments: String) raises -> String:
    if not (name == "shell" or name == "exec_command" or name == "exec" or name == "functions.exec_command") or not arguments:
        return arguments
    try:
        var doc = JsonDocument(arguments)
        if doc.nodes[doc.root].kind != JSON_OBJECT:
            return arguments
        var key = "cmd"
        var command = doc.get(doc.root, key)
        if name == "shell" or name == "exec_command":
            if command < 0:
                key = "command"
                command = doc.get(doc.root, key)
        if command < 0 or doc.nodes[command].kind != JSON_STRING:
            return arguments
        var rewritten = prefixed_noisy_command(doc.nodes[command].text)
        if not rewritten:
            return arguments
        doc.nodes[command].text = rewritten.value()
        return serialize_json(doc, doc.root)
    except:
        return arguments


def _split_name(name: String) -> Tuple[String, String]:
    for offset in range(name.byte_length() - 2, -1, -1):
        if name.as_bytes()[offset] == 45 and name.as_bytes()[offset + 1] == 45:
            var prefix = String(name[byte=:offset])
            var suffix = String(name[byte=offset + 2:])
            if trim_text(prefix) and trim_text(suffix):
                return (prefix, suffix)
    if name.startswith("mcp__"):
        var split = name.rfind("__")
        if split > 0 and split + 2 < name.byte_length():
            var suffix = String(name[byte=split + 2:])
            if trim_text(suffix):
                return (String(name[byte=:split]), suffix)
    return (String(), name)


def _first_string(doc: JsonDocument, node: Int, names: List[String]) -> Optional[String]:
    for name in names:
        var value = doc.get(node, name)
        if value >= 0 and doc.nodes[value].kind == JSON_STRING:
            return Optional[String](doc.nodes[value].text)
    return Optional[String]()


def _added_file(path: String, content: String) -> String:
    var result = "*** Begin Patch\n*** Add File: " + path + "\n"
    for line in _patch_lines(content):
        result += "+" + line + "\n"
    return result + "*** End Patch"


def _patch_lines(content: String) -> List[String]:
    var lines = List[String]()
    var normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    for line in normalized.split("\n"):
        lines.append(String(line))
    if normalized and normalized.endswith("\n"):
        _ = lines.pop()
    return lines^


def _patch_text(text: String) -> String:
    var normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    var lines = normalized.split("\n")
    var begin = -1
    var finish = -1
    for index in range(len(lines)):
        var trimmed = trim_text(lines[index])
        if begin < 0 and trimmed.startswith("*** Begin Patch"):
            begin = index
        elif begin >= 0 and trimmed.startswith("*** End Patch"):
            finish = index
            break
    if begin < 0 or finish < begin:
        var converted = _unified_diff(text)
        if converted:
            return converted.value()
        return text
    var output = String()
    var in_file = False
    for index in range(begin, finish + 1):
        var line = lines[index]
        if index > begin:
            output += "\n"
        if line.startswith("*** Add File: "):
            in_file = True
        elif line.startswith("*** "):
            in_file = False
        elif in_file and not line.startswith("+"):
            output += "+"
        output += line
    return output


def _unified_diff(text: String) -> Optional[String]:
    var normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    var lines = List[String]()
    for line in normalized.split("\n"):
        lines.append(String(line))
    var output = "*** Begin Patch\n"
    var position = 0
    var converted = False
    while position < len(lines):
        var git_section = False
        if lines[position].startswith("diff --git "):
            git_section = True
        elif not _header_pair(lines, position):
            position += 1
            continue
        var section_end = position + 1
        if not git_section:
            section_end += 1
        while section_end < len(lines) and not lines[section_end].startswith("diff --git ") and (git_section or not _header_pair(lines, section_end)):
            section_end += 1
        var header = position
        while header < section_end and not _header_pair(lines, header):
            header += 1
        if header >= section_end:
            position = section_end
            continue
        var old_path = _diff_path(String(lines[header][byte=4:]))
        var new_path = _diff_path(String(lines[header + 1][byte=4:]))
        position = header + 2
        var section = String()
        if not old_path and new_path:
            section = "*** Add File: " + new_path + "\n"
            var saw_added = False
            for index in range(position, section_end):
                var line = lines[index]
                if line.startswith("+") and not line.startswith("+++"):
                    section += line + "\n"
                    saw_added = True
            if not saw_added:
                section = ""
        elif old_path and not new_path:
            section = "*** Delete File: " + old_path + "\n"
        elif old_path and new_path:
            section = "*** Update File: " + old_path + "\n"
            if old_path != new_path:
                section += "*** Move to: " + new_path + "\n"
            var saw_hunk = False
            var saw_change = False
            for index in range(position, section_end):
                var line = lines[index]
                if line.startswith("@@"):
                    section += _hunk_header(line) + "\n"
                    saw_hunk = True
                elif saw_hunk and line and (line.startswith("+") or line.startswith("-") or line.startswith(" ")):
                    section += line + "\n"
                    if line.startswith("+") or line.startswith("-"):
                        saw_change = True
                elif saw_hunk and line == "\\ No newline at end of file":
                    section += "*** End of File\n"
            if not saw_change:
                section = ""
        if section:
            output += section
            converted = True
        position = section_end
    if not converted:
        return Optional[String]()
    return Optional[String](output + "*** End Patch")


def _header_pair(lines: List[String], index: Int) -> Bool:
    return index + 1 < len(lines) and lines[index].startswith("--- ") and lines[index + 1].startswith("+++ ")


def _diff_path(header: String) -> String:
    var path = header
    if path.startswith("\"") and path.endswith("\"") and path.byte_length() >= 2:
        var unquoted = String(path[byte=1:path.byte_length() - 1])
        path = unquoted
    if path == "/dev/null":
        return ""
    if path.startswith("a/") or path.startswith("b/"):
        var without_prefix = String(path[byte=2:])
        path = without_prefix
    return _ascii_trim(path)


def _hunk_header(line: String) -> String:
    var close = line.find("@@", 2)
    if close < 0:
        return "@@"
    var context = _ascii_trim(String(line[byte=close + 2:]))
    return "@@" + (" " + context if context else "")


def _ascii_trim(text: String) -> String:
    var start = 0
    var end = text.byte_length()
    while start < end and (text.as_bytes()[start] == 32 or 9 <= Int(text.as_bytes()[start]) <= 13):
        start += 1
    while start < end and (text.as_bytes()[end - 1] == 32 or 9 <= Int(text.as_bytes()[end - 1]) <= 13):
        end -= 1
    return String(text[byte=start:end])
