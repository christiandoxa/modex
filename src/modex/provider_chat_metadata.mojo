"""Provider and request metadata merge used by chat response assembly."""

from .json import JSON_OBJECT, JsonDocument, quote_json, serialize_json


def merge_chat_metadata(provider_metadata: String, request_metadata: String) raises -> String:
    var provider = JsonDocument(provider_metadata)
    var request = JsonDocument(request_metadata)
    var left = _canonical_doc(provider)
    var right = _canonical_doc(request)
    var left_root = left.root
    var right_root = right.root
    if right.nodes[right_root].kind != JSON_OBJECT:
        return serialize_json(left, left_root)
    if left.nodes[left_root].kind != JSON_OBJECT:
        return serialize_json(right, right_root)
    var result = _merge_objects(left, right, left_root, right_root, True)
    var merged = JsonDocument(result)
    return serialize_json(merged, merged.root)


def _canonical_doc(doc: JsonDocument) raises -> JsonDocument:
    var text = serialize_json(doc, doc.root)
    return JsonDocument(text)


def _merge_objects(left: JsonDocument, right: JsonDocument, left_node: Int, right_node: Int, merge_nested: Bool) -> String:
    var result = "{"
    var count = 0
    for i in range(len(left.nodes[left_node].children)):
        var key = left.nodes[left_node].names[i]
        var right_node_value = right.get(right_node, key)
        if count:
            result += ","
        result += quote_json(key) + ":"
        if right_node_value < 0:
            result += serialize_json(left, left.nodes[left_node].children[i])
        elif merge_nested and right.nodes[right_node_value].kind == JSON_OBJECT:
            var left_value = left.nodes[left_node].children[i]
            if left.nodes[left_value].kind == JSON_OBJECT:
                result += _merge_objects(left, right, left_value, right_node_value, False)
            else:
                result += serialize_json(left, left_value)
        else:
            result += serialize_json(right, right_node_value)
        count += 1
    for i in range(len(right.nodes[right_node].children)):
        var key = right.nodes[right_node].names[i]
        if left.get(left_node, key) < 0:
            if count:
                result += ","
            result += quote_json(key) + ":" + serialize_json(right, right.nodes[right_node].children[i])
            count += 1
    return result + "}"
