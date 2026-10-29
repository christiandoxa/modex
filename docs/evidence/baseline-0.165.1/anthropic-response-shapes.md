# Anthropic response metadata and search query shapes

The response parser now ignores unknown fields on selected Anthropic content
blocks and stream events, as both pinned processes do. It still validates known
block types, required search and result IDs, tool names, JSON fragments, and
the 65,536 buffered content-block limit. Request validation remains strict.

For `server_tool_use.input`, the releases prefer a string `query`. If it is not
a string, they project `queries` when it is an array. Buffered responses keep
string array entries only; streamed responses retain every JSON value. Missing
or invalid query fields produce `queries: []`. The stream also generates a
`call_deepseek_...` ID when a function `tool_use` omits its ID. Buffered
function calls without an ID still fail.

Frozen source trace:

- Prodex 0.165.1 commit
  `10ae15b5d1806302b60f051e4e6fec788044f4c2` reads only selected content-block
  keys in `mojo/prodex_core/anthropic_request.mojo:1048-1114`; the
  `preserve_non_string_values` switch controls `queries` array filtering.
  Its generic stream state supplies the fallback call ID in
  `crates/prodex-app/src/runtime_launch/proxy_startup/deepseek_sse.rs:129-139`.
- Prodex 0.439.2 commit
  `72b77478a5198fc5da6b4d2253137f9cdbf43be9` passes full search blocks to the
  response kernel in
  `crates/prodex-provider-core/src/translators/anthropic/messages/web_search.rs:6-20`.
  Its stream reader forwards optional function-call IDs to the shared chat
  state in `crates/prodex-app/src/runtime_launch/proxy_startup/anthropic_messages_sse_reader.rs:135-148`;
  the shared state creates missing call IDs in
  `crates/prodex-app/src/runtime_launch/proxy_startup/deepseek_sse.rs:129-139`.

`test_buffered_text_block_citations_and_extra_fields_match_both_releases`,
`test_buffered_search_query_shapes_match_both_releases`,
`test_stream_search_query_shapes_and_metadata_match_both_releases`, and
`test_stream_missing_function_id_uses_release_fallback` compare complete
responses, events, upstream requests, and cleanup against the checksum-pinned
0.165.1 and 0.439.2 Linux processes. The tests use synthetic provider replies,
keys, Codex peers, isolated directories, and loopback traffic.

Validation: `make build` passed. The earlier 53-method run of
`test_anthropic_mixed_tools_01651.py` passed on Linux x86-64. After the final
test-only edits, `test_buffered_search_query_shapes_match_both_releases` and
`test_stream_numeric_function_argument_fragment_remains_strict` passed in a
focused run; a full rerun was stopped before completion. Oracle hashes are
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` for
0.165.1 and `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`
for 0.439.2.

One stream mismatch remains guarded: when `input_json_delta.partial_json` is
numeric, both releases complete with an empty function-call argument string;
Modex fails the stream because the fragment is not a string. Other Anthropic
content blocks, broader event orders, continuation, transport security, and
non-Linux release targets remain unqualified.
