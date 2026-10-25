"""DeepSeek request tool translation and validation."""

from std.collections import List
from .json import JSON_ARRAY, JSON_BOOL, JSON_NULL, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json
from .text import trim_text
from .json_float import json_float


def request_tool_fields(
    doc: JsonDocument,
    thinking_enabled: Bool = False,
    strict_tools: Bool = False,
    web_search_mode: String = "auto",
) raises -> String:
    var root = doc.root
    var tools_node = doc.get(root, "tools")
    var converted = List[String]()
    var tool_names = List[String]()
    var web = doc.get(root, "web_search_options")
    var explicit_web = web >= 0
    _validate_tools_shape(doc, root, tools_node)
    if tools_node >= 0:
        for node in doc.nodes[tools_node].children:
            var kind = _str(doc, node, "type")
            if _is_web(kind):
                if web < 0:
                    web = node
                continue
            var function = doc.get(node, "function")
            var body = function if kind == "function" and function >= 0 and doc.nodes[function].kind == JSON_OBJECT else node
            var name = _str(doc, body, "name")
            var has_schema = False
            for key in ["parameters", "parametersJsonSchema", "input_schema", "schema"]:
                has_schema = has_schema or doc.get(node, key) >= 0
            if kind == "custom" and trim_text(name):
                _add_tool(_function_tool(doc, node, "custom", name), converted, tool_names, strict_tools)
            elif trim_text(name) and (kind == "function" or has_schema and (kind.startswith("mcp") or name.startswith("mcp__"))):
                _add_tool(_function_tool(doc, body, "function", name), converted, tool_names, strict_tools)
            if kind == "namespace":
                _namespace(doc, node, converted, tool_names, strict_tools)
            if kind == "tool_search":
                _add_tool(_function_tool(doc, node, "tool_search", "tool_search"), converted, tool_names, strict_tools)
            if kind == "mcp" or kind == "mcp_toolset":
                _mcp_tools(doc, node, converted, tool_names, strict_tools)
        var function_count = 0
        for tool in converted:
            if tool: function_count += 1
        if function_count > 128:
            raise Error("DeepSeek supports at most 128 function tools")
    if not explicit_web:
        _validate_web_context(doc, tools_node)

    var tools_out = ""
    if converted:
        tools_out = "\"tools\":["
        var wrote_tool = False
        for i in range(len(converted)):
            if not converted[i]: continue
            if wrote_tool: tools_out += ","
            tools_out += converted[i]
            wrote_tool = True
        tools_out += "]"
    var web_out = ""
    if web >= 0:
        if web_search_mode == "off":
            raise Error("DeepSeek web search mode is off; remove web_search tools or set deepseek.web_search_mode")
        var is_tool = not explicit_web
        if not is_tool and doc.nodes[web].kind != JSON_OBJECT:
            raise Error("DeepSeek web_search_options must be an object")
        var size = doc.get(web, "search_context_size")
        if size < 0 and is_tool: size = doc.get(web, "context_size")
        if size >= 0 and (doc.nodes[size].kind != JSON_STRING or (doc.nodes[size].text != "low" and doc.nodes[size].text != "medium" and doc.nodes[size].text != "high")):
            raise Error("DeepSeek web_search search_context_size must be low, medium, or high")
        _validate_web_options(doc, web, is_tool)
        web_out = "\"web_search_options\":"
        if is_tool:
            web_out += "{"
            var first = True
            for key in ["search_context_size", "allowed_domains", "blocked_domains", "max_uses", "user_location"]:
                var member = doc.get(web, key)
                if key == "search_context_size" and member < 0: member = doc.get(web, "context_size")
                if key == "user_location" and member < 0: member = doc.get(web, "location")
                if member >= 0:
                    if not first: web_out += ","
                    web_out += quote_json(key) + ":" + serialize_json(doc, member)
                    first = False
            web_out += "}"
        else:
            web_out += serialize_json(doc, web)
    var choice_out = ""
    var choice = doc.get(root, "tool_choice")
    if choice >= 0:
        if not thinking_enabled:
            var selected_choice = _choice(doc, choice, tool_names)
            if selected_choice: choice_out = "\"tool_choice\":" + selected_choice
    var output = "{"
    var first_output = True
    for field in [choice_out, tools_out, web_out]:
        if field:
            if not first_output: output += ","
            output += field
            first_output = False
    return output + "}"


