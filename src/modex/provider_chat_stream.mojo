"""Stateful DeepSeek-compatible chat chunks translated into Responses SSE."""

from std.collections import Dict, List

from .json import JSON_ARRAY, JSON_NULL, JSON_OBJECT, JSON_STRING, JsonDocument, quote_json, serialize_json
from .provider_chat_chunk import chat_choice_delta, chat_choice_metadata, chat_first_choice, chat_stream_error
from .provider_chat_items import tool_added_item, tool_output_item, wrap_tool_arguments
from .provider_chat_metadata import merge_chat_metadata
from .provider_chat_tools import chat_tool_delta, incremental_arguments
from .provider_chat_usage import chat_usage, json_unsigned
from .provider_anthropic_messages import AnthropicWebSearch, _only_fields, _search_queries, _search_sources
from .provider_sse_events import sse_event, sse_failed_event, sse_text_item_added, sse_text_item_done
from .text import trim_text
from .uuid7 import new_uuid7


@fieldwise_init
struct ChatStreamTool(Copyable):
    var index: UInt64
    var call_id: String
    var name: Optional[String]
    var arguments: String
    var signature: Optional[String]
    var added: Bool
    var done: Bool


struct DeepSeekChatState:
    var request_id: UInt64
    var response_id: String
    var created_at: UInt64
    var sequence: UInt64
    var created: Bool
    var completed: Bool
    var text_added: Bool
    var text_done: Bool
    var reasoning_added: Bool
    var reasoning_done: Bool
    var model: Optional[String]
    var usage: Optional[String]
    var logprobs: Optional[String]
    var finish_reason: Optional[String]
    var fingerprint: Optional[String]
    var output_text: String
    var reasoning: String
    var refusal: String
    var annotations: List[String]
    var tools: List[ChatStreamTool]
    var external_output_items: List[String]
    var anthropic_searches: List[AnthropicWebSearch]
    var anthropic_search_position_by_index: Dict[UInt64, Int]
    var anthropic_stream_terminal: Bool
    var anthropic_open_result_indices: Dict[UInt64, Bool]
    var anthropic_input_tokens: UInt64
    var anthropic_output_tokens: UInt64
    var anthropic_message_delta_seen: Bool
    var request_metadata: String
    var conversation_snapshot: Optional[String]

    def __init__(out self, request_id: UInt64, response_id: String, created_at: UInt64, request_metadata: String = "null"):
        self.request_id = request_id
        self.response_id = response_id
        self.created_at = created_at
        self.sequence = 0
        self.created = False
        self.completed = False
        self.text_added = False
        self.text_done = False
        self.reasoning_added = False
        self.reasoning_done = False
        self.model = Optional[String]()
        self.usage = Optional[String]()
        self.logprobs = Optional[String]()
        self.finish_reason = Optional[String]()
        self.fingerprint = Optional[String]()
        self.output_text = ""
        self.reasoning = ""
        self.refusal = ""
        self.annotations = List[String]()
        self.tools = List[ChatStreamTool]()
        self.external_output_items = List[String]()
        self.anthropic_searches = List[AnthropicWebSearch]()
        self.anthropic_search_position_by_index = Dict[UInt64, Int]()
        self.anthropic_stream_terminal = False
        self.anthropic_open_result_indices = Dict[UInt64, Bool]()
        self.anthropic_input_tokens = 0
        self.anthropic_output_tokens = 0
        self.anthropic_message_delta_seen = False
        self.request_metadata = request_metadata
        self.conversation_snapshot = Optional[String]()

    def next_sequence(mut self) -> UInt64:
        var sequence = self.sequence
        if self.sequence < UInt64.MAX:
            self.sequence += 1
        return sequence

    def event(mut self, name: String, fields: String, include_created: Bool = False) raises -> String:
        var body = '{"type":' + quote_json(name) + ',"sequence_number":' + String(self.next_sequence())
        if include_created:
            body += ',"created_at":' + String(self.created_at)
        if fields:
            body += "," + fields
        return sse_event(name, body + "}")

    def fail(mut self, code: String, message: String) raises -> List[String]:
        var output = List[String]()
        if not self.completed:
            var sequence = self.next_sequence()
            self.completed = True
            output.append(sse_failed_event(sequence, self.created_at, self.response_id, code, message))
        return output^

    def observe(mut self, source: String) raises -> List[String]:
        var doc = JsonDocument(source)
        if doc.nodes[doc.root].kind != JSON_OBJECT:
            raise Error("chat stream chunk is not an object")
        var embedded_error = chat_stream_error(doc)
        if embedded_error != "null":
            var error = JsonDocument(embedded_error)
            return self.fail(error.string(error.get(error.root, "code")), error.string(error.get(error.root, "message")))
        self.apply_metadata(doc)
        var output = List[String]()
        if not self.created:
            self.created = True
            output.append(self.event("response.created", '"response":{"id":' + quote_json(self.response_id) + "}", True))
        var choice = chat_first_choice(doc)
        if choice < 0:
            return output^
        var metadata = JsonDocument(chat_choice_metadata(doc, choice))
        var logprobs = metadata.get(metadata.root, "logprobs")
        if metadata.nodes[logprobs].kind != JSON_NULL:
            self.logprobs = serialize_json(metadata, logprobs)
        var delta = JsonDocument(chat_choice_delta(doc, choice))
        var reasoning = optional_string(delta, delta.root, "reasoning_content")
        if reasoning:
            output.extend(self.reasoning_delta(reasoning.value()))
        var refusal = optional_string(delta, delta.root, "refusal")
        if refusal:
            self.refusal += refusal.value()
        var annotations = delta.get(delta.root, "annotations")
        for item in delta.nodes[annotations].children:
            self.annotations.append(serialize_json(delta, item))
        var content = optional_string(delta, delta.root, "content")
        if content:
            output.extend(self.content_delta(content.value()))
        var tools = delta.get(delta.root, "tool_calls")
        for tool in delta.nodes[tools].children:
            output.extend(self.tool_delta(delta, tool))
        var finish = optional_string(metadata, metadata.root, "finish_reason")
        if finish:
            self.finish_reason = finish.value()
            var failure = self.validate_tools()
            if failure:
                output.extend(self.fail("invalid_tool_call_arguments", failure.value()))
            else:
                output.extend(self.complete_tools())
                if self.tools:
                    self.conversation_snapshot = self.assistant_message()
        return output^

    def observe_anthropic(mut self, source: String) raises -> List[String]:
        var doc = JsonDocument(source)
        if self.completed and not self.anthropic_stream_terminal:
            try:
                return self.observe_anthropic_document(doc)
            except:
                return List[String]()
        return self.observe_anthropic_document(doc)

    def observe_anthropic_document(mut self, doc: JsonDocument) raises -> List[String]:
        if doc.nodes[doc.root].kind != JSON_OBJECT:
            raise Error("Anthropic stream event must be an object")
        var kind = doc.string(doc.get(doc.root, "type"))
        if kind == "ping":
            return List[String]()
        if kind == "error":
            self.anthropic_stream_terminal = True
            var error = doc.get(doc.root, "error")
            var code_node = doc.get(error, "type")
            var message_node = doc.get(error, "message")
            var code = "anthropic_stream_error"
            if code_node >= 0 and doc.nodes[code_node].kind == JSON_STRING:
                code = doc.string(code_node)
            var message = "Anthropic stream failed"
            if message_node >= 0 and doc.nodes[message_node].kind == JSON_STRING:
                message = doc.string(message_node)
            return self.fail(code, message)
        if kind == "message_start":
            var output = List[String]()
            var message = doc.get(doc.root, "message")
            var id = optional_string(doc, message, "id")
            if id and self.response_id.startswith("resp_deepseek_"):
                self.response_id = id.value()
            var model = optional_string(doc, message, "model")
            if model:
                self.model = model.value()
            var usage = doc.get(message, "usage")
            var input = json_unsigned(doc, doc.get(usage, "input_tokens"))
            if input:
                self.anthropic_input_tokens = input.value()
            var output_tokens = json_unsigned(doc, doc.get(usage, "output_tokens"))
            if output_tokens:
                self.anthropic_output_tokens = output_tokens.value()
            var total = UInt64.MAX if self.anthropic_output_tokens > UInt64.MAX - self.anthropic_input_tokens else self.anthropic_input_tokens + self.anthropic_output_tokens
            self.usage = Optional[String]('{"input_tokens":' + String(self.anthropic_input_tokens) + ',"output_tokens":' + String(self.anthropic_output_tokens) + ',"total_tokens":' + String(total) + '}')
            if not self.created:
                self.created = True
                output.append(self.event("response.created", '"response":{"id":' + quote_json(self.response_id) + "}", True))
            return output^
        if kind == "content_block_start":
            var block = doc.get(doc.root, "content_block")
            if block < 0:
                return self.fail("invalid_anthropic_stream", "content block is missing")
            var block_type_node = doc.get(block, "type")
            if block_type_node < 0 or doc.nodes[block_type_node].kind != JSON_STRING:
                return self.fail("invalid_anthropic_stream", "content block type is missing")
            var block_type = doc.nodes[block_type_node].text
            if block_type == "thinking":
                return List[String]()
            if block_type == "image":
                return List[String]()
            if block_type == "text":
                return List[String]()
            if block_type != "tool_use" and block_type != "web_search_tool_result" and (
                block_type != "server_tool_use"
                or doc.string(doc.get(block, "name")) != "web_search"
            ):
                return List[String]()
            var index = json_unsigned(doc, doc.get(doc.root, "index"))
            var block_index = UInt64(0)
            if index: block_index = index.value()
            if block_type == "server_tool_use" and doc.string(doc.get(block, "name")) == "web_search":
                return self.start_anthropic_search(doc, block, block_index)
            if block_type == "tool_use":
                var id = optional_string(doc, block, "id")
                var name = optional_string(doc, block, "name")
                var id_field = String()
                if id: id_field = ',"id":' + quote_json(id.value())
                # Preserve missing names so shared stream validation fails after argument deltas.
                var name_field = String()
                if name: name_field = '"name":' + quote_json(name.value()) + ","
                return self.observe(
                    '{"choices":[{"delta":{"tool_calls":[{"index":' + String(block_index)
                    + id_field
                    + ',"type":"function","function":{' + name_field
                    + '"arguments":""}}]},"finish_reason":null}]}'
                )
            if block_type == "web_search_tool_result":
                self.anthropic_open_result_indices[block_index] = True
                return self.finish_anthropic_search(doc, block)
            return List[String]()
        if kind == "content_block_delta":
            var event_index = json_unsigned(doc, doc.get(doc.root, "index"))
            var block_index = UInt64(0)
            if event_index: block_index = event_index.value()
            var delta = doc.get(doc.root, "delta")
            var delta_type_node = doc.get(delta, "type")
            var search = self.anthropic_search_index(block_index)
            if block_index in self.anthropic_open_result_indices:
                return List[String]()
            if search >= 0 and (
                delta_type_node < 0
                or doc.nodes[delta_type_node].kind != JSON_STRING
                or doc.nodes[delta_type_node].text != "input_json_delta"
            ):
                return List[String]()
            if delta < 0 or doc.nodes[delta].kind != JSON_OBJECT:
                return self.fail("invalid_anthropic_stream", "content delta type is missing")
            delta_type_node = doc.get(delta, "type")
            if delta_type_node < 0 or doc.nodes[delta_type_node].kind != JSON_STRING:
                return self.fail("invalid_anthropic_stream", "content delta type is missing")
            var delta_type = doc.nodes[delta_type_node].text
            if delta_type != "text_delta" and delta_type != "input_json_delta" and delta_type != "thinking_delta":
                return List[String]()
            if delta_type == "thinking_delta":
                var thinking = optional_string(doc, delta, "thinking")
                if thinking: return self.reasoning_delta(thinking.value())
                return List[String]()
            if delta_type == "text_delta":
                var text_value = doc.get(delta, "text")
                if text_value < 0 or doc.nodes[text_value].kind != JSON_STRING:
                    return List[String]()
                return self.observe('{"choices":[{"delta":{"content":' + quote_json(doc.nodes[text_value].text) + '},"finish_reason":null}]}')
            if delta_type == "input_json_delta":
                var fragment_value = doc.get(delta, "partial_json")
                if fragment_value < 0 or doc.nodes[fragment_value].kind != JSON_STRING:
                    return List[String]()
                var fragment = doc.nodes[fragment_value].text
                if search >= 0:
                    self.anthropic_searches[search].input_json += fragment
                    return List[String]()
                return self.observe(
                    '{"choices":[{"delta":{"tool_calls":[{"index":' + String(block_index)
                    + ',"function":{"arguments":' + quote_json(fragment)
                    + '}}]},"finish_reason":null}]}'
                )
            raise Error("Anthropic content delta type is not supported")
        if kind == "content_block_stop":
            var index = json_unsigned(doc, doc.get(doc.root, "index"))
            var block_index = UInt64(0)
            if index: block_index = index.value()
            # The baseline only uses stops to clear currently ignored result indexes.
            if block_index in self.anthropic_open_result_indices:
                _ = self.anthropic_open_result_indices.pop(block_index)
            return List[String]()
        if kind == "message_delta":
            var delta = doc.get(doc.root, "delta")
            var stop_reason = doc.get(delta, "stop_reason")
            # The release reads string stop_reason only and ignores stop_sequence.
            var usage = doc.get(doc.root, "usage")
            var output = json_unsigned(doc, doc.get(usage, "output_tokens"))
            if output: self.anthropic_output_tokens = output.value()
            self.anthropic_message_delta_seen = True
            if stop_reason >= 0 and doc.nodes[stop_reason].kind == JSON_STRING:
                var reason = doc.nodes[stop_reason].text
                if reason == "tool_use":
                    self.finish_reason = Optional[String]("tool_calls")
                elif reason == "max_tokens":
                    self.finish_reason = Optional[String]("length")
                else:
                    self.finish_reason = Optional[String]("stop")
            var total = UInt64.MAX if self.anthropic_output_tokens > UInt64.MAX - self.anthropic_input_tokens else self.anthropic_input_tokens + self.anthropic_output_tokens
            self.usage = Optional[String]('{"input_tokens":' + String(self.anthropic_input_tokens) + ',"output_tokens":' + String(self.anthropic_output_tokens) + ',"total_tokens":' + String(total) + '}')
            var events = List[String]()
            if not self.created and self.anthropic_searches:
                self.created = True
                events.append(self.event("response.created", '"response":{"id":' + quote_json(self.response_id) + "}", True))
            var failure = self.validate_tools()
            if failure:
                events.extend(self.fail("invalid_tool_call_arguments", failure.value()))
            else:
                events.extend(self.complete_tools())
            return events^
        if kind == "message_stop":
            self.anthropic_stream_terminal = True
            var emit_created = self.anthropic_message_delta_seen
            # The release completes searches still pending at message_stop.
            var events = self.complete_anthropic_searches()
            if not self.created and emit_created:
                self.created = True
                events.insert(0, self.event("response.created", '"response":{"id":' + quote_json(self.response_id) + "}", True))
            events.extend(self.complete())
            return events^
        # The release ignores event types it does not recognize.
        return List[String]()

    def start_anthropic_search(mut self, doc: JsonDocument, block: Int, index: UInt64) raises -> List[String]:
        var id_node = doc.get(block, "id")
        var id = "web_search_" + String(index)
        if id_node >= 0 and doc.nodes[id_node].kind == JSON_STRING:
            id = doc.nodes[id_node].text
        var input = doc.get(block, "input")
        var input_json = serialize_json(doc, input) if input >= 0 and len(doc.nodes[input].children) != 0 else String()
        var search = AnthropicWebSearch(index, id, input_json, "[]", False)
        var item = _stream_anthropic_search_item(search, True)
        var position = self.anthropic_search_index(index)
        if position >= 0:
            self.anthropic_searches[position] = search.copy()
        else:
            position = len(self.anthropic_searches)
            self.anthropic_searches.append(search^)
        self.anthropic_search_position_by_index[index] = position
        var output = List[String]()
        output.append(self.event("response.output_item.added", '"output_index":' + String(index) + ',"item":' + item))
        return output^

    def finish_anthropic_search(mut self, doc: JsonDocument, block: Int) raises -> List[String]:
        var id_node = doc.get(block, "tool_use_id")
        if id_node < 0 or doc.nodes[id_node].kind != JSON_STRING:
            return List[String]()
        var id = doc.nodes[id_node].text
        var position = self.anthropic_search_index_by_id(id)
        if position < 0:
            return List[String]()
        var sources = _search_sources(doc, block)
        var output = List[String]()
        self.anthropic_searches[position].sources = sources
        if not self.anthropic_searches[position].done:
            var item = _stream_anthropic_search_item(self.anthropic_searches[position], False)
            self.anthropic_searches[position].done = True
            self.external_output_items.append(item)
            output.append(self.event("response.output_item.done", '"output_index":' + String(self.anthropic_searches[position].output_index) + ',"item":' + item))
        return output^

    def complete_anthropic_searches(mut self) raises -> List[String]:
        var output = List[String]()
        var pending_indices = List[UInt64]()
        for position in range(len(self.anthropic_searches)):
            if not self.anthropic_searches[position].done:
                pending_indices.append(self.anthropic_searches[position].output_index)
        sort(pending_indices)
        for index in pending_indices:
            var position = self.anthropic_search_index(index)
            var item = _stream_anthropic_search_item(self.anthropic_searches[position], False)
            self.anthropic_searches[position].done = True
            self.external_output_items.append(item)
            output.append(self.event("response.output_item.done", '"output_index":' + String(self.anthropic_searches[position].output_index) + ',"item":' + item))
        return output^

    def anthropic_search_index(self, index: UInt64) -> Int:
        var position = self.anthropic_search_position_by_index.get(index)
        if position: return position.value()
        return -1

    def anthropic_search_index_by_id(self, id: String) -> Int:
        var found = -1
        for position in range(len(self.anthropic_searches)):
            if self.anthropic_searches[position].id == id and (
                found < 0
                or self.anthropic_searches[position].output_index
                < self.anthropic_searches[found].output_index
            ):
                found = position
        return found

    def apply_metadata(mut self, doc: JsonDocument) raises:
        var id = optional_string(doc, doc.root, "id")
        if id and self.response_id.startswith("resp_deepseek_"):
            self.response_id = id.value()
        var model = optional_string(doc, doc.root, "model")
        if model:
            self.model = model.value()
        var created = json_unsigned(doc, doc.get(doc.root, "created"))
        if created:
            self.created_at = created.value()
        var fingerprint = optional_string(doc, doc.root, "system_fingerprint")
        if fingerprint and fingerprint.value():
            self.fingerprint = fingerprint.value()
        var usage = doc.get(doc.root, "usage")
        if usage >= 0:
            self.usage = chat_usage(doc, usage, "deepseek")

    def text_item_id(self) -> String:
        return "msg_deepseek_" + String(self.request_id)

    def content_delta(mut self, text: String) raises -> List[String]:
        var output = List[String]()
        if not self.text_added:
            self.text_added = True
            output.append(sse_text_item_added(self.next_sequence(), self.response_id, self.text_item_id()))
        self.output_text += text
        output.append(self.event("response.output_text.delta", '"response_id":' + quote_json(self.response_id) + ',"delta":' + quote_json(text), True))
        return output^

    def reasoning_delta(mut self, text: String) raises -> List[String]:
        var output = List[String]()
        if not text:
            return output^
        self.reasoning += text
        var position = '"response_id":' + quote_json(self.response_id) + ',"output_index":0,"summary_index":0'
        if not self.reasoning_added:
            self.reasoning_added = True
            output.append(self.event("response.reasoning_summary_part.added", position + ',"part":{"type":"summary_text","text":""}'))
        output.append(self.event("response.reasoning_summary_text.delta", position + ',"delta":' + quote_json(text)))
        return output^

    def tool_delta(mut self, doc: JsonDocument, node: Int) raises -> List[String]:
        if doc.nodes[node].kind != JSON_OBJECT:
            return self.fail("invalid_tool_call_arguments", "DeepSeek streamed a tool call without a function object")
        var delta = JsonDocument(chat_tool_delta(doc, node))
        var index = json_unsigned(delta, delta.get(delta.root, "index")).value()
        var position = 0
        while position < len(self.tools) and self.tools[position].index < index:
            position += 1
        var existing = position < len(self.tools) and self.tools[position].index == index
        var function = doc.get(node, "function")
        if not existing and (function < 0 or doc.nodes[function].kind != JSON_OBJECT):
            return self.fail("invalid_tool_call_arguments", "DeepSeek streamed a tool call without a function object")
        if not existing:
            self.tools.insert(position, ChatStreamTool(index, "call_deepseek_" + new_uuid7(), Optional[String](), "", Optional[String](), False, False))
        var id = optional_string(delta, delta.root, "id")
        if id:
            self.tools[position].call_id = id.value()
        var name = optional_string(delta, delta.root, "name")
        if name:
            self.tools[position].name = name.value()
        var signature = optional_string(delta, delta.root, "thought_signature")
        if signature:
            self.tools[position].signature = signature.value()
        var arguments = optional_string(delta, delta.root, "arguments")
        var incoming = Optional[String]()
        if arguments:
            incoming = incremental_arguments(self.tools[position].arguments, arguments.value())
            if incoming:
                self.tools[position].arguments += incoming.value()
        var actual_name = self.tools[position].name.value() if self.tools[position].name else String("tool_call")
        var output = List[String]()
        if not self.tools[position].added:
            self.tools[position].added = True
            var item = tool_added_item(self.tools[position].call_id, actual_name)
            if item:
                output.append(self.event("response.output_item.added", '"output_index":' + String(index) + ',"item":' + item.value()))
        if incoming and actual_name != "apply_patch" and actual_name != "tool_search":
            output.append(self.event("response.function_call_arguments.delta", '"output_index":' + String(index) + ',"call_id":' + quote_json(self.tools[position].call_id) + ',"delta":' + quote_json(incoming.value())))
        return output^

    def validate_tools(self) -> Optional[String]:
        for tool in self.tools:
            if not tool.name or not trim_text(tool.name.value()):
                return Optional[String]("DeepSeek streamed a tool call without a function name at index " + String(tool.index))
            if not trim_text(tool.arguments):
                continue
            try:
                var arguments = JsonDocument(tool.arguments)
            except:
                return Optional[String]("DeepSeek streamed malformed JSON arguments for tool call `" + trim_text(tool.name.value()) + "` at index " + String(tool.index) + ": invalid JSON")
        return Optional[String]()

    def complete_tools(mut self) raises -> List[String]:
        var output = List[String]()
        for position in range(len(self.tools)):
            if self.tools[position].done:
                continue
            self.tools[position].done = True
            var name = self.tools[position].name.value() if self.tools[position].name else String("tool_call")
            self.tools[position].arguments = wrap_tool_arguments(name, self.tools[position].arguments)
            var item = tool_output_item(self.tools[position].call_id, name, self.tools[position].arguments, self.tools[position].signature)
            output.append(self.event("response.output_item.done", '"output_index":' + String(self.tools[position].index) + ',"item":' + item))
        return output^

    def complete(mut self) raises -> List[String]:
        if self.completed:
            return List[String]()
        var failure = self.validate_tools()
        if failure:
            return self.fail("invalid_tool_call_arguments", failure.value())
        var output = self.complete_tools()
        if self.reasoning and not self.reasoning_done:
            self.reasoning_done = True
            output.append(self.event("response.reasoning_summary_text.done", '"response_id":' + quote_json(self.response_id) + ',"output_index":0,"summary_index":0,"text":' + quote_json(self.reasoning)))
        if self.output_text and not self.text_done:
            if not self.text_added:
                self.text_added = True
                output.append(sse_text_item_added(self.next_sequence(), self.response_id, self.text_item_id()))
            self.text_done = True
            output.append(sse_text_item_done(self.next_sequence(), self.response_id, self.text_item_id(), self.output_text))
        var response = self.response_value()
        output.append(self.event("response.completed", '"response":' + response, True))
        self.conversation_snapshot = self.assistant_message()
        self.completed = True
        return output^

    def response_value(self) raises -> String:
        var items = List[String]()
        if self.anthropic_searches:
            for item in self.external_output_items:
                items.append(item)
        if self.output_text:
            items.append('{"type":"message","role":"assistant","content":[{"type":"output_text","text":' + quote_json(self.output_text) + "}]}")
        for tool in self.tools:
            var name = tool.name.value() if tool.name else String("tool_call")
            items.append(tool_output_item(tool.call_id, name, tool.arguments, tool.signature))
        if not self.anthropic_searches:
            for item in self.external_output_items:
                items.append(item)
        var response = '{"id":' + quote_json(self.response_id) + ',"output":' + json_array(items)
        if self.model:
            response += ',"model":' + quote_json(self.model.value())
        if self.usage:
            response += ',"usage":' + self.usage.value()
        var metadata = merge_chat_metadata(self.provider_metadata(), self.request_metadata)
        if metadata != "null":
            response += ',"metadata":' + metadata
        return response + "}"

    def provider_metadata(self) -> String:
        var fields = List[String]()
        if self.logprobs: fields.append('"logprobs":' + self.logprobs.value())
        if self.reasoning: fields.append('"reasoning_content":' + quote_json(self.reasoning))
        if self.refusal: fields.append('"refusal":' + quote_json(self.refusal))
        if self.annotations: fields.append('"annotations":' + json_array(self.annotations))
        if self.finish_reason: fields.append('"finish_reason":' + quote_json(self.finish_reason.value()))
        if self.fingerprint: fields.append('"system_fingerprint":' + quote_json(self.fingerprint.value()))
        if not fields:
            return "null"
        var body = String()
        for field in fields:
            if body: body += ","
            body += field
        return '{"deepseek":{' + body + "}}"

    def assistant_message(self) -> Optional[String]:
        if not self.output_text and not self.reasoning and not self.tools:
            return Optional[String]()
        var body = '{"role":"assistant","content":'
        body += quote_json(self.output_text) if self.output_text or self.tools else String("null")
        if self.reasoning:
            body += ',"reasoning_content":' + quote_json(self.reasoning)
        if self.tools:
            var calls = List[String]()
            for tool in self.tools:
                var name = tool.name.value() if tool.name else String("tool_call")
                var call = '{"id":' + quote_json(tool.call_id) + ',"type":"function","function":{"name":' + quote_json(name) + ',"arguments":' + quote_json(tool.arguments) + "}"
                if tool.signature:
                    call += ',"extra_content":{"google":{"thought_signature":' + quote_json(tool.signature.value()) + "}}"
                calls.append(call + "}")
            body += ',"tool_calls":' + json_array(calls)
        return Optional[String](body + "}")


def optional_string(doc: JsonDocument, parent: Int, key: StringSlice) -> Optional[String]:
    var node = doc.get(parent, key)
    if node >= 0 and doc.nodes[node].kind == JSON_STRING:
        return Optional[String](doc.nodes[node].text)
    return Optional[String]()


def json_array(values: List[String]) -> String:
    var body = String("[")
    for index in range(len(values)):
        if index:
            body += ","
        body += values[index]
    return body + "]"


def _stream_anthropic_search_item(search: AnthropicWebSearch, in_progress: Bool) -> String:
    var queries = String("[]")
    try:
        queries = _search_queries(search.input_json, True)
    except:
        pass
    return (
        '{"type":"web_search_call","id":' + quote_json(search.id)
        + ',"status":' + quote_json("in_progress" if in_progress else "completed")
        + ',"action":{"type":"search","queries":' + queries
        + ',"sources":' + search.sources + "}}"
    )
