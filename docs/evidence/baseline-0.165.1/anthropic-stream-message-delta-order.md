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
`mojo/prodex_core/anthropic_stream_policy.mojo`. Modex had added a
`message_started` gate around all content-block deltas, which suppressed
validly parsed delta events in the synthetic order probes. That gate is
removed. The separate content-block-start guard remains.

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

This source predicts ID/model/usage `msg_a`/`model-msg_b`/`9 input + 5 output
tokens for the case with two starts before content: the first start
replaces the generated ID, so the second start cannot replace it, while model
and usage still take the second values.
The verified release processes instead return `msg_b` with the second
start's model and usage. For two starts after content, the release returns
`msg_a` with the second start's model and usage, which does agree with the
source's one-time ID replacement. Thus the pinned source gives no complete
rule for the binary's order-dependent ID behavior. The mismatch between source
and process evidence remains unresolved. Keep the six metadata gaps open; the
source does not justify changing message-start metadata behavior.

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
is repeated. The exact ID contradiction is reproducible with the matrix case
`duplicate starts before content` in
`tests/test_provider_stream_cross_release_characterization.py`:
`[start("msg_a", 3), start("msg_b", 9), text_block, text_delta,
message_delta(output_tokens=5), message_stop]`: both release processes return
`msg_b`, `model-msg_b`, and usage `{input_tokens: 9, output_tokens: 5,
total_tokens: 14}`. Moving both starts after the text delta instead returns
`msg_a` while retaining the second start's model and usage. Other recorded
cases include a late start after text, a late start after `message_delta`, an
empty text-block start before a message start, and a custom ID beginning
`resp_deepseek_` followed by another start. Modex currently keeps its generated
response ID and omits late/repeated-start model and input-usage metadata; the
matrix compares complete normalized event sequences so these differences stay
visible as gaps.

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
