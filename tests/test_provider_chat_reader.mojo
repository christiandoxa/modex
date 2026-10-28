from std.collections import List, Span
from std.testing import assert_equal, assert_true

from modex.provider_chat_reader import DeepSeekChatReader


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


def anthropic_search_to_result() -> String:
    return 'data: {"type":"content_block_start","index":0,"content_block":{"type":"server_tool_use","id":"search_1","name":"web_search","input":{}}}\n\n' + 'data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\\"query\\":\\"query\\"}"}}\n\n' + 'data: {"type":"content_block_stop","index":0}\n\n' + 'data: {"type":"content_block_start","index":1,"content_block":{"type":"web_search_tool_result","tool_use_id":"search_1","content":[{"type":"web_search_result","url":"https://example.test"}]}}\n\n' + 'data: {"type":"content_block_stop","index":1}\n\n'


def assert_anthropic_failed(source: String) raises:
    var reader = DeepSeekChatReader(9, "resp_deepseek_initial", 1, native_messages=True)
    var events = collect(reader, source)
    if not reader.done:
        events.extend(reader.finish())
    assert_true(reader.done and reader.state.completed)
    assert_true(len(events) > 0 and events[len(events) - 1].startswith("event: response.failed\r\n"))


def main() raises:
    var reader = DeepSeekChatReader(7, "resp_deepseek_initial", 1)
    var events = collect(reader, 'data: {"choices":[{"delta":{"content":"kept"}}]}\ndata: {"error":{"message":"synthetic failure"}}\n\ndata: [DONE]\n\n')
    assert_true(reader.done and reader.state.completed)
    assert_equal(len(events), 4)
    assert_true(events[0].startswith("event: response.created\r\n"))
    assert_true(events[2].startswith("event: response.output_text.delta\r\n"))
    assert_true('"delta":"kept"' in events[2])
    assert_true(events[3].startswith("event: response.failed\r\n"))
    assert_true("synthetic failure" in events[3])
    reader = DeepSeekChatReader(8, "resp_deepseek_initial", 1)
    events = collect(reader, 'data: {"choices":[{"delta":{"content":"one"}}]}\ndata: {"choices":[{"delta":{"content":"two"}}]}\n\ndata: [DONE]\n\n')
    assert_true(reader.done and reader.state.completed)
    assert_true('"delta":"one"' in events[2])
    assert_true('"delta":"two"' in events[3])
    assert_true(events[len(events) - 1].startswith("event: response.completed\r\n"))
    assert_equal(len(reader.finish()), 0)

    var message_start = 'data: {"type":"message_start","message":{"id":"msg_search","type":"message","role":"assistant","model":"deepseek-chat","usage":{"input_tokens":3,"output_tokens":0}}}\n\n'
    var search_result = anthropic_search_to_result()
    var text_start = 'data: {"type":"content_block_start","index":2,"content_block":{"type":"text","text":""}}\n\n'
    var text_delta = 'data: {"type":"content_block_delta","index":2,"delta":{"type":"text_delta","text":"Found it."}}\n\n'
    var text_stop = 'data: {"type":"content_block_stop","index":2}\n\n'
    var message_delta = 'data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":5}}\n\n'
    var ping = 'event: ping\ndata: {"type":"ping"}\n\n'
    var valid_native = message_start + ping + search_result + ping + text_start + text_delta + ping + text_stop + message_delta + 'data: {"type":"message_stop"}\n\n'
    var native_reader = DeepSeekChatReader(9, "resp_deepseek_initial", 1, native_messages=True)
    var native_events = collect(native_reader, valid_native)
    assert_true(native_reader.done and native_reader.state.completed)
    assert_true(native_events[len(native_events) - 1].startswith("event: response.completed\r\n"))

    assert_anthropic_failed(search_result + text_start + text_delta + text_stop + message_delta + 'data: {"type":"message_stop"}\n\n')
    assert_anthropic_failed(message_start + search_result + text_start + text_delta + text_stop + message_delta + 'data: [DONE]\n\n')
    assert_anthropic_failed(message_start + search_result + text_start + text_delta + text_stop + 'data: {"type":"message_stop"}\n\n')
    assert_anthropic_failed(message_start + search_result + 'data: {"type":"content_block_start","index":2,"content_block":{"type":"text","text":"unstreamed"}}\n\n')
    assert_anthropic_failed(message_start + 'data: {"type":"future_event"}\n\n')
    print("Provider chat reader checks: PASS")
