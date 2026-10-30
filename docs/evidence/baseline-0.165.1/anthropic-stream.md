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

The release also ignores an Anthropic `image` content block and does not expose
its source data in Responses output. Modex now matches the complete normalized
0.165.1 stream for the synthetic image case; the historical 0.439.2 comparison
matches too. A request containing Responses `input_image` remains rejected
before provider dispatch by both processes, matching the pinned text-only
request adapter. Image blocks in buffered responses remain separately
unsupported and are covered by the buffered evidence.

Additional real-process cases put a nonempty image source, same-index
`image_delta`, and matching stop between text deltas. Both indexed and
missing-index image starts match 0.165.1 and 0.439.2: the text deltas retain
their order, and neither the source nor delta marker reaches Responses output.
These cases qualify the tested image event shapes only; other image delta
types and malformed block sequences remain unverified.

The production parser also maps a tested Anthropic `tool_use` block and split
`input_json_delta` fragments into Responses function-call events. A synthetic
loopback comparison matches the complete 0.165.1 event sequence, upstream
request and cleanup. Additional controls cover duplicate index, missing stop,
orphan and mismatched indices, duplicate/reopened stops, and deltas after stop.
The nine index/stop controls now match the complete normalized event stream
against both pinned releases. The orphan and mismatched-index delta controls
generate fallback UUIDv7 call IDs; the test validates those IDs and normalizes
only those values.
No mismatch was reproduced in those stop cases. This is not general
function-tool or event-order parity.

Both pinned source readers pass `tool_use` names, including absent or non-string
values, into common tool-call accumulation. That path emits an added item with
the fallback name `tool_call`, forwards argument deltas, and reports a missing
or blank name as `invalid_tool_call_arguments` at message completion. Modex
previously rejected these blocks immediately as `provider_stream_error`; it now
preserves that deferred validation behavior. Real-process comparisons cover a
missing name, null, numeric, empty, and whitespace-only names, plus a valid
`lookup` control. The complete normalized event sequence, upstream request and
cleanup match Prodex 0.165.1 and 0.439.2. Source traces are the pinned
`anthropic_messages_sse_reader.rs` and `deepseek_sse/tool_calls.rs` at 0.165.1
commit `10ae15b5d1806302b60f051e4e6fec788044f4c2` and 0.439.2 commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. These synthetic cases do not
establish general Anthropic tool or provider parity.

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
validation. Query fragments before, during, and after a result block match the
release; a new search can also start while an earlier result block remains open.

For search input, the release emits `queries: []` when the query is missing,
non-string, or malformed. Modex now extracts only a non-empty string query and
maps those other shapes to an empty list, so malformed fragments are not echoed
or turned into an action. Valid split query fragments still match. Function
argument validation remains separate: the native reader unit continues to
reject malformed JSON arguments with `invalid_tool_call_arguments`.

Validation on Linux x86-64: `make build` passed; the focused
`test_provider_stream_01651_characterization.py` suite passed 26 tests; the
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

This image update was validated on Linux x86-64 with `make build` and the two
focused provider characterization modules (48 tests). The two added indexed and
missing-index image sequence methods also passed against both real oracles. The
71-file production import audit passed. Other release targets remain
unverified.

## Reused content-block indices follow the frozen stop policy

The production reader now treats `content_block_stop` like both pinned
releases: it only clears an index currently ignored because a
`web_search_tool_result` block started there. Stops for text, tool, server
search, image, and unknown blocks do not change their state. Search input
deltas remain routed by active search index after a stop; tool argument and
text deltas also continue after stops. A result stop still clears the ignored
index, including when an image or later text reuses it.

Real Super process comparisons against 0.165.1 and 0.439.2 cover text, tool,
search, and result index reuse by image blocks; repeated image and result
starts; duplicate search starts at one index; search results before a search
stop; deltas after non-result stops; deltas without matching starts; unknown
block starts; missing delta types; and post-failure continuation. The three-way
shared suite asserts identical request bodies and normalized output events
from both releases and Modex. Synthetic image source and delta markers remain
absent from every downstream response. A native reader regression covers the
same text/image index collision.

Validation on Linux x86-64: `make build`, native `test_provider_chat_stream`
and `test_provider_chat_reader`, and 66 tests across
`test_provider_stream_01651_characterization.py`,
`test_provider_tools_04392_characterization.py`,
`test_anthropic_stream_optional_metadata_shared.py`, and
`test_anthropic_text_stream_04392.py` passed. These focused checks do not
qualify other release targets or general Anthropic parity. The shared suite's
`test_invalid_utf8_after_response_failed_records_release_open_body` now matches
both pinned releases: after a closed-result delta emits `response.failed`, an
invalid UTF-8 byte in an ignored comment line leaves all three downstream
chunked bodies open until the five-second synthetic client timeout closes its
socket. Additional real-process probes verify that ordinary upstream EOF after
the failure closes the body, a 100 ms upstream idle timeout leaves it open
until client disconnect, and an upstream reset after the failure has the same
open-body result. A request `SHUT_WR` control produces the same incomplete body
in both releases and Modex. Parent-EOF cancellation has separate active and
historical held-open process tests:
`test_parent_eof_cancels_held_failed_stream_with_truncated_pipeline_body`
in this historical module compares 0.165.1/0.439.2 with Modex; the active
counterpart in `test_anthropic_parent_shutdown_01660.py` compares 0.166.0 with
Modex. Both stop upstream after `response.failed`, send a pipeline head plus
1,024 bytes of a declared 1 MiB body, and keep the client write side open.
They require a live parent before SIGTERM, exit on SIGTERM, close upstream
before the 30-second fixture timeout, and leave no direct children after two
seconds. A held-open truncated-head control covers the incomplete-head case.
The earlier serial Modex parent exited but left its relay
and synthetic Codex children alive; the pooled cancellation path now closes
the open stream despite pending pipeline bytes. A complete 1 MiB pipeline
control can finish naturally after the queued 502, so it checks completion
without requiring SIGTERM. A forced four-second observation delay once left a
direct child of the active 0.166.0 launcher alive at the two-second check;
five later active-oracle repetitions with the same delay had no survivor. Its
role was not captured, and the child assertion is unchanged. The original
invalid-UTF-8-tail plus parent-EOF combination is retained as a historical
characterization in
`test_parent_eof_with_invalid_utf8_truncated_pipeline_is_characterized`; its
active 0.166.0 counterpart is in
`test_anthropic_parent_shutdown_01660.AnthropicParentShutdown01660Tests.test_parent_eof_with_invalid_utf8_truncated_pipeline_is_characterized`.
Both distinguish an actual SIGTERM exit from a clean status-0 return before
SIGTERM; the latter is not counted as cancellation. The historical case
compares Modex with 0.165.1/0.439.2; the active case compares Modex with
0.166.0. The old full-suite snapshot observed Modex return 0 before SIGTERM,
while an isolated follow-up sent SIGTERM to all four processes. See
`docs/evidence/baseline-0.166.0/anthropic-parent-eof-cancellation.md`. The
normal client-close probe also exercises launcher cleanup, and valid
continuation through `message_stop` closes normally. Clients that retain their
socket after a read timeout and other invalid UTF-8 framing positions were not
tested. Broader malformed shapes and aggregate stream-state limits remain
unverified.

The first four-module run reported four failures and one test-helper error.
Three failures came from terminating a stream after `response.failed` instead
of continuing through `message_stop`; the fourth exposed content blocks being
translated before `message_start`. The helper error was a stale normalization
reference. Those causes were corrected, and the final 66-test rerun passed.
