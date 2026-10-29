"""Synthetic Anthropic server-search event fixtures shared by release tests."""

from test_anthropic_text_stream_04392 import MESSAGE_DELTA, START, STOP, stream


def repeated_search_case(shared_id=False):
    request = {
        "model": "deepseek-chat",
        "input": "synthetic query",
        "stream": True,
        "tools": [{"type": "web_search_preview"}],
    }
    first_id = "shared_search" if shared_id else "search_1"
    second_id = "shared_search" if shared_id else "search_2"
    events = [
        START,
        {"type": "content_block_start", "index": 0, "content_block": {
            "type": "server_tool_use", "id": first_id, "name": "web_search", "input": {},
        }},
        {"type": "content_block_delta", "index": 0, "delta": {
            "type": "input_json_delta", "partial_json": '{"query":"first"}',
        }},
        {"type": "content_block_stop", "index": 0},
        {"type": "content_block_start", "index": 1, "content_block": {
            "type": "web_search_tool_result", "tool_use_id": first_id, "content": [
                {"type": "web_search_result", "url": "https://one.example.test", "title": "One"},
            ],
        }},
        {"type": "content_block_stop", "index": 1},
        {"type": "content_block_start", "index": 2, "content_block": {
            "type": "server_tool_use", "id": second_id, "name": "web_search", "input": {},
        }},
        {"type": "content_block_delta", "index": 2, "delta": {
            "type": "input_json_delta", "partial_json": '{"query":"second"}',
        }},
        {"type": "content_block_stop", "index": 2},
        {"type": "content_block_start", "index": 3, "content_block": {
            "type": "web_search_tool_result", "tool_use_id": second_id, "content": [
                {"type": "web_search_result", "url": "https://two.example.test", "title": "Two"},
            ],
        }},
        {"type": "content_block_stop", "index": 3},
        {"type": "content_block_start", "index": 4, "content_block": {
            "type": "text", "text": "",
        }},
        {"type": "content_block_delta", "index": 4, "delta": {
            "type": "text_delta", "text": "Found both.",
        }},
        {"type": "content_block_stop", "index": 4},
        MESSAGE_DELTA,
        STOP,
    ]
    reply = {
        "status": 200,
        "content_type": "text/event-stream",
        "body": stream(events),
    }
    return request, reply