def _str(doc: JsonDocument, node: Int, key: String) -> String:
    var item = doc.get(node, key)
    if item >= 0 and doc.nodes[item].kind == JSON_STRING:
        return doc.nodes[item].text
    return ""


def _first_string_node(doc: JsonDocument, node: Int, keys: List[String]) -> Int:
    for key in keys:
        var member = doc.get(node, key)
        if member >= 0 and doc.nodes[member].kind == JSON_STRING:
            return member
    return -1


def _is_web(kind: String) -> Bool:
    return kind == "web_search" or kind == "web_search_preview" or kind.startswith("web_search_preview_")


def _validate_tools_shape(doc: JsonDocument, root: Int, tools: Int) raises:
    if tools < 0: return
    if doc.nodes[tools].kind != JSON_ARRAY: raise Error("DeepSeek tools must be an array")
    for node in doc.nodes[tools].children:
        if doc.nodes[node].kind != JSON_OBJECT: raise Error("DeepSeek tools entries must be objects")
        var type_node = doc.get(node, "type")
        if type_node < 0 or doc.nodes[type_node].kind != JSON_STRING: continue
        var kind = doc.nodes[type_node].text
        if not (kind == "function" or kind == "custom" or kind == "namespace" or kind == "tool_search" or kind == "mcp" or kind == "mcp_toolset" or kind == "web_search" or kind == "web_search_preview" or kind.startswith("mcp") or kind.startswith("web_search_preview_")):
            raise Error("DeepSeek tool type `" + kind + "` is not supported")
        if _bad_type(doc, node, "description", JSON_STRING): raise Error("DeepSeek tool description must be a string")
        var function_node = doc.get(node, "function")
        if function_node >= 0 and doc.nodes[function_node].kind == JSON_OBJECT:
            if _bad_type(doc, function_node, "description", JSON_STRING): raise Error("DeepSeek function description must be a string")
            if _bad_type(doc, function_node, "strict", JSON_BOOL): raise Error("DeepSeek function strict must be a boolean")
        if _bad_type(doc, node, "strict", JSON_BOOL): raise Error("DeepSeek tool strict must be a boolean")
        if (kind == "function" or kind == "custom") and not _tool_name(doc, node):
            raise Error("DeepSeek " + kind + " tools require a name")
        if kind == "custom":
            var strict = doc.get(node, "strict")
            if strict >= 0 and doc.nodes[strict].text == "true": raise Error("DeepSeek custom tools cannot preserve strict=true through the function wrapper")
            var format = doc.get(node, "format")
            if format >= 0 and doc.nodes[format].kind != JSON_OBJECT: raise Error("DeepSeek custom tool format must be an object")
            if format >= 0 and _bad_type(doc, format, "type", JSON_STRING): raise Error("DeepSeek custom tool format.type must be a string")
        if kind == "namespace": _validate_namespace(doc, node)
        if kind == "mcp" or kind == "mcp_toolset": _validate_mcp_toolset(doc, node)
        elif kind.startswith("mcp"):
            var name = _str(doc, node, "name")
            if not trim_text(name): raise Error("DeepSeek MCP function tools require a name")
            if doc.get(node, "parameters") < 0 and doc.get(node, "parametersJsonSchema") < 0 and doc.get(node, "input_schema") < 0 and doc.get(node, "schema") < 0: raise Error("DeepSeek MCP function tool `" + name + "` requires a schema")


def _bad_type(doc: JsonDocument, node: Int, key: String, kind: Int) -> Bool:
    var member = doc.get(node, key)
    return member >= 0 and doc.nodes[member].kind != kind


def _tool_name(doc: JsonDocument, node: Int) -> String:
    var name = doc.get(node, "name")
    if name < 0 or doc.nodes[name].kind != JSON_STRING:
        name = doc.get(doc.get(node, "function"), "name")
    if name >= 0 and doc.nodes[name].kind == JSON_STRING and trim_text(doc.nodes[name].text): return doc.nodes[name].text
    return ""


