# Anthropic stream event ordering and start metadata

References: Prodex 0.165.1 at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and official Prodex 0.439.2 at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`.
The Linux oracle SHA-256 values are
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` and
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

## Source trace

In both pinned source snapshots,
`crates/prodex-app/src/runtime_launch/proxy_startup/anthropic_messages_sse_reader.rs`
routes `DeltaText` and `DeltaArguments` through
`inner.observe_chat_chunk`. The compiled
`crates/prodex-mojo-core/src/anthropic_stream_policy.rs` dispatches
`content_block_delta` by event and delta type; its facts do not include a
`message_start` state. Modex had added a `message_started` gate around all
content-block deltas, which suppressed validly parsed delta events in the
synthetic order probes. That gate is removed. The separate content-block-start
guard remains.

The baseline `MessageStart` arm constructs a chat chunk with the message ID,
model, and usage, then passes it to `observe_chat_chunk`; the downstream
`apply_chunk_metadata` updates response ID, model, and usage. Its source does
not describe the order-dependent admission seen below. The mismatch between
that source path and the verified process observations remains unresolved, so
Modex does not implement a sequence or prefix heuristic for message-start
metadata.

## Process observations

Each case uses the production Super path, isolated synthetic state, loopback
provider traffic, and checksum-verified Linux binaries. The test compares
complete normalized event sequences against both releases, including response
IDs, model, usage, and error events. Both pinned releases agree on every listed
case.

Matching cases now include the canonical start/text/delta sequence, a text
delta before any message start followed by `message_delta`, a function-argument
delta before start that fails for a missing function name, and a lone
`message_delta` plus `message_stop` before start. The last case returns only an
empty `response.completed`; Modex previously emitted an extra
`response.created` with finish metadata and usage. Modex now ignores that
standalone delta while still accepting `message_delta` after earlier content
has created a response.

Known differences remain for streams where a start follows earlier content or
is repeated. Both releases apply selected late/repeated start metadata where a
single canonical start does not: examples include a late start after text, two
starts before text, two starts after text, an empty text-block start before a
message start, and a custom ID beginning `resp_deepseek_` followed by another
start. In those cases Modex keeps the generated response ID, omits the release
model field, and retains zero input tokens. The matrix records the exact release
ID/model/usage values and compares the entire normalized Modex event list so
these observations stay visible as gaps.

The regression test uses synthetic credentials only and makes no account login
or paid provider request.

## Validation

- `rtk make build` — pass with Mojo 1.2.0; existing unused-variable warnings remain.
- `python3 -m unittest test_provider_stream_cross_release_characterization.ProviderStreamCrossReleaseCharacterizationTests.test_anthropic_message_delta_before_message_start_is_ignored test_provider_stream_cross_release_characterization.ProviderStreamCrossReleaseCharacterizationTests.test_anthropic_out_of_order_stream_matrix_and_start_metadata_gap test_provider_stream_01651_characterization.ProviderStream01651CharacterizationTests.test_anthropic_message_delta_stop_fields_match_release -v` — all three pass, including explicit assertions for the retained metadata gaps.
- `python3 scripts/ci/check-product-dependencies.py` — pass; all 71 Mojo production files use standard-library or internal imports.
- `python3 scripts/ci/check-test-census.py` — pass; all 50 native test sources and 148 Python test modules have one suite owner.
- `git diff --check` — pass.

This qualifies only the tested out-of-order event sequence on Linux x86-64.
Other Anthropic stream orders and all six baseline release targets remain
unqualified.
