"""Native construction of provider response SSE events."""

from .json import JsonDocument, quote_json, serialize_json
from .log_redaction import redact_log_text


def sse_event(name: String, data: String) raises -> String:
    var document = JsonDocument(data)
    return "event: " + name + "\r\ndata: " + serialize_json(document, document.root) + "\r\n\r\n"


def sse_failed_event(sequence: UInt64, created: UInt64, response_id: String, code: String, message: String) raises -> String:
    var body = "{\"response\":{\"error\":{" + quote_json("code") + ":" + quote_json(code) + ",\"message\":" + quote_json(redact_log_text(message)) + "},\"id\":" + quote_json(response_id) + "},\"sequence_number\":" + String(sequence) + ",\"created_at\":" + String(created) + ",\"type\":\"response.failed\"}"
    return sse_event("response.failed", body)


def sse_text_item_added(sequence: UInt64, response_id: String, item_id: String) raises -> String:
    var body = "{\"item\":{\"content\":[],\"id\":" + quote_json(item_id) + ",\"role\":\"assistant\",\"type\":\"message\"},\"response_id\":" + quote_json(response_id) + ",\"sequence_number\":" + String(sequence) + ",\"type\":\"response.output_item.added\"}"
    return sse_event("response.output_item.added", body)


def sse_text_item_done(sequence: UInt64, response_id: String, item_id: String, text: String) raises -> String:
    var body = "{\"item\":{\"content\":[{\"text\":" + quote_json(text) + ",\"type\":\"output_text\"}],\"id\":" + quote_json(item_id) + ",\"role\":\"assistant\",\"type\":\"message\"},\"response_id\":" + quote_json(response_id) + ",\"sequence_number\":" + String(sequence) + ",\"type\":\"response.output_item.done\"}"
    return sse_event("response.output_item.done", body)