def _validate_namespace(doc: JsonDocument, node: Int) raises:
    var name = _str(doc, node, "name")
    if not trim_text(name): raise Error("DeepSeek namespace tools require a name")
    var tools = doc.get(node, "tools")
    if tools < 0 or doc.nodes[tools].kind != JSON_ARRAY: raise Error("DeepSeek namespace tool `" + name + "` requires a tools array")
    if not doc.nodes[tools].children: raise Error("DeepSeek namespace tool `" + name + "` requires at least one tool")
    for child in doc.nodes[tools].children:
        if doc.nodes[child].kind != JSON_OBJECT: raise Error("DeepSeek namespace tool `" + name + "` entries must be objects")
        if _bad_type(doc, child, "description", JSON_STRING): raise Error("DeepSeek namespace function description must be a string")
        if _bad_type(doc, child, "strict", JSON_BOOL): raise Error("DeepSeek namespace function strict must be a boolean")
        if _str(doc, child, "type") != "function": raise Error("DeepSeek namespace tool `" + name + "` entries must be function tools")
        var child_name = doc.get(child, "name")
        if child_name < 0 or doc.nodes[child_name].kind != JSON_STRING or not trim_text(doc.nodes[child_name].text): raise Error("DeepSeek namespace tool `" + name + "` function entries require a name")


def _validate_mcp_toolset(doc: JsonDocument, node: Int) raises:
    var declares = doc.get(node, "allowed_tools") >= 0 or doc.get(node, "configs") >= 0
    if not declares: return
    var server = String()
    for key in ["mcp_server_name", "server_label", "server_name", "name"]:
        server = _str(doc, node, key)
        if trim_text(server): break
    if not trim_text(server): raise Error("DeepSeek MCP toolsets require a server name")
    var allowed = doc.get(node, "allowed_tools")
    var has_allowed = False
    if allowed >= 0 and doc.nodes[allowed].kind == JSON_ARRAY:
        for item in doc.nodes[allowed].children:
            if doc.nodes[item].kind == JSON_STRING and trim_text(doc.nodes[item].text): has_allowed = True
    var configs = doc.get(node, "configs")
    var has_enabled = False
    if configs >= 0 and doc.nodes[configs].kind == JSON_OBJECT:
        var default_config = doc.get(node, "default_config")
        var default_flag = doc.get(default_config, "enabled")
        var default_enabled = default_flag < 0 or doc.nodes[default_flag].kind != JSON_BOOL or doc.nodes[default_flag].text != "false"
        for config in doc.nodes[configs].children:
            var flag = doc.get(config, "enabled")
            var enabled = default_enabled
            if flag >= 0 and doc.nodes[flag].kind == JSON_BOOL:
                enabled = doc.nodes[flag].text == "true"
            if enabled: has_enabled = True
    if not has_allowed and not has_enabled: raise Error("DeepSeek MCP toolset `" + server + "` requires allowed_tools or enabled configs")


def _validate_web_context(doc: JsonDocument, tools: Int) raises:
    if tools < 0 or doc.nodes[tools].kind != JSON_ARRAY: return
    for node in doc.nodes[tools].children:
        if not _is_web(_str(doc, node, "type")): continue
        var size = doc.get(node, "search_context_size")
        if size < 0: size = doc.get(node, "context_size")
        if size >= 0 and (doc.nodes[size].kind != JSON_STRING or (doc.nodes[size].text != "low" and doc.nodes[size].text != "medium" and doc.nodes[size].text != "high")):
            raise Error("DeepSeek web_search context_size must be low, medium, or high")


def _validate_web_options(doc: JsonDocument, options: Int, is_tool: Bool) raises:
    for key in ["allowed_domains", "blocked_domains"]:
        var node = doc.get(options, key)
        if node < 0: continue
        if doc.nodes[node].kind != JSON_ARRAY: raise Error("DeepSeek web_search " + key + " must be an array of strings")
        for item in doc.nodes[node].children:
            if doc.nodes[item].kind != JSON_STRING or not trim_text(doc.nodes[item].text): raise Error("DeepSeek web_search " + key + " entries must be non-empty strings")
    var max_uses = doc.get(options, "max_uses")
    if max_uses >= 0:
        var valid = doc.nodes[max_uses].kind == 2
        var nonzero = False
        for byte in serialize_json(doc, max_uses).as_bytes():
            valid = valid and byte >= 48 and byte <= 57
            nonzero = nonzero or byte != 48
        if not valid or not nonzero:
            raise Error("DeepSeek web_search max_uses must be a positive integer")
    var location = doc.get(options, "user_location")
    if location < 0 and is_tool: location = doc.get(options, "location")
    if location >= 0 and doc.nodes[location].kind != JSON_OBJECT: raise Error("DeepSeek web_search user_location must be an object")


