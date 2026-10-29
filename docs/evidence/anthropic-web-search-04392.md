# Anthropic web-search slice against Prodex 0.439.2

Frozen reference: official Prodex 0.439.2 source commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`; Linux oracle SHA-256
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

The production Super relay now routes selected Responses requests with one
`web_search_preview` tool to Anthropic Messages. Synthetic process comparisons
cover `/v1`, `/beta`, `/anthropic`, `/anthropic/v1`, preserved path prefixes,
dot-segment and literal-backslash normalization (including suffix detection
before normalization), generated Messages request JSON, `x-api-key` and
`anthropic-version` handling, buffered text/search output and token usage,
search sources, and normalized full buffered and SSE event payloads. The
buffered comparison checks all fields, including Anthropic stop-reason
metadata and empty text and response ID; only timestamps are normalized. The
stream comparison normalizes generated response/message IDs and timestamps
only; it also covers
output ordering, usage, finish-reason metadata and omitted model fields.
Valid Anthropic `ping` heartbeats are ignored, matching the release. Unknown
event types fail closed. Anthropic stream error events preserve the release's
error code and message.
Incoming Anthropic auth headers are replaced only on the Messages route;
ordinary DeepSeek and raw passthrough keep forwarding those headers as before.

The production adapter accepts string input and selected arrays of messages,
with user, assistant, system and developer roles and web-search tools.
Adjacent messages with the same conversation
role are combined; system and developer text becomes the Messages `system`
field. Synthetic release comparisons cover Unicode and role transitions.
Selected message content arrays are flattened to text by the existing shared
Responses mapper, including annotated input text, text parts separated by a
newline, and non-text scalar array entries ignored by the release. Selected
object content is serialized as text. The releases and Modex discard the
tested message metadata and map untyped unknown or non-string roles to user.
Typed unsupported roles and typed image parts reject before dispatch. Untyped
image parts are omitted by both releases and Modex; when no text remains the
request returns 400, otherwise only text reaches the synthetic upstream. An
untyped image object used as the entire content is instead serialized as text
and forwarded, matching both releases; it is not image decoding support.
The pinned `deepseek_bridge/input_items.rs` applies the same shared mapper
before the Anthropic request translation. Blank array entries are dropped by
the shared Responses-to-chat mapper. Empty, whitespace-only and system-only
arrays now return the release's HTTP 400 JSON error when no conversation
message remains; blank entries alongside nonblank messages are omitted. The
production process controls compare these cases with checksum-pinned 0.165.1
and 0.439.2, including Unicode whitespace, blank role transitions, and blank
system/developer messages alongside a user message. The release's input
reconstruction omits blank text items, and its Anthropic chat validator rejects
requests with no translated conversation blocks. History and other input
shapes remain separately qualified. Focused checks passed after `rtk make
build`: both array comparison methods, the existing simple-array and rich-input
controls, the four-mode matrix, and streamed requests with empty or mixed
blank/nonblank arrays. A two-turn control confirms a blank continuation still
hits the same bound-provider-unavailable response without a second POST.
The native request-message test, 71-file product import audit, and test census
also passed. These are Linux x86-64 synthetic process tests, not full parity.
The full five-method message-array suite passed against 0.439.2; separate
0.165.1 controls passed for the expanded text/metadata shapes and web-search
mode routing. A streamed annotated-text request also matched both releases.
An exactly empty string input returns the release's HTTP 400 JSON error before
any upstream POST. Whitespace-only inputs, including NBSP and U+200B, remain
accepted by the tested release and Modex controls.

Buffered response handling now omits citations and other tested text-block
metadata like both releases, while requiring string text. The releases map a
`thinking` block into reasoning output; Modex matches the tested thinking
case. The releases ignore a
streamed image block without preserving its data. Modex now matches the
complete normalized stream for that image case. A buffered image block in the
tested search response shape still returns 502 after one synthetic upstream
response in both the release and Modex; Responses `input_image` requests are
rejected before provider dispatch by both. Native SSE success requires an
ordered message start, one search block,
one result block, one empty-start text block, their stop events and a message
stop for the tested search-result shape. A separate text-only or empty message
may now complete without a web-search block. Eight such event sequences match
the release after normalizing generated IDs and timestamps, with or without
`message_delta`. A bare `[DONE]`, missing start/stop, nonempty initial text and
unsupported block order fail closed. The release drops a nonempty initial text
block; Modex rejects that tested shape instead.

Buffered Anthropic `end_turn` responses now match both pinned release
processes for empty content, empty/single/multiple text blocks, and text blocks
separated by `thinking`. Missing or non-string text and unsupported content
blocks still return the same 502 response across the two releases and Modex.
An orphan `web_search_tool_result`, either after text or as the only content
block, is now ignored like both releases. The source trace, exact synthetic
responses, before/after process comparison, and remaining limits are recorded in
`docs/evidence/baseline-0.165.1/anthropic-orphan-result.md`.

Two additional real-process image controls match the full normalized release
event sequence: a nonempty indexed image source with a same-index `image_delta`
and stop between text deltas, and an image start/delta/stop sequence with the
index omitted. Both preserve the surrounding text order and discard the image
source and delta marker. Other image delta types and malformed block sequences
remain unverified.

Full normalized release comparisons now match `stop_sequence`, null and
unknown string reasons, `tool_use`, `max_tokens`, a non-null stop sequence with
`end_turn`, and a missing `message_delta`. Missing or non-string stop reasons
and non-string stop sequences remain explicit, unapproved fail-closed differences: the release
completes while Modex emits `response.failed`.

Checks run in an isolated workspace copy:

- `make check-toolchain` — pass.
- `make build-internal` — pass.
- `python3 -m unittest test_provider_tools_04392_characterization` — 15 tests pass against the pinned release and production Modex CLI, including path, empty-input, heartbeat and ten stop variants.
- `python3 scripts/ci/run-unittest.py test_anthropic_buffered_payload_04392.py` — full buffered comparisons pass for normal, empty-text and empty-ID cases.
- `python3 -m unittest test_local_rewrite` — 19 tests pass after rebuilding the isolated test-only relay driver.
- `make unit-build UNIT_BUILD_PROGRAMS='test_gateway_cli test_provider_chat_reader test_provider_chat_stream test_provider_deepseek_transport'` and execute all four programs — pass, including incomplete native stream and route-scoped header checks.
- `make unit-build UNIT_BUILD_PROGRAMS='local_rewrite_driver'` — pass.
- `python3 scripts/ci/check-product-dependencies.py` — pass; production imports use only Mojo std/internal modules.

The combined production build subsequently passed all 20 methods in
`test_anthropic_message_arrays_04392.py` and
`test_provider_tools_04392_characterization.py` without skips.
The later text-only stream change passed
`python3 scripts/ci/run-unittest.py test_anthropic_text_stream_04392.py`,
three existing SSE characterization methods and the rebuilt native reader and
stream programs.

The streamed image update passed `make build` and a combined 48-test run of the
0.165.1 and 0.439.2 provider characterization modules. The added indexed and
missing-index image-sequence methods then passed against both release
processes, including nonempty source data, a matching `image_delta` and stop,
and text before and after. The 71-file production import audit passed.

The focused two-method buffered text-only process run passed against Prodex
0.165.1, Prodex 0.439.2 and Modex. `make unit-build
UNIT_BUILD_PROGRAMS=test_provider_chat_buffered` and the rebuilt
`build/tests/test_provider_chat_buffered` program also passed.

Fixtures use synthetic keys and local loopback providers. No paid provider traffic,
real credentials or account login were used. This does not qualify general
Anthropic Messages translation, arbitrary Responses input, tool-result/history
round trips, full metadata/citation behavior, HTTPS/TLS, DNS, proxies,
redirects, resource limits, backpressure or all error cases. The six release
targets, all 76 contracts, 456 platform obligations and blocked qualifications
remain unchanged; no parity status is promoted.
