from std.testing import assert_equal, assert_false, assert_true

from modex.json import quote_json
from modex.provider_chat_items import tool_added_item, tool_output_item, wrap_tool_arguments


def main() raises:
    assert_false(tool_added_item("call_search", "tool_search"))
    assert_equal(tool_added_item("call_patch", "apply_patch").value(), '{"type":"custom_tool_call","call_id":"call_patch","name":"apply_patch","input":""}')
    assert_equal(tool_added_item("call_東京", "mcp__org__lookup").value(), '{"type":"function_call","call_id":"call_東京","name":"lookup","namespace":"mcp__org"}')
    assert_equal(tool_added_item("call_explicit", "shell--exec").value(), '{"type":"function_call","call_id":"call_explicit","name":"exec","namespace":"shell"}')
    assert_equal(tool_added_item("call_flat", "functions__lookup").value(), '{"type":"function_call","call_id":"call_flat","name":"functions__lookup"}')
    assert_equal(tool_added_item("call_ws", "server-- ").value(), '{"type":"function_call","call_id":"call_ws","name":"server-- "}')
    assert_equal(tool_added_item("call_ns_ws", "namespace--tool--  ").value(), '{"type":"function_call","call_id":"call_ns_ws","name":"tool--  ","namespace":"namespace"}')

    assert_equal(tool_output_item("call_1", "tool_search", '{"query":"東京"}', Optional[String]()), '{"type":"tool_search_call","call_id":"call_1","execution":"client","arguments":{"query":"東京"}}')
    assert_equal(tool_output_item("call_2", "tool_search", "{bad", Optional[String]()), '{"type":"tool_search_call","call_id":"call_2","execution":"client","arguments":{}}')
    assert_equal(tool_output_item("call_array", "tool_search", '["one",2]', Optional[String]()), '{"type":"tool_search_call","call_id":"call_array","execution":"client","arguments":["one",2]}')
    assert_equal(tool_output_item("call_scalar", "tool_search", '"query"', Optional[String]()), '{"type":"tool_search_call","call_id":"call_scalar","execution":"client","arguments":"query"}')
    assert_equal(tool_output_item("call_3", "apply_patch", '{"input":"*** Begin Patch\\n*** End Patch"}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_3","name":"apply_patch","input":"*** Begin Patch\\n*** End Patch"}')
    assert_equal(tool_output_item("call_7", "apply_patch", '{"path":"note.txt","content":"hello"}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_7","name":"apply_patch","input":"*** Begin Patch\\n*** Add File: note.txt\\n+hello\\n*** End Patch"}')
    assert_equal(tool_output_item("call_update", "apply_patch", '{"filename":" note.txt ","old_string":"old","new_string":"new"}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_update","name":"apply_patch","input":"*** Begin Patch\\n*** Update File: note.txt\\n@@\\n-old\\n+new\\n*** End Patch"}')
    assert_equal(tool_output_item("call_empty_new", "apply_patch", '{"path":"note.txt","old":"old","new":""}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_empty_new","name":"apply_patch","input":"*** Begin Patch\\n*** Update File: note.txt\\n@@\\n-old\\n*** End Patch"}')
    assert_equal(tool_output_item("call_empty_add", "apply_patch", '{"path":"note.txt","new":""}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_empty_add","name":"apply_patch","input":"*** Begin Patch\\n*** Add File: note.txt\\n+\\n*** End Patch"}')
    assert_equal(tool_output_item("call_old_only", "apply_patch", '{"path":"gone.txt","old":"old"}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_old_only","name":"apply_patch","input":"{\\"old\\":\\"old\\",\\"path\\":\\"gone.txt\\"}"}')
    assert_equal(tool_output_item("call_patch_string", "apply_patch", '"*** Begin Patch\\n*** Add File: note.txt\\nhello\\n*** End Patch"', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_patch_string","name":"apply_patch","input":"*** Begin Patch\\n*** Add File: note.txt\\n+hello\\n*** End Patch"}')
    assert_equal(tool_output_item("call_block_space", "apply_patch", '{"input":"  *** Begin Patch\\r\\n*** Add File: note.txt\\r\\nhello\\r\\n*** End Patch"}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_block_space","name":"apply_patch","input":"  *** Begin Patch\\n*** Add File: note.txt\\n+hello\\n*** End Patch"}')
    assert_equal(tool_output_item("call_cr", "apply_patch", '{"path":"note.txt","content":"hello\\rworld"}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_cr","name":"apply_patch","input":"*** Begin Patch\\n*** Add File: note.txt\\n+hello\\n+world\\n*** End Patch"}')
    assert_equal(tool_output_item("call_alias_barrier", "apply_patch", '{"path":"note.txt","old_string":"","old":"ignored","new":"body"}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_alias_barrier","name":"apply_patch","input":"*** Begin Patch\\n*** Add File: note.txt\\n+body\\n*** End Patch"}')
    assert_equal(tool_output_item("call_path_barrier", "apply_patch", '{"file_path":"  ","path":"note.txt","new":"body"}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_path_barrier","name":"apply_patch","input":' + quote_json('{"file_path":"  ","new":"body","path":"note.txt"}') + '}')
    var unicode_edit = '{"filename":' + quote_json("  docs/雪.rs\t") + ',"old_string":"before","new_string":"after"}'
    assert_equal(tool_output_item("call_unicode_path", "apply_patch", unicode_edit, Optional[String]()), '{"type":"custom_tool_call","call_id":"call_unicode_path","name":"apply_patch","input":"*** Begin Patch\\n*** Update File: docs/雪.rs\\n@@\\n-before\\n+after\\n*** End Patch"}')
    assert_equal(tool_output_item("call_invalid_edit", "apply_patch", '{"path":42,"new":["not","text"]}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_invalid_edit","name":"apply_patch","input":' + quote_json('{"new":["not","text"],"path":42}') + '}')
    assert_equal(tool_output_item("call_explicit_empty", "apply_patch", '{"input":"","patch":"*** Begin Patch\\n*** End Patch"}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_explicit_empty","name":"apply_patch","input":""}')
    assert_equal(tool_output_item("call_bad_diff", "apply_patch", '{"diff":"diff --git a/file b/file\\nmalformed"}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_bad_diff","name":"apply_patch","input":"diff --git a/file b/file\\nmalformed"}')
    assert_equal(tool_output_item("call_move", "apply_patch", '{"diff":"diff --git a/README.md b/docs/README.md\\n--- a/README.md\\n+++ b/docs/README.md\\n@@ -1 +1 @@ title\\n-old\\n+new\\n"}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_move","name":"apply_patch","input":"*** Begin Patch\\n*** Update File: README.md\\n*** Move to: docs/README.md\\n@@ title\\n-old\\n+new\\n*** End Patch"}')
    assert_equal(tool_output_item("call_multi", "apply_patch", '{"diff":"--- /dev/null\\n+++ b/one.txt\\n@@ -0,0 +1,2 @@\\n+first\\n+\\n--- a/two.txt\\n+++ /dev/null\\n"}', Optional[String]()), '{"type":"custom_tool_call","call_id":"call_multi","name":"apply_patch","input":"*** Begin Patch\\n*** Add File: one.txt\\n+first\\n+\\n*** Delete File: two.txt\\n*** End Patch"}')
    var git_diff = "diff --git a/note.txt b/note.txt\nindex 123..456\n--- a/note.txt\n+++ b/note.txt\n@@ -1 +1 @@\n--- literal\n+++ literal\n"
    var git_item = tool_output_item("git", "apply_patch", '{"diff":' + quote_json(git_diff) + '}', Optional[String]())
    assert_equal(git_item, '{"type":"custom_tool_call","call_id":"git","name":"apply_patch","input":' + quote_json("*** Begin Patch\n*** Update File: note.txt\n@@\n--- literal\n+++ literal\n*** End Patch") + '}')
    var spaced_null = "---  /dev/null \n+++ b/note.txt\n@@ -1 +1 @@\n-old\n+new\n"
    assert_equal(tool_output_item("literal", "apply_patch", '{"diff":' + quote_json(spaced_null) + '}', Optional[String]()), '{"type":"custom_tool_call","call_id":"literal","name":"apply_patch","input":' + quote_json("*** Begin Patch\n*** Update File: /dev/null\n*** Move to: note.txt\n@@\n-old\n+new\n*** End Patch") + '}')
    var unicode_diff = "--- a/ note.txt \n+++ b/ note.txt \n@@ -1 +1 @@  context  \n-old\n+new\n"
    assert_equal(tool_output_item("unicode", "apply_patch", '{"diff":' + quote_json(unicode_diff) + '}', Optional[String]()), '{"type":"custom_tool_call","call_id":"unicode","name":"apply_patch","input":' + quote_json("*** Begin Patch\n*** Update File:  note.txt \n@@  context \n-old\n+new\n*** End Patch") + '}')
    assert_equal(tool_output_item("call_4", "mcp__org__lookup", '{"q":"東京"}', Optional[String]("sig")), '{"type":"function_call","call_id":"call_4","name":"lookup","arguments":"{\\"q\\":\\"東京\\"}","namespace":"mcp__org","gemini_thought_signature":"sig"}')

    assert_equal(wrap_tool_arguments("exec", '{"cmd":"cargo test","other":1}'), '{"cmd":"rtk cargo test","other":1}')
    assert_equal(wrap_tool_arguments("exec", '{"z":1,"cmd":"cargo test","a":2}'), '{"a":2,"cmd":"rtk cargo test","z":1}')
    assert_equal(wrap_tool_arguments("exec", '{"cmd":"quiet","cmd":"cargo test"}'), '{"cmd":"rtk cargo test"}')
    assert_equal(wrap_tool_arguments("shell", '{"command":"pwd && cargo check"}'), '{"command":"rtk pwd && cargo check"}')
    assert_equal(wrap_tool_arguments("exec", '{"cmd":"pwd"}'), '{"cmd":"pwd"}')
    assert_equal(wrap_tool_arguments("exec", "{bad"), "{bad")
    assert_equal(wrap_tool_arguments("other", '{"cmd":"cargo test"}'), '{"cmd":"cargo test"}')
    print("Provider chat item checks: PASS")