def _mcp_tools(doc: JsonDocument, node: Int, mut output: List[String], mut names: List[String], strict_tools: Bool) raises:
    var server = doc.string(_first_string_node(doc, node, ["mcp_server_name", "server_label", "server_name", "name"]))
    if not trim_text(server): return
    var selected = List[String]()
    var allowed = doc.get(node, "allowed_tools")
    if allowed >= 0 and doc.nodes[allowed].kind == JSON_ARRAY:
        for item in doc.nodes[allowed].children:
            if doc.nodes[item].kind == JSON_STRING and trim_text(doc.nodes[item].text): selected.append(trim_text(doc.nodes[item].text))
    var configs = doc.get(node, "configs")
    var default_config = doc.get(node, "default_config")
    var default_enabled = True
    var default_flag = doc.get(default_config, "enabled")
    if default_flag >= 0 and doc.nodes[default_flag].kind == JSON_BOOL and doc.nodes[default_flag].text == "false": default_enabled = False
    if configs >= 0 and doc.nodes[configs].kind == JSON_OBJECT:
        for index in range(len(doc.nodes[configs].children)):
            var item = doc.nodes[configs].children[index]
            var enabled = doc.get(item, "enabled")
            var include = default_enabled
            if enabled >= 0 and doc.nodes[enabled].kind == JSON_BOOL:
                include = doc.nodes[enabled].text == "true"
            if include: selected.append(doc.nodes[configs].names[index])
    sort(selected)
    for item in selected:
        var server_part = _segment(server)
        var tool_part = _segment(item)
        if not server_part or not tool_part: continue
        var name = tool_part if trim_text(item).startswith("mcp__") else "mcp__" + server_part + "__" + tool_part
        var description = _str(doc, node, "description")
        if not trim_text(description): description = "MCP tool " + item + " from " + server + "."
        _add_tool('{"type":"function","function":{"name":' + quote_json(name) + ',"description":' + quote_json(description) + ',"parameters":{"type":"object","additionalProperties":true}}}', output, names, strict_tools)


def _validate_name(name: String) raises:
    var valid = name.byte_length() > 0 and name.byte_length() <= 64
    for character in name.codepoints():
        var c = Int(character)
        if not ((65 <= c <= 90) or (97 <= c <= 122) or (48 <= c <= 57) or c == 95 or c == 45):
            valid = False
    if not valid:
        raise Error("DeepSeek function tool names must use only letters, numbers, underscores, or dashes and be at most 64 bytes")


def _function_tool(doc: JsonDocument, node: Int, kind: String, name: String) raises -> String:
    var description = doc.get(node, "description")
    var params = doc.get(node, "parameters")
    if kind != "tool_search":
        if params < 0: params = doc.get(node, "parametersJsonSchema")
        if params < 0: params = doc.get(node, "input_schema")
        if params < 0: params = doc.get(node, "schema")
    var result = "{\"type\":\"function\",\"function\":{\"name\":" + quote_json(name)
    if description >= 0 and doc.nodes[description].kind == JSON_STRING and trim_text(doc.nodes[description].text):
        result += ",\"description\":" + serialize_json(doc, description)
    if kind == "custom":
        var custom_desc = doc.string(description) if description >= 0 else "Freeform custom tool input."
        if not trim_text(custom_desc): custom_desc = "Freeform custom tool input."
        var patch = name == "apply_patch"
        var custom_help = "the exact raw tool input in the `input` string field."
        if patch:
            custom_help = "the exact Codex apply_patch grammar in the `input` string field. The first line must be `*** Begin Patch`, the last line must be `*** End Patch`, and hunks must use `*** Add File:`, `*** Delete File:`, or `*** Update File:`. For `*** Add File: path`, every new file content line must start with `+`; for example `+hello`, and a blank content line is `+`. Do not pass unified diff headers such as `--- a/...` or `+++ b/...` as the top-level input."
        custom_desc += "\n\nCall this custom/freeform tool with " + custom_help
        var format = doc.get(node, "format")
        if format >= 0: custom_desc += "\n\nOriginal custom tool format JSON: " + serialize_json(doc, format)
        result = "{\"type\":\"function\",\"function\":{\"name\":" + quote_json(name) + ",\"description\":" + quote_json(custom_desc) + ",\"parameters\":{\"type\":\"object\",\"properties\":{\"input\":{\"type\":\"string\",\"description\":" + quote_json("Exact raw apply_patch input. For Add File, prefix every new file content line with '+'." if patch else "Exact raw input for the custom/freeform tool.") + "}},\"required\":[\"input\"],\"additionalProperties\":false}}}"
        return result
    if params >= 0:
        result += ",\"parameters\":" + serialize_json(doc, params)
    var strict = doc.get(node, "strict")
    if kind != "tool_search" and strict >= 0 and doc.nodes[strict].kind == JSON_BOOL:
        result += ",\"strict\":" + serialize_json(doc, strict)
    return result + "}}"


