"""Scoped in-memory provider history and frozen bounded retention rules."""

from std.collections import List

from .json import JSON_ARRAY, JSON_BOOL, JSON_NUMBER, JSON_STRING, JsonDocument, quote_json, serialize_json
from .provider_request_messages import _history_has_call

comptime CONVERSATION_SCOPE_LIMIT = 256
comptime CONVERSATION_TOTAL_LIMIT = 2048
comptime CONVERSATION_BYTE_LIMIT = 67108864
comptime CONVERSATION_SCOPE_PREFIX = "\0prodex:"


def conversation_key(response_id: String, namespace: Optional[String] = None) -> String:
    if namespace:
        var name = namespace.value()
        return CONVERSATION_SCOPE_PREFIX + String(name.byte_length()) + ":" + name + ":" + response_id
    return response_id


def _in_scope(key: String, namespace: Optional[String]) -> Bool:
    if namespace:
        return key.startswith(conversation_key("", namespace))
    return not key.startswith(CONVERSATION_SCOPE_PREFIX)


def _saturating_estimate_add(total: UInt64, extra: UInt64) -> UInt64:
    if total > UInt64.MAX - extra:
        return UInt64.MAX
    return total + extra


def conversation_estimated_bytes(key: String, messages: String) raises -> UInt64:
    var original = JsonDocument(messages)
    var doc = JsonDocument(serialize_json(original, original.root))
    if doc.nodes[doc.root].kind != JSON_ARRAY:
        raise Error("provider conversation messages must be an array")
    # Infer logical cache weights from frozen 64-bit Serde types; artifact eviction boundaries still need checking.
    # The frozen estimator clamps to usize::MAX instead of allowing overflow.
    var estimated = UInt64(key.byte_length())
    for index in range(len(doc.nodes)):
        if index == doc.root:
            continue
        estimated = _saturating_estimate_add(estimated, 32)
        var node = doc.nodes[index].copy()
        if node.kind == JSON_BOOL:
            estimated = _saturating_estimate_add(estimated, 1)
        elif node.kind == JSON_NUMBER:
            estimated = _saturating_estimate_add(estimated, 16)
        elif node.kind == JSON_STRING:
            estimated = _saturating_estimate_add(estimated, UInt64(node.text.byte_length()))
        for name in node.names:
            estimated = _saturating_estimate_add(estimated, UInt64(name.byte_length()))
    return estimated


@fieldwise_init
struct ProviderConversation(Copyable):
    var key: String
    var messages: String
    var sequence: UInt64
    var estimated_bytes: UInt64


struct ProviderConversationStore:
    var rows: List[ProviderConversation]
    var next_sequence: UInt64
    var estimated_bytes: UInt64

    def __init__(out self):
        self.rows = List[ProviderConversation]()
        self.next_sequence = 0
        self.estimated_bytes = 0

    def history(self, response_id: String, namespace: Optional[String] = None) -> Optional[String]:
        var key = conversation_key(response_id, namespace)
        for row in self.rows:
            if row.key == key:
                return Optional[String](row.messages)
        return Optional[String]()

    def contains(self, response_id: String, namespace: Optional[String] = None) -> Bool:
        return Bool(self.history(response_id, namespace))

    def find_tool_history(self, call_id: String, namespace: Optional[String] = None) raises -> Optional[String]:
        var item = JsonDocument('{"call_id":' + quote_json(call_id) + "}")
        var selected = -1
        for index in range(len(self.rows)):
            if not _in_scope(self.rows[index].key, namespace):
                continue
            var history = JsonDocument(self.rows[index].messages)
            if _history_has_call(history, item, item.root) and (selected < 0 or self.rows[index].sequence >= self.rows[selected].sequence):
                selected = index
        return Optional[String](self.rows[selected].messages) if selected >= 0 else Optional[String]()

    def _remove(mut self, index: Int):
        self.estimated_bytes -= self.rows[index].estimated_bytes
        _ = self.rows.pop(index)

    def _oldest(self, namespace: Optional[String], scoped: Bool) -> Int:
        var selected = -1
        for index in range(len(self.rows)):
            if scoped and not _in_scope(self.rows[index].key, namespace):
                continue
            if selected < 0 or self.rows[index].sequence < self.rows[selected].sequence:
                selected = index
        return selected

    def insert(mut self, response_id: String, messages: String, namespace: Optional[String] = None) raises:
        var doc = JsonDocument(messages)
        var canonical = serialize_json(doc, doc.root)
        var key = conversation_key(response_id, namespace)
        var estimated = conversation_estimated_bytes(key, canonical)
        for index in range(len(self.rows)):
            if self.rows[index].key == key:
                self._remove(index)
                break
        if estimated > UInt64(CONVERSATION_BYTE_LIMIT):
            return
        if self.next_sequence < UInt64.MAX:
            self.next_sequence += 1
        var position = 0
        while position < len(self.rows) and self.rows[position].key < key:
            position += 1
        self.rows.insert(position, ProviderConversation(key, canonical, self.next_sequence, estimated))
        self.estimated_bytes += estimated
        var scope_count = 0
        for row in self.rows:
            if _in_scope(row.key, namespace):
                scope_count += 1
        while scope_count > CONVERSATION_SCOPE_LIMIT:
            self._remove(self._oldest(namespace, True))
            scope_count -= 1
        while len(self.rows) > CONVERSATION_TOTAL_LIMIT or self.estimated_bytes > UInt64(CONVERSATION_BYTE_LIMIT):
            self._remove(self._oldest(None, False))
