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
