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

The controls below cover selected search/result event orders. Other event
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
`message_stop`. These checks cover text and function blocks only; mixed
server-side search and user-function streams are covered below.

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
directories. This qualifies the tested serial shape only; interleaved mixed
search/function events are covered below.

Two serial searches with the same `server_tool_use.id` also match both real
release binaries. The first result completes the earliest matching search. The
second result is accepted against that already-completed ID, then the later
search is completed at `message_stop` with no sources. The production reader
uses ordered append and binary block-index lookup plus an earliest-ID index, so
serial search handling avoids cumulative quadratic list scans. It still retains
search records and completed output items in memory proportional to stream
search count. The upstream SSE body has no aggregate byte or search-count cap;
that linear-memory bound remains a gap for long-lived streams.

## Interleaved mixed function and web-search streams

The checksum-pinned 0.165.1 process accepts multiple overlapping
`server_tool_use` blocks, function use and argument deltas while those searches
are open, and overlapping `web_search_tool_result` blocks whose stop events
arrive in reverse order. Search completion events follow result-start order;
their output indexes remain the original Anthropic content-block indexes. The
production reader now tracks each search block's stop state and only retains
currently open result indexes, while mapping results by the earliest matching
tool-use ID as the release does.

`tests/provider_stream_search_cases.py` generates isolated synthetic streams
with fragmented valid queries and function arguments, two interleaved searches,
overlapping reversed results, duplicate IDs, and a 64-search stress case. The
real Super process comparison checks the upstream Messages path/body and full
normalized response event sequence against the checksum-verified 0.165.1
oracle. A pending search with no result is completed at `message_stop`, matching
the release. Provider error events fail the stream without a completed
response. Separate loopback, relay, and transport downstream-reset tests still
close the active upstream stream.

A result can also start and stop after its matching search closes while another
search input remains open; deltas for that search work while the result block is
open and after it stops. An empty valid result array completes with
`sources: []`, as in the release. The parser tracks open search inputs and
result blocks independently and keeps the existing result-array and result-item
validation.

For search input, the release emits `queries: []` when the query is missing,
non-string, or malformed. Modex now extracts only a non-empty string query and
maps those other shapes to an empty list, so malformed fragments are not echoed
or turned into an action. Valid split query fragments still match. Function
argument validation remains separate: the native reader unit continues to
reject malformed JSON arguments with `invalid_tool_call_arguments`.

Validation on Linux x86-64: `make build` passed; the focused
`test_provider_stream_01651_characterization.py` suite passed 25 tests; the
native `test_provider_chat_stream` checks passed; the direct loopback reset,
local-rewrite downstream RST, and provider-transport cancellation tests passed;
`check-product-dependencies.py` and `git diff --check` passed. The 64-search
case is a finite synthetic stress check, not a search-count or total-memory cap.
Other content-block/text ordering, unbounded total stream memory, other release
targets, and general Anthropic parity remain unverified.

Hosted Fast CI run [40792087830](https://github.com/christiandoxa/modex/actions/runs/40792087830)
failed before active stream tests because their setup required the historical
0.439.2 binary before CI acquired it. Active cases now validate only 0.165.1
and Modex, including both repeated-search shapes. Separate three-way regression
checks run after 0.439.2 acquisition. The CI routing test exercises active
setup with the historical path absent and checks that historical tests wait
for acquisition.
