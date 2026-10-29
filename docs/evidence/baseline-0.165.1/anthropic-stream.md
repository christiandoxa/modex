# Anthropic stream stop fields against 0.165.1

The pinned source reader takes `stop_reason` only when it is a string and does
not use `stop_sequence`. Before this change, Modex rejected a missing or
non-string reason and a non-string sequence. The production stream parser now
accepts those cases with the observed release mapping.

`tests/test_provider_stream_01651_characterization.py` compares complete
normalized events, the synthetic upstream request, status and cleanup through
real Super dispatch for eight cases: normal end turn, tool use, token limit,
null, missing or non-string reason, non-string sequence, and no message delta.
The checksum-verified 0.165.1 binary and Modex matched on Linux x86-64. The
native reader unit covers these cases as well. The separately pinned 0.439.2
regression remains historical.

The initial web-search control covered one search/result pair. Other event
orders, metadata and error conditions, WebSockets, and non-Linux targets remain
unverified; no provider contract is promoted to PASS.

The release also ignores unknown Anthropic event types. A synthetic future event
previously failed Modex; both production processes now complete the same tested
stream. Known malformed events remain subject to validation.

The production parser also maps a tested Anthropic `tool_use` block and split
`input_json_delta` fragments into Responses function-call events. A synthetic
loopback comparison matches the complete 0.165.1 event sequence, upstream
request and cleanup. Additional controls cover duplicate index, missing stop,
orphan and mismatched indices, duplicate/reopened stops, and deltas after stop.
Some malformed stop sequences complete in the release but remain rejected in
Modex; image blocks also remain a documented mismatch. This is not general
function-tool or event-order parity.

Selected mixed text/function streams now match the release with text before or
after multiple function calls, argument deltas and stops while text is open,
and a late argument delta after `message_delta`. The real-process comparisons
also check the observed output indexes and ignore a trailing event after
`message_stop`. Mixed server-side web search and user-function streams remain
unverified; previous support remains unchanged.

For a tested text block, the 0.165.1 release ignores the initial `text` field
and emits later text deltas. Modex now matches full normalized events when the
initial field is nonempty, empty, missing, or numeric. The old 0.439.2
characterization was updated after reproducing the same behavior; other content
block shapes and event orders remain unverified.

A two-search stream with sequential `server_tool_use`/`web_search_tool_result`
pairs at indexes 0/1 and 2/3, followed by text at index 4, now matches both the
0.165.1 release and historical 0.439.2 through real Super dispatch. The test
compares the Anthropic request path and body, complete normalized event
sequences, query/source order, final text and HTTP status. Both searches use a
synthetic loopback upstream, synthetic keys, and isolated HOME, state, and work
directories. This qualifies the tested serial shape only. Interleaved search
calls/results and mixed server-side search with user-function calls remain
unverified. The mixed request path also remains unsupported: Modex requires one
`web_search_preview` request tool and does not translate function declarations
to Anthropic `input_schema` values.

Two serial searches with the same `server_tool_use.id` also match both real
release binaries. The first result completes the earliest matching search. The
second result is accepted against that already-completed ID, then the later
search is completed at `message_stop` with no sources. The production reader
uses ordered append and binary block-index lookup plus an earliest-ID index, so
serial search handling avoids cumulative quadratic list scans. It still retains
search records and completed output items in memory proportional to stream
search count. The upstream SSE body has no aggregate byte or search-count cap;
that linear-memory bound remains a gap for long-lived streams.
