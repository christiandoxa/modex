from std.testing import assert_equal, assert_true

from modex.provider_conversations import ProviderConversation, ProviderConversationStore, conversation_estimated_bytes, conversation_key


def main() raises:
    var store = ProviderConversationStore()
    store.insert("response", '[{"content":"root"}]')
    store.insert("response", '[{"content":"tenant"}]', "a")
    store.insert("response", '[{"content":"other"}]', "a:b")
    assert_equal(store.history("response").value(), '[{"content":"root"}]')
    assert_equal(store.history("response", "a").value(), '[{"content":"tenant"}]')
    assert_equal(store.history("response", "a:b").value(), '[{"content":"other"}]')
    assert_true(not store.contains("response", "absent"))
    assert_equal(conversation_key("response", "é"), "\0prodex:2:é:response")
    assert_equal(conversation_estimated_bytes("é", "[]"), UInt64(2))
    assert_equal(conversation_estimated_bytes("resp-", '[null,false,true,-42,"é",[null,{"鍵":"値","x":[]}]]'), UInt64(5 + 10 * 32 + 2 + 16 + 2 + 3 + 3 + 1))
    store.insert("response", '[{"nested":[true,null,"é"]}]')
    assert_equal(store.next_sequence, UInt64(4))
    assert_equal(len(store.rows), 3)
    store.insert("older", '[{"tool_calls":[{"id":"synthetic-call"}],"content":"old"}]', "a")
    store.insert("newer", '[{"tool_calls":[{"id":"synthetic-call"}],"content":"new"}]', "a")
    store.insert("other", '[{"tool_calls":[{"id":"synthetic-call"}],"content":"other"}]', "b")
    assert_equal(store.find_tool_history("synthetic-call", "a").value(), '[{"content":"new","tool_calls":[{"id":"synthetic-call"}]}]')
    assert_true(not store.find_tool_history("synthetic-call"))
    assert_true(not store.find_tool_history("missing", "a"))
    for index in range(len(store.rows)):
        store.rows[index].sequence = UInt64.MAX
    store.next_sequence = UInt64.MAX
    assert_equal(store.find_tool_history("synthetic-call", "a").value(), '[{"content":"old","tool_calls":[{"id":"synthetic-call"}]}]')

    var scoped = ProviderConversationStore()
    scoped.insert("other", "[]", "b")
    for index in range(257):
        scoped.insert("response-" + String(index), "[]", "a")
    assert_true(not scoped.contains("response-0", "a"))
    assert_true(scoped.contains("response-256", "a"))
    assert_true(scoped.contains("other", "b"))
    assert_equal(len(scoped.rows), 257)

    var global_store = ProviderConversationStore()
    for index in range(2048):
        global_store.insert("response", "[]", "tenant-" + String(index))
    global_store.insert("new", "[]")
    assert_equal(len(global_store.rows), 2048)
    assert_true(not global_store.contains("response", "tenant-0"))
    assert_true(global_store.contains("new"))

    var saturated = ProviderConversationStore()
    saturated.next_sequence = UInt64.MAX
    for index in range(257):
        saturated.insert(String(index), "[]")
    assert_equal(saturated.next_sequence, UInt64.MAX)
    assert_true(not saturated.contains("0"))
    assert_equal(len(saturated.rows), 256)

    var budget = ProviderConversationStore()
    budget.rows.append(ProviderConversation("old", "[]", 1, 67108864))
    budget.next_sequence = 1
    budget.estimated_bytes = 67108864
    budget.insert("new", "[]")
    assert_true(not budget.contains("old"))
    assert_equal(budget.estimated_bytes, UInt64(3))
    var replacement = ProviderConversationStore()
    replacement.insert("response", '["old"]')
    replacement.insert("response", '["' + String("x") * 67108864 + '"]')
    assert_true(not replacement.contains("response"))
    assert_equal(replacement.next_sequence, UInt64(1))
    assert_equal(replacement.estimated_bytes, UInt64(0))
    print("Provider conversation cache checks: PASS")
