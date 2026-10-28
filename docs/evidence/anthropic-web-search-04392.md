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

The production adapter rejects inputs outside the proven shape before its
upstream POST: string input, one `web_search_preview` tool, optional
`allowed_domains`, default token limit and no other request fields. It rejects
typed/multiple message history and mixed function/web tools rather than
coercing or dropping them. Oracle controls show that Prodex 0.439.2 coerces an
untyped `critic` role to `user`, sends mixed function/web tools, and combines
two same-role input messages into one message with both text parts; Modex
returns 502 with no upstream request for those shapes.
An exactly empty string input returns the release's HTTP 400 JSON error before
any upstream POST. Whitespace-only inputs, including NBSP and U+200B, remain
accepted by the tested release and Modex controls.

Buffered and streamed response handling also fails closed for unknown content,
citations and unsupported fields. Oracle controls show the release omits
citations from text output, maps a `thinking` block into reasoning output, and
completes after an image block without preserving its data. Modex returns 502
for the buffered cases and a terminal `response.failed` event for the stream
case. Native SSE success requires an ordered message start, one search block,
one result block, one empty-start text block, their stop events and a message
stop. A bare `[DONE]`, missing start/stop, nonempty initial text and unsupported
block order fail closed. Only the tested single web-search call/result and text
shape succeeds.

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

The 15-method characterization suite ran before the profile-help integration;
the ten stop cases were rerun against the combined production build afterward.

Fixtures use synthetic keys and local loopback providers. No paid provider traffic,
real credentials or account login were used. This does not qualify general
Anthropic Messages translation, arbitrary Responses input, tool-result/history
round trips, full metadata/citation behavior, HTTPS/TLS, DNS, proxies,
redirects, resource limits, backpressure or all error cases. The six release
targets, all 76 contracts, 456 platform obligations and blocked qualifications
remain unchanged; no parity status is promoted.