def _add_tool(tool: String, mut output: List[String], mut names: List[String], strict_tools: Bool) raises:
    var doc = JsonDocument(tool)
    var function = doc.get(doc.root, "function")
    var name = doc.string(doc.get(function, "name"))
    _validate_name(name)
    var params = doc.get(function, "parameters")
    if params >= 0 and doc.nodes[params].kind != JSON_OBJECT:
        raise Error("DeepSeek function tool `" + name + "` parameters must be an object")
    var strict = doc.get(function, "strict")
    if strict >= 0 and doc.nodes[strict].text == "true" and not strict_tools:
        raise Error("DeepSeek strict function tool `" + name + "` requires deepseek.strict_tools=true")
    var next_tool = tool
    if strict_tools:
        var normalized = String('{"type":"object","properties":{},"required":[],"additionalProperties":false}')
        if params >= 0: normalized = _normalize_schema(doc, params, 0, name)
        next_tool = '{"type":"function","function":{'
        for index in range(len(doc.nodes[function].children)):
            var key = doc.nodes[function].names[index]
            if key != "parameters" and key != "strict":
                next_tool += quote_json(key) + ":" + serialize_json(doc, doc.nodes[function].children[index]) + ","
        next_tool += '"parameters":' + normalized + ',"strict":true}}'
    var prior = -1
    for index in range(len(names)):
        if names[index] == name: prior = index
    if prior >= 0:
        if _canonical_tool_equal(output[prior], next_tool) or _generic_schema(next_tool): return
        if not _generic_schema(output[prior]):
            raise Error("DeepSeek function tool name `" + name + "` is duplicated after translation")
        output[prior] = ""
        names[prior] = ""
    names.append(name)
    output.append(next_tool)


def _namespace(doc: JsonDocument, node: Int, mut output: List[String], mut names: List[String], strict_tools: Bool) raises:
    var namespace = _str(doc, node, "name")
    var inner = doc.get(node, "tools")
    if inner < 0 or doc.nodes[inner].kind != JSON_ARRAY:
        raise Error("DeepSeek namespace tools must be an array")
    for child in doc.nodes[inner].children:
        var name = _str(doc, child, "name")
        var flat = _flatten_name(namespace, name)
        _add_tool(_function_tool(doc, child, "function", flat), output, names, strict_tools)


def _generic_schema(tool: String) raises -> Bool:
    var value = JsonDocument(tool)
    var function_node = value.get(value.root, "function")
    var params = value.get(function_node, "parameters")
    if params < 0: return False
    var additional = value.get(params, "additionalProperties")
    return additional >= 0 and value.nodes[additional].kind == JSON_BOOL and value.nodes[additional].text == "true" and value.get(params, "properties") < 0 and value.get(params, "required") < 0


def _canonical_tool_equal(left: String, right: String) raises -> Bool:
    var left_doc = JsonDocument(left)
    var right_doc = JsonDocument(right)
    return _canonical_json_equal(left_doc, left_doc.root, right_doc, right_doc.root)


