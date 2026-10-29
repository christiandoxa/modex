# Buffered Anthropic tool-use observations

The production Super path was compared with the checksum-pinned Linux 0.165.1
executable using synthetic Codex and loopback peers. Buffered Anthropic
responses with function tool calls now preserve tool order and adjacent text
parts, including mixed text and multiple calls. The tested input variants
include missing, scalar and array tool inputs and namespaced names. Missing,
null and numeric stop reasons retain the observed metadata behavior.

A synthetic two-turn comparison also checks the second upstream request: the
saved assistant tool call and its function result are translated into Anthropic
history. Additional production comparisons cover unmatched call IDs, mixed
text/tool history and representative array outputs. Historical 0.439.2
Anthropic checks are retained separately. These
cases do not qualify mixed web-search/function blocks, arbitrary malformed
input, real providers, concurrency or any non-Linux release target.

Untyped `input` items with `role: "tool"` use `call_prodex` when
`tool_call_id` is missing, null, numeric, empty or whitespace-only. Their
results keep their input order and precede ordinary text in the grouped user
message; surrounding result content whitespace is preserved. A typed
`{"type":"message","role":"tool"}` remains rejected before provider I/O.
When a function output follows a returned tool call, its ID remains attached
to the grouped result and multiple output strings are joined in order.
`test_untyped_tool_message_fallback_order_matches_releases` compares buffered
requests and responses plus complete normalized stream events across the
checksum-pinned 0.165.1 and 0.439.2 Linux binaries and Modex. The
`test_function_output_id_is_retained_with_grouped_tool_results` compares the
two-turn request bodies and cleanup across all three processes; the existing
function-output/history controls compare 0.165.1 and Modex. These cases qualify
only the listed input and grouped-history shapes.

On Linux x86-64, the two new methods and three existing function-output/history
controls passed. The 71-file production import audit, test census (50 native
sources and 135 Python modules), and `git diff --check` passed. `make build` had
passed after the source change; it was not rerun because subsequent changes
were tests and evidence only.

## Buffered reasoning blocks

The pinned 0.165.1 source classifies an Anthropic `thinking` block as a
Responses `reasoning` item when its `thinking` field is a string. The source
planner in `mojo/prodex_core/rich_abi.mojo` only marks string-valued fields;
`mojo/prodex_core/anthropic_request.mojo` writes the string under
`summary_text`. Missing and non-string values produce no reasoning item, but
still split adjacent text blocks. Other thinking-block fields, including a
signature, are ignored. The oracle is
`~/.cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu`, SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.

Modex now applies that projection in its production buffered Messages adapter.
`test_buffered_thinking_blocks_match_release` compares full provider request
bodies and normalized responses from the checksum-verified 0.165.1 and 0.439.2
Linux binaries with Modex. The active 0.439.2 oracle is
`~/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu`, SHA-256
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.
Synthetic cases cover UTF-8 and empty reasoning, missing/non-string values,
repeated reasoning interleaved with two searches and two function calls, and a
no-reasoning control. A malformed function call without a name still fails in
all three processes. Each run uses isolated HOME, state, shared, work,
config/cache/data directories, a synthetic Codex peer, a synthetic API key,
and a loopback provider.

Validation on Linux x86-64: `rtk make build` passed; the full
`python3 scripts/ci/run-unittest.py test_anthropic_mixed_tools_01651.py` run
passed 23 tests, including the expanded reasoning matrix, malformed-call guard,
and real continuation boundary. The native `test_provider_chat_buffered` check
and 71-file production import audit passed, as did `git diff --check`. The
malformed-call control remains fail-closed, and the no-reasoning control
matches both releases. This qualifies the tested buffered response shapes
only. A real two-turn process probe with a reasoning-plus-function response
returns 503 `bound_continuation_unavailable` before a second provider POST in
both releases and Modex, so follow-up history retention is not qualified.
`test_reasoning_response_continuation_matches_unavailable_boundary` keeps
that boundary reproducible. Anthropic citations, other content blocks,
streaming metadata, other release targets, and general provider parity remain
open.

A synthetic buffered response with an Anthropic `image` block in the tested
web-search shape returns 502 in both Prodex 0.165.1 and Modex after one local
upstream response; neither client response exposes the image data. Responses
`input_image` requests are also rejected before the provider POST by both
processes. The streaming image block has a different release behavior and is
covered in `anthropic-stream.md`; this buffered rejection does not imply that
image request or response support is implemented.

