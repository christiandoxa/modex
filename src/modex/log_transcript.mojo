"""Projection of visible transcript records from session JSONL."""

from .json import JSON_ARRAY, JSON_BOOL, JSON_NULL, JSON_NUMBER, JSON_OBJECT, JSON_STRING, JsonDocument, serialize_json
from .log_text import operation_value, safe_text, tool_name, trim_unicode, visible_message, visible_tool_output


def transcript_event(line: String) raises -> Optional[Tuple[String, String, String]]:
    var doc: JsonDocument
    try:
        doc = JsonDocument(line)
    except:
        return None
    var timestamp_node = doc.get(doc.root, "timestamp")
    var timestamp = doc.string(timestamp_node) if timestamp_node >= 0 and doc.nodes[timestamp_node].kind == JSON_STRING else String("-")
    var kind = doc.string(doc.get(doc.root, "type"))
    var payload = doc.get(doc.root, "payload")
    if payload < 0 or doc.nodes[payload].kind != JSON_OBJECT:
        return None
    var event_type = doc.string(doc.get(payload, "type"))
    var source = String()
    var text = String()

    if kind == "session_meta":
        var base = doc.get(payload, "base_instructions")
        var base_text = doc.string(doc.get(base, "text"))
        if base_text.strip():
            source = "prompt-engineering"
            text = base_text
        var provider = doc.get(payload, "model_provider")
        if provider < 0:
            provider = doc.get(payload, "provider")
        var fields = String()
        fields = context_field(doc, fields, "provider", provider)
        for key in ["source", "originator", "cwd"]:
            fields = context_field(doc, fields, key, doc.get(payload, key))
        if fields:
            source = "session-context"
            text = fields
    elif kind == "turn_context":
        for key, label in [("model", "model"), ("effort", "effort"), ("summary", "summary"), ("approval_policy", "approval"), ("cwd", "cwd")]:
            text = context_field(doc, text, label, doc.get(payload, key))
        if text:
            source = "turn-context"
    elif kind == "event_msg":
        if event_type == "user_message":
            source = "user"
            text = visible_message(doc.string(doc.get(payload, "message")))
        elif event_type == "agent_message":
            source = "assistant"
            text = visible_message(doc.string(doc.get(payload, "message")))
        elif event_type == "agent_reasoning":
            source = "reasoning"
            text = visible_message(doc.string(doc.get(payload, "text")))
        elif is_protocol_event(event_type):
            source = protocol_source(event_type)
            text = protocol_fields(doc, payload, event_type)
        elif is_status_event(event_type):
            var status = doc.string(doc.get(payload, "status"))
            source = "error" if status.find("fail") >= 0 or status.find("error") >= 0 or event_type.find("fail") >= 0 or event_type.find("abort") >= 0 or event_type == "error" else "terminal"
            text = status_fields(doc, payload)
            if not text: text = event_type.replace("_", " ")
    elif kind == "response_item":
        if event_type == "message":
            var role_node = doc.get(payload, "role")
            if role_node >= 0 and doc.nodes[role_node].kind == JSON_STRING:
                source = doc.string(role_node)
            else:
                source = "message"
            var metadata = doc.get(payload, "internal_chat_message_metadata_passthrough")
            var kinds = doc.get(metadata, "content_item_kinds")
            var user_hidden = source == "user" and kinds >= 0 and doc.nodes[kinds].kind == JSON_ARRAY and not visible_user_kinds(doc, kinds)
            if not user_hidden:
                var content = doc.get(payload, "content")
                if content >= 0 and doc.nodes[content].kind == JSON_ARRAY:
                    for child in doc.nodes[content].children:
                        var part_node = doc.get(child, "text")
                        if part_node < 0: part_node = doc.get(child, "content")
                        var part = visible_message(doc.string(part_node))
                        if part:
                            if text: text += "\n"
                            text += part
        elif event_type == "function_call" or event_type == "custom_tool_call" or event_type == "shell_call" or event_type == "local_shell_call":
            var shell = event_type == "shell_call" or event_type == "local_shell_call"
            var name_node = doc.get(payload, "name")
            var name = doc.string(name_node)
            if name_node < 0 or doc.nodes[name_node].kind != JSON_STRING:
                name = "shell" if shell else "custom-tool" if event_type == "custom_tool_call" else "tool"
            source = "tool-call:" + tool_name(name)
            var arg = -1
            if shell:
                for key in ["command", "arguments", "action"]:
                    if arg < 0: arg = doc.get(payload, key)
            else:
                arg = doc.get(payload, "arguments") if event_type == "function_call" else doc.get(payload, "input")
            if shell and arg >= 0 and doc.nodes[arg].kind != JSON_NULL:
                text = operation_value(doc.string(arg)) if doc.nodes[arg].kind == JSON_STRING else json_value(doc, arg)
            elif arg >= 0 and doc.nodes[arg].kind == JSON_STRING:
                text = doc.string(arg)
        elif event_type == "function_call_output" or event_type == "custom_tool_call_output" or event_type == "shell_call_output" or event_type == "local_shell_call_output":
            source = "tool-output"
            var shell = event_type == "shell_call_output" or event_type == "local_shell_call_output"
            var output = doc.get(payload, "output")
            if shell and output < 0: output = doc.get(payload, "aggregated_output")
            if shell and output < 0: output = doc.get(payload, "stdout")
            if shell and output >= 0 and doc.nodes[output].kind != JSON_NULL:
                var value = operation_value(doc.string(output)) if doc.nodes[output].kind == JSON_STRING else json_value(doc, output)
                text = visible_tool_output(value)
            elif output >= 0 and doc.nodes[output].kind == JSON_STRING:
                text = visible_tool_output(doc.string(output))
        elif event_type == "reasoning":
            source = "reasoning"
            var summary = doc.get(payload, "summary")
            if summary >= 0 and doc.nodes[summary].kind == JSON_ARRAY:
                for child in doc.nodes[summary].children:
                    var part = reasoning_part(doc, child)
                    if part:
                        if text: text += "\n"
                        text += part
            elif summary >= 0:
                text = reasoning_part(doc, summary)
        elif protocol_source(event_type) != "tool" or event_type == "computer_call" or event_type == "computer_call_output" or event_type == "web_search_call" or event_type == "file_search_call" or event_type == "code_interpreter_call":
            source = protocol_source(event_type)
            text = protocol_fields(doc, payload, event_type)

    text = safe_text(text)
    if not trim_unicode(text):
        return None
    return (timestamp^, source^, text^)


