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
`message_start` state. The compiled policy is in
`mojo/prodex_core/anthropic_stream_policy.mojo`. Modex now dispatches supported
content-block starts, deltas, stops, and `message_delta` without a
`message_start` sequencing guard, matching the reader's event policy.

The complete pinned-source path was traced in both releases. In
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_response_dispatch.rs`
and
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_response_anthropic_messages.rs`,
a successful native Anthropic event-stream response is routed to
`RuntimeAnthropicMessagesSseReader`.
`crates/prodex-app/src/runtime_launch/proxy_startup/provider_sse_reader.rs`
parses each `data:` JSON value and calls the state observer; the `event:` label
does not control dispatch. In
`crates/prodex-app/src/runtime_launch/proxy_startup/anthropic_messages_sse_reader.rs`,
the `MessageStart` arm converts its message ID, model, and accumulated
input/output usage into a chat chunk and sends it to
`RuntimeDeepSeekSseState::observe_chat_chunk`.

The native first-event lookahead is in
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_upstream.rs`.
It buffers bytes through the first complete event whose JSON `type` is not
`ping`; on timeout, EOF, or the 8 KiB lookahead limit, it keeps the bytes read
so far. `runtime_local_rewrite_finish_native_prefetch` stores that prefix on
the live response. Native Anthropic dispatch destructures the response without
passing `prefix` to `RuntimeAnthropicMessagesSseReader`, so the reader starts
after the consumed prefix. The `event:` SSE field is ignored by the shared
line parser; ping detection uses the JSON payload's `type`.

In `crates/prodex-app/src/runtime_launch/proxy_startup/deepseek_sse.rs`, that
state applies chunk metadata before deciding whether to emit
`response.created`. The ID helper in
`crates/prodex-provider-core/src/translators/deepseek/stream/shaping.rs` accepts
a streamed ID only while the current response ID has the generated
`resp_<provider>_` prefix; model and usage are updated whenever valid projected
values are present. The prefix check is implemented in
`mojo/prodex_core/deepseek_stream_policy.mojo`. The compiled Mojo Anthropic
policy classifies `message_start` by event type without sequence state, and
`deepseek_put_stream_chunk_metadata` in `mojo/prodex_core/deepseek.mojo`
selects `model`, `created`, `system_fingerprint`, and `usage`. At completion,
`crates/prodex-app/src/runtime_launch/proxy_startup/deepseek_sse/completion.rs`
assembles the response from the current ID, model, and usage. The inspected
reader and state implementations, ID policy, and relevant Mojo policy/projection
functions are identical between the two pinned snapshots.

The prefetch prefix explains the earlier source/process mismatch. With two
starts before content, the first start (`msg_a`) is consumed before dispatch;
the reader projects the second start (`msg_b`) as the first visible start.
With both starts after text, the first content-block start is consumed, the
text delta creates a response under its generated ID, and the later starts
replace that ID only while it still has the generated prefix. Model and usage
continue to update on every visible start.

## Process observations

Each case uses the production Super path, isolated synthetic state, loopback
provider traffic, and checksum-verified Linux binaries. The test compares
complete normalized event sequences against both releases, including response
IDs, model, usage, and error events. Both pinned releases agree on every listed
case.

The complete normalized event matrix now matches both release processes for
the canonical sequence, pre-start deltas, the standalone pre-start
`message_delta`, late and repeated starts, and generated-prefix ID replacement.
The native prefetch matrix also matches both releases for first start/text/error
events, retryable and non-retryable first errors without an available fallback,
JSON pings with conflicting `event:` labels, a fragmented first frame, timeout
after a partial frame, EOF inside a frame, and events at and across the 8 KiB
lookahead boundary. The label-mismatch cases confirm that `event:` does not
control dispatch.

The production Modex transport has no matching prefetch semaphore, so behavior
when Prodex skips lookahead because its prefetch slots are saturated is not
qualified. The tests cover Linux x86-64 only; the other five release targets
remain unqualified.

The regression test uses synthetic credentials only and makes no account login
or paid provider request.

## Validation

- `rtk make build` — pass with Mojo 1.2.0; existing unused-variable warnings remain.
- `python3 -m unittest test_provider_stream_cross_release_characterization.ProviderStreamCrossReleaseCharacterizationTests.test_anthropic_message_delta_before_message_start_is_ignored test_provider_stream_cross_release_characterization.ProviderStreamCrossReleaseCharacterizationTests.test_anthropic_out_of_order_stream_matrix_and_start_metadata test_provider_stream_cross_release_characterization.ProviderStreamCrossReleaseCharacterizationTests.test_anthropic_native_prefetch_consumes_exact_prefix test_provider_stream_01651_characterization.ProviderStream01651CharacterizationTests.test_anthropic_message_delta_stop_fields_match_release -v` — pass against both pinned releases.
- `python3 scripts/ci/check-product-dependencies.py` — pass; all 71 Mojo production files use standard-library or internal imports.
- `python3 scripts/ci/check-test-census.py` — pass; all 50 native test sources and 149 Python test modules have one suite owner.
- `git diff --check` — pass.

This qualifies only the tested out-of-order event sequence on Linux x86-64.
Other Anthropic stream orders and all six baseline release targets remain
unqualified.