def _canonical_json_equal(left: JsonDocument, a: Int, right: JsonDocument, b: Int) raises -> Bool:
    if left.nodes[a].kind != right.nodes[b].kind: return False
    var kind = left.nodes[a].kind
    if kind == JSON_OBJECT:
        var keys_a = _sorted_keys(left, a)
        var keys_b = _sorted_keys(right, b)
        if len(keys_a) != len(keys_b): return False
        for key in keys_a:
            var key_found = False
            for other in keys_b:
                if key == other: key_found = True
            if not key_found or not _canonical_json_equal(left, left.get(a, key), right, right.get(b, key)): return False
        return True
    if kind == JSON_ARRAY:
        if len(left.nodes[a].children) != len(right.nodes[b].children): return False
        for i in range(len(left.nodes[a].children)):
            if not _canonical_json_equal(left, left.nodes[a].children[i], right, right.nodes[b].children[i]): return False
        return True
    if kind == 2:
        var x = left.nodes[a].text
        var y = right.nodes[b].text
        var x_float = x.find(".") >= 0 or x.find("e") >= 0 or x.find("E") >= 0
        var y_float = y.find(".") >= 0 or y.find("e") >= 0 or y.find("E") >= 0
        if x_float != y_float: return False
        if x_float: return json_float(x) == json_float(y)
    return left.nodes[a].text == right.nodes[b].text


def _sorted_keys(doc: JsonDocument, node: Int) -> List[String]:
    var keys = List[String]()
    for key in doc.nodes[node].names: keys.append(key)
    sort(keys)
    var unique = List[String]()
    for key in keys:
        if not unique or unique[len(unique) - 1] != key: unique.append(key)
    return unique^


def _normalize_schema(doc: JsonDocument, node: Int, depth: Int, name: String) raises -> String:
    if depth > 127 or doc.nodes[node].kind != JSON_OBJECT:
        raise Error("DeepSeek strict tool schema `" + name + "` could not be normalized")
    if serialize_json(doc, node).byte_length() > 4194304: raise Error("DeepSeek strict tool schema `" + name + "` could not be normalized")
    var allowed = ["type", "description", "properties", "required", "additionalProperties", "items", "enum", "anyOf"]
    for key in doc.nodes[node].names:
        var known = False
        for allowed_key in allowed:
            if key == allowed_key: known = True
        if not known: raise Error("DeepSeek strict tool schema `" + name + "` could not be normalized")
    var any_of = doc.get(node, "anyOf")
    if any_of >= 0:
        if doc.nodes[any_of].kind != JSON_ARRAY: raise Error("DeepSeek strict tool schema `" + name + "` could not be normalized")
        var result = "{"
        var keys = _sorted_keys(doc, node)
        for i in range(len(keys)):
            if i: result += ","
            var key = keys[i]
            result += quote_json(key) + ":"
            var member = doc.get(node, key)
            if key == "anyOf":
                result += "["
                for j in range(len(doc.nodes[member].children)):
                    if j: result += ","
                    result += _normalize_schema(doc, doc.nodes[member].children[j], depth + 1, name)
                result += "]"
            else: result += serialize_json(doc, member)
        return result + "}"
    var enum_values = doc.get(node, "enum")
    if enum_values >= 0 and doc.nodes[enum_values].kind != JSON_ARRAY: raise Error("DeepSeek strict tool schema `" + name + "` could not be normalized")
    var type_node = doc.get(node, "type")
    var schema_type = "object" if type_node < 0 else doc.string(type_node)
    if type_node >= 0 and doc.nodes[type_node].kind != JSON_STRING: raise Error("DeepSeek strict tool schema `" + name + "` could not be normalized")
    if schema_type != "object" and schema_type != "array" and schema_type != "string" and schema_type != "number" and schema_type != "integer" and schema_type != "boolean": raise Error("DeepSeek strict tool schema `" + name + "` could not be normalized")
    if schema_type == "object":
        var props = doc.get(node, "properties")
        if props >= 0 and doc.nodes[props].kind != JSON_OBJECT: raise Error("DeepSeek strict tool schema `" + name + "` could not be normalized")
        var result = "{\"type\":\"object\""
        var keys = _sorted_keys(doc, node)
        for key in keys:
            var member = doc.get(node, key)
            if key == "type" or key == "properties" or key == "required" or key == "additionalProperties": continue
            result += "," + quote_json(key) + ":" + serialize_json(doc, member)
        result += ",\"properties\":{"
        var required = ""
        if props >= 0:
            var property_names = _sorted_keys(doc, props)
            for i in range(len(property_names)):
                if i: result += ","
                var prop_name = property_names[i]
                var prop = doc.get(props, prop_name)
                result += quote_json(prop_name) + ":" + _normalize_schema(doc, prop, depth + 1, name)
                if i: required += ","
                required += quote_json(prop_name)
        return result + "},\"required\":[" + required + "],\"additionalProperties\":false}"
    if schema_type == "array":
        var items = doc.get(node, "items")
        if items < 0: raise Error("DeepSeek strict tool schema `" + name + "` could not be normalized")
        var result = "{"
        var first = True
        var keys = _sorted_keys(doc, node)
        for key in keys:
            var member = doc.get(node, key)
            if key == "items":
                if not first: result += ","
                result += "\"items\":" + _normalize_schema(doc, member, depth + 1, name)
                first = False
            else:
                if not first: result += ","
                result += quote_json(key) + ":" + serialize_json(doc, member)
                first = False
        return result + "}"
    return serialize_json(doc, node)