## Buffered response envelope fields and usage

The frozen 0.439.2 response translator requires a `content` array, then passes
the full provider object to the Anthropic response-envelope kernel. The kernel
reads `id`, `model`, `usage.input_tokens`, `usage.output_tokens`, optional
`usage.server_tool_use.web_search_requests`, and `stop_reason`; it ignores
unknown envelope and usage fields. Missing or non-string IDs and models become
`resp_anthropic` and `unknown`. A missing or non-object usage value is omitted;
an object with absent or non-unsigned token counts produces zero counts. A
valid web-search request count maps to
`tool_usage.web_search.num_requests`.

`tests/test_anthropic_mixed_tools_01651.py::test_buffered_envelope_extensions_and_usage_normalization_match_releases`
compares the production Super path against checksum-pinned 0.165.1 and 0.439.2
Linux processes. Its cases cover extra top-level fields (including
`stop_sequence`, `context_management`, and a conflicting top-level
`tool_usage`), extra cached-token usage fields, nested web-search counts,
invalid ID/model/token field types, missing and non-object usage, and a missing
stop reason. A non-array `content` field still returns the release's 502; the
existing exact/over-limit content-block tests retain the 65,536-block bound.
The tests use synthetic responses, isolated state, and loopback provider
traffic.

Frozen-source trace: Prodex 0.439.2 commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`,
`crates/prodex-provider-core/src/translators/anthropic/messages.rs:141-150`,
`crates/prodex-provider-core/src/translators/anthropic/messages/response.rs:72-103`,
and `mojo/prodex_core/anthropic_request.mojo:2088-2187`. The pinned 0.165.1
comparison is process evidence only. Oracle SHA-256 values are
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` and
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

Validation on Linux x86-64: `make build` passed; the full
`python3 scripts/ci/run-unittest.py test_anthropic_mixed_tools_01651.py` suite
passed all 50 tests, including the new envelope comparison and the existing
65,536/65,537 content-block boundary. The focused native
`test_provider_chat_buffered` unit, 71-file production import audit, test
census (50 native test sources and 136 Python modules), and `git diff --check`
also passed.

This covers only the tested envelope fields on Linux x86-64. Existing content
block validation, the response-size limit, unsupported response blocks,
continuation behavior, transport security, other release targets, and general
Anthropic parity remain open.

## Multiple buffered web-search blocks

The historical 0.165.1 source at commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and the frozen 0.439.2 source at
commit `72b77478a5198fc5da6b4d2253137f9cdbf43be9` use
`crates/prodex-provider-core/src/translators/anthropic/messages/response.rs:15-103`
to classify and plan every response block. In both releases,
`mojo/prodex_core/rich_abi.mojo:224-350` walks the blocks in input order and
plans text, thinking, server-tool-use, and search-result entries; it does not
require one search/result/text triple. The output kernel in
`mojo/prodex_core/anthropic_request.mojo:1625-1774` matches results by
`tool_use_id`, omits result entries after attachment, preserves unmatched
search calls, and omits orphan results. This source trace explains why
multiple searches and interleaved blocks reach translation, while the process
comparison below establishes the observed output.

Modex buffered validation now validates each text, web-search use, search
result, and thinking block without imposing a single-search shape. The separate
function-tool branch remains unchanged, and unsupported blocks still fail.
`tests/test_anthropic_mixed_tools_01651.py::test_buffered_search_only_sequences_match_both_releases`
compares normalized requests and responses through the production Super path
against checksum-pinned 0.165.1, 0.439.2, and Modex processes. It covers two
search/result pairs without text, plus interleaved text and thinking, an orphan
result, and a pending search. Both releases return HTTP 200 for these cases;
the pre-fix Modex build returned 502 for the multi-pair case.

Validation on Linux x86-64: `rtk make build` passed; the focused
`test_anthropic_mixed_tools_01651.py` run passed 63 tests; native
`test_provider_chat_buffered`, the 71-file production import audit, the test
census (50 native test sources and 140 Python modules), and `git diff --check`
passed. Tests used synthetic provider responses and isolated process fixtures.
This qualifies only the selected buffered shapes on Linux x86-64. Streaming,
other response shapes, all six release targets, and general provider parity
remain open.
