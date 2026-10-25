from std.collections import List, Span
from std.testing import assert_equal, assert_true

from modex.json import JsonDocument
from modex.provider_chat_reader import DeepSeekChatReader
from modex.provider_chat_stream import DeepSeekChatState


def collect(mut reader: DeepSeekChatReader, source: String) raises -> List[String]:
    var output = List[String]()
    var bytes = source.as_bytes()
    var offset = 0
    while offset < len(bytes) and not reader.done:
        var next = reader.consume(Span(bytes)[offset:])
        assert_true(next[0] > 0)
        offset += next[0]
        output.extend(next[1].copy())
    return output^


def data(event: String) raises -> JsonDocument:
    var start = event.find("\r\ndata: ")
    assert_true(start >= 0 and event.endswith("\r\n\r\n"))
    return JsonDocument(String(event[byte=start + 8:event.byte_length() - 4]))


def main() raises:
    var reader = DeepSeekChatReader(7, "resp_deepseek_initial", 1, '{"deepseek":{"finish_reason":"override"},"other":true}')
    var events = collect(reader, 'data: {"id":"chat_1","created":123,"model":"deepseek-chat","system_fingerprint":"fp","choices":[{"delta":{"reasoning_content":"think","content":"Hi","refusal":"no","annotations":[{"x":1}]},"finish_reason":"stop","logprobs":false}],"usage":{"prompt_tokens":2,"completion_tokens":3}}\n\ndata: [DONE]\n\nignored')
    assert_equal(len(events), 8)
    assert_true(reader.done and reader.state.completed)
    assert_equal(len(reader.finish()), 0)
    for index in range(len(events)):
        var doc = data(events[index])
        assert_equal(doc.nodes[doc.get(doc.root, "sequence_number")].text, String(index))
    var completed = data(events[7])
    var response = completed.get(completed.root, "response")
    assert_equal(completed.string(completed.get(response, "id")), "chat_1")
    var metadata = completed.get(response, "metadata")
    var provider = completed.get(metadata, "deepseek")
    assert_equal(completed.string(completed.get(provider, "reasoning_content")), "think")
    assert_equal(completed.string(completed.get(provider, "finish_reason")), "override")
    var usage = completed.get(response, "usage")
    assert_equal(completed.nodes[completed.get(usage, "total_tokens")].text, "5")
    assert_true(reader.state.conversation_snapshot)

    var empty = DeepSeekChatReader(0, "resp_deepseek_initial", 2)
    var eof = empty.finish()
    assert_equal(len(eof), 1)
    assert_true(eof[0].find("unexpected end of stream") >= 0)
    assert_equal(len(empty.finish()), 0)

    var final_cr = DeepSeekChatReader(0, "resp_deepseek_initial", 2)
    assert_equal(len(collect(final_cr, 'data: {"choices":[{"delta":{"content":"tail"}}]}\n\r')), 0)
    var tail = final_cr.finish()
    assert_equal(len(tail), 4)
    assert_true(tail[3].find("unexpected end of stream") >= 0)

    var errored_done = DeepSeekChatReader(0, "resp_deepseek_initial", 2)
    var failed = collect(errored_done, 'data: {"error":"embedded"}\n\ndata: {\n\ndata: [DONE]\n\n')
    assert_equal(len(failed), 1)
    assert_true(errored_done.done)

    var errored_wire = DeepSeekChatReader(0, "resp_deepseek_initial", 2)
    assert_equal(len(collect(errored_wire, 'data: {"error":"embedded"}\n\n')), 1)
    var invalid: List[UInt8] = [255, 10]
    var rejected = False
    try:
        _ = errored_wire.consume(Span(invalid))
    except error:
        rejected = String(error) == "stream did not contain valid UTF-8"
    assert_true(rejected)

    var tools = DeepSeekChatReader(9, "resp_deepseek_initial", 1)
    var started = collect(tools, 'data: {"id":"chat_tools","choices":[{"delta":{"tool_calls":[{"index":4,"id":"c4","function":{"name":"lookup","arguments":"{"}},{"index":1,"id":"c1","function":{"name":"lookup","arguments":"{}"}}]}}]}\n\n')
    assert_equal(len(started), 5)
    var first_added = data(started[1])
    var first_item = first_added.get(first_added.root, "item")
    assert_equal(first_added.string(first_added.get(first_item, "call_id")), "c4")
    var fallback = DeepSeekChatState(12, "resp_deepseek_initial", 0)
    _ = fallback.observe('{"choices":[{"delta":{"tool_calls":[{"index":3,"function":{"name":"lookup","arguments":"{}"}}]}}]}')
    var fallback_message = JsonDocument(fallback.assistant_message().value())
    var fallback_calls = fallback_message.get(fallback_message.root, "tool_calls")
    var fallback_id = fallback_message.string(fallback_message.get(fallback_message.nodes[fallback_calls].children[0], "id"))
    assert_true(fallback_id.startswith("call_deepseek_"))
    assert_equal(fallback_id.byte_length(), 50)
    assert_equal(fallback_id[byte=28], "7")
    var finished = collect(tools, 'data: {"choices":[{"delta":{"tool_calls":[{"index":4,"function":{"arguments":"}"}}]},"finish_reason":"tool_calls"}]}\n\ndata: [DONE]\n\n')
    assert_equal(len(finished), 4)
    var first_done = data(finished[1])
    assert_equal(first_done.nodes[first_done.get(first_done.root, "output_index")].text, "1")
    var second_done = data(finished[2])
    assert_equal(second_done.nodes[second_done.get(second_done.root, "output_index")].text, "4")
    assert_true(tools.state.conversation_snapshot)

    var numeric = DeepSeekChatState(1, "resp_deepseek_initial", 0)
    _ = numeric.observe('{"choices":[{"delta":{"tool_calls":[{"id":"n","function":{"name":"lookup","arguments":"1e999"}}]}}]}')
    assert_true(numeric.validate_tools())
    var final = numeric.complete()
    assert_true(final[len(final) - 1].find("response.failed") >= 0)
    assert_equal(len(numeric.complete()), 0)
    var empty_arguments = DeepSeekChatState(1, "resp_deepseek_initial", 0)
    _ = empty_arguments.observe('{"choices":[{"delta":{"tool_calls":[{"id":"empty","function":{"name":"lookup"}}]}}]}')
    assert_true(not empty_arguments.validate_tools())
    var empty_complete = empty_arguments.complete()
    assert_true(empty_complete[len(empty_complete) - 1].find("response.completed") >= 0)
    var invalid_tool = DeepSeekChatState(2, "resp_deepseek_initial", 0)
    var invalid_events = invalid_tool.observe('{"choices":[{"delta":{"tool_calls":[null,{"index":1,"id":"valid","function":{"name":"lookup","arguments":"{}"}}]}}]}')
    assert_equal(len(invalid_events), 4)
    var invalid_event = data(invalid_events[1])
    assert_equal(invalid_event.string(invalid_event.get(invalid_event.root, "type")), "response.failed")
    var invalid_response = invalid_event.get(invalid_event.root, "response")
    var invalid_error = invalid_event.get(invalid_response, "error")
    assert_equal(invalid_event.string(invalid_event.get(invalid_error, "code")), "invalid_tool_call_arguments")
    assert_equal(invalid_event.string(invalid_event.get(invalid_error, "message")), "DeepSeek streamed a tool call without a function object")
    assert_true(invalid_events[2].find("response.output_item.added") >= 0)
    assert_true(invalid_events[3].find("response.function_call_arguments.delta") >= 0)
    var truncated_tool = DeepSeekChatState(3, "resp_deepseek_initial", 0)
    _ = truncated_tool.observe('{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"name":"lookup","arguments":"{\\"key\\":"}}]}}]}')
    var truncated_result = truncated_tool.complete()
    var truncated_event = data(truncated_result[len(truncated_result) - 1])
    var truncated_response = truncated_event.get(truncated_event.root, "response")
    var truncated_error = truncated_event.get(truncated_response, "error")
    assert_equal(truncated_event.string(truncated_event.get(truncated_error, "code")), "invalid_tool_call_arguments")
    assert_equal(truncated_event.string(truncated_event.get(truncated_error, "message")), "DeepSeek streamed malformed JSON arguments for tool call `lookup` at index 0: invalid JSON")
    numeric.sequence = UInt64.MAX
    assert_equal(numeric.next_sequence(), UInt64.MAX)
    assert_equal(numeric.next_sequence(), UInt64.MAX)
    print("Provider chat stream checks: PASS")