def _choice(doc: JsonDocument, node: Int, names: List[String]) raises -> String:
    if doc.nodes[node].kind == JSON_STRING:
        var mode = doc.nodes[node].text
        if mode == "auto" or mode == "none" or mode == "required":
            return serialize_json(doc, node)
        raise Error("DeepSeek tool_choice string `" + mode + "` is not supported")
    if doc.nodes[node].kind != JSON_OBJECT:
        raise Error("DeepSeek tool_choice must be a string or object")
    var kind = _str(doc, node, "type")
    if kind == "function" or kind.startswith("mcp"):
        var name_node = _first_string_node(doc, node, ["name"])
        if name_node < 0:
            name_node = _first_string_node(doc, doc.get(node, "function"), ["name"])
        var name = doc.string(name_node)
        if not trim_text(name):
            raise Error("DeepSeek named tool_choice requires a function name")
        var namespace_node = _first_string_node(doc, node, ["namespace", "server_label", "mcp_server_name", "server_name"])
        if namespace_node < 0:
            namespace_node = _first_string_node(doc, doc.get(node, "function"), ["namespace"])
        var namespace = doc.string(namespace_node)
        if trim_text(namespace):
            name = _flatten_name(namespace, name, kind.startswith("mcp") and not namespace.startswith("mcp__"))
        _validate_name(name)
        var found = False
        for candidate in names:
            if candidate == name: found = True
        if not found:
            raise Error("DeepSeek named tool_choice `" + name + "` does not match any translated function tool")
        return "{\"type\":\"function\",\"function\":{\"name\":" + quote_json(name) + "}}"
    raise Error("DeepSeek tool_choice type `" + kind + "` is not supported")


def _flatten_name(namespace: String, name: String, add_mcp_prefix: Bool = False) -> String:
    var ns = trim_text(namespace)
    if add_mcp_prefix and ns:
        var start = namespace.find(ns)
        ns = String(namespace[byte=:start + ns.byte_length()])
    var tool = trim_text(name)
    var pair = (add_mcp_prefix or ns.startswith("mcp__")) and not ns.endswith("_") and not tool.startswith("_") and tool.find("__") < 0
    return ("mcp__" if add_mcp_prefix else "") + ns + ("__" if pair else "--") + tool


def _segment(value: String) -> String:
    var codes = List[Int]()
    var first_alnum = -1
    var last_alnum = -1
    for character in value.codepoints():
        var b = Int(character)
        codes.append(b)
        if (48 <= b <= 57) or (65 <= b <= 90) or (97 <= b <= 122):
            if first_alnum < 0: first_alnum = len(codes) - 1
            last_alnum = len(codes) - 1
    if last_alnum < 0: return ""
    var out = String()
    for i in range(first_alnum, last_alnum + 1):
        var b = codes[i]
        if (48 <= b <= 57) or (65 <= b <= 90) or (97 <= b <= 122) or b == 95: out += chr(b)
        else: out += "_"
    return out