def context_field(doc: JsonDocument, mut current: String, label: String, node: Int) -> String:
    if node < 0 or doc.nodes[node].kind != JSON_STRING:
        return current
    var value = doc.string(node)
    if current: current += " "
    return current + label + "=" + value


def protocol_fields(doc: JsonDocument, payload: Int, event_type: String) -> String:
    var text = String()
    var has_status = False
    for label in ["server", "tool", "name", "status", "phase"]:
        var node = doc.get(payload, label)
        var value = operation_value(doc.string(node))
        if label == "server" and not value:
            for alias in ["server_label", "server_name"]:
                value = operation_value(doc.string(doc.get(payload, alias)))
                if value: break
        if label == "tool" and not value:
            value = operation_value(doc.string(doc.get(payload, "tool_name")))
        if value:
            if text: text += " "
            text += label + "=" + value
            if label == "status": has_status = True
    if not has_status and (event_type.startswith("subagent_") or event_type.startswith("sub_agent_")):
        var prefix = "subagent_" if event_type.startswith("subagent_") else "sub_agent_"
        var implicit = operation_value(String(event_type[byte=prefix.byte_length():]))
        if implicit:
            if text: text += " "
            text += "status=" + implicit
    if not text:
        text = event_type.replace("_", " ")
    return text^


def status_fields(doc: JsonDocument, payload: Int) -> String:
    var text = String()
    for key in ["status", "exit_code", "exit_status", "reason", "duration_ms", "message"]:
        var node = doc.get(payload, key)
        if node >= 0 and (doc.nodes[node].kind == JSON_STRING or doc.nodes[node].kind == JSON_NUMBER or doc.nodes[node].kind == JSON_BOOL):
            var value = operation_value(json_value(doc, node))
            if value:
                if text: text += " "
                text += key + "=" + value
    for key in ["stdout", "stderr", "output"]:
        var node = doc.get(payload, key)
        if node >= 0 and doc.nodes[node].kind != JSON_NULL:
            var value = safe_text(operation_value(doc.string(node))) if doc.nodes[node].kind == JSON_STRING else safe_text(json_value(doc, node))
            if value:
                if text: text += " "
                text += key + ":\n" + value
    return text^


def is_status_event(event_type: String) -> Bool:
    return event_type == "task_started" or event_type == "task_complete" or event_type == "task_completed" or event_type == "turn_started" or event_type == "turn_complete" or event_type == "turn_completed" or event_type == "turn_aborted" or event_type == "turn_cancelled" or event_type == "turn_interrupted" or event_type == "turn_failed" or event_type == "command_execution_started" or event_type == "command_execution_completed" or event_type == "command_execution_finished" or event_type == "command_execution_output" or event_type == "exec_command_begin" or event_type == "exec_command_end" or event_type == "error" or (event_type.find("command") >= 0 and event_type.find("status") >= 0)


def is_protocol_event(event_type: String) -> Bool:
    return event_type.find("tool_call") >= 0 or event_type.find("mcp") >= 0 or event_type.find("subagent") >= 0 or event_type.find("sub_agent") >= 0


def protocol_source(event_type: String) -> String:
    if event_type.find("mcp") >= 0: return "mcp"
    if event_type.find("subagent") >= 0 or event_type.find("sub_agent") >= 0: return "agent"
    return "tool"


def reasoning_part(doc: JsonDocument, node: Int) -> String:
    var selected = node
    if doc.nodes[node].kind == JSON_OBJECT:
        selected = doc.get(node, "text")
        if selected < 0: selected = doc.get(node, "summary_text")
    var value = doc.string(selected)
    return value if trim_unicode(value) else ""


def visible_user_kinds(doc: JsonDocument, kinds: Int) -> Bool:
    if len(doc.nodes[kinds].children) == 0: return False
    for child in doc.nodes[kinds].children:
        if doc.string(child) != "user.text": return False
    return True


def json_value(doc: JsonDocument, node: Int, nested: Bool = False) -> String:
    if node < 0: return ""
    if doc.nodes[node].kind == JSON_STRING and not nested:
        return doc.nodes[node].text
    return serialize_json(doc, node)
