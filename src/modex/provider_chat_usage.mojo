"""Chat response usage projection for the DeepSeek-compatible provider."""

from .json import JSON_NUMBER, JSON_OBJECT, JsonDocument, quote_json, serialize_json, serialize_number
from .text import unsigned_value


def json_unsigned(doc: JsonDocument, node: Int) -> Optional[UInt64]:
    if node < 0 or doc.nodes[node].kind != JSON_NUMBER:
        return Optional[UInt64]()
    var text = serialize_number(doc.nodes[node].text)
    if text.startswith("-") or text.find(".") >= 0 or text.find("e") >= 0 or text.find("E") >= 0:
        return Optional[UInt64]()
    try:
        return Optional[UInt64](unsigned_value(text))
    except:
        return Optional[UInt64]()


def chat_usage(doc: JsonDocument, usage: Int, provider: String) raises -> String:
    if usage < 0:
        return "null"
    var input_tokens = UInt64(0)
    var output_tokens = UInt64(0)
    var total_tokens: UInt64
    var cache_hit = Optional[UInt64]()
    var cache_miss = Optional[UInt64]()
    var reasoning = Optional[UInt64]()
    if doc.nodes[usage].kind == JSON_OBJECT:
        var value = json_unsigned(doc, doc.get(usage, "prompt_tokens"))
        if value:
            input_tokens = value.value()
        value = json_unsigned(doc, doc.get(usage, "completion_tokens"))
        if value:
            output_tokens = value.value()
        value = json_unsigned(doc, doc.get(usage, "total_tokens"))
        if value:
            total_tokens = value.value()
        else:
            total_tokens = UInt64.MAX if output_tokens > UInt64.MAX - input_tokens else input_tokens + output_tokens
        cache_hit = json_unsigned(doc, doc.get(usage, "prompt_cache_hit_tokens"))
        cache_miss = json_unsigned(doc, doc.get(usage, "prompt_cache_miss_tokens"))
        var details = doc.get(usage, "completion_tokens_details")
        if details >= 0 and doc.nodes[details].kind == JSON_OBJECT:
            reasoning = json_unsigned(doc, doc.get(details, "reasoning_tokens"))
    else:
        total_tokens = 0

    var result = "{\"input_tokens\":" + String(input_tokens) + ",\"output_tokens\":" + String(output_tokens) + ",\"total_tokens\":" + String(total_tokens)
    if cache_hit:
        result += ",\"input_tokens_details\":{\"cached_tokens\":" + String(cache_hit.value()) + "}"
    if reasoning:
        result += ",\"output_tokens_details\":{\"reasoning_tokens\":" + String(reasoning.value()) + "}"
    if cache_hit or cache_miss:
        result += ",\"metadata\":{" + quote_json(provider) + ":{\"prompt_cache_hit_tokens\":" + String(cache_hit.value() if cache_hit else UInt64(0)) + ",\"prompt_cache_miss_tokens\":" + String(cache_miss.value() if cache_miss else UInt64(0)) + "}}"
    result += "}"
    var canonical = JsonDocument(result)
    return serialize_json(canonical, canonical.root)
