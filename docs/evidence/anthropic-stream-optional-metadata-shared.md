# Anthropic stream optional metadata across Prodex releases

The official 0.165.1 and 0.439.2 releases both tolerate absent or wrongly typed optional fields in Anthropic `message_start` metadata and usage, ignore unusable `message_delta.usage` counters, and ignore non-string text-delta payloads. Before this change, Modex failed those streams with `response.failed`.

The two pinned source commits are Prodex 0.165.1 `10ae15b5d1806302b60f051e4e6fec788044f4c2` and Prodex 0.439.2 `72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Their `crates/prodex-app/src/runtime_launch/proxy_startup/anthropic_messages_sse_reader.rs` implementations are identical. In `observe_value`, `MessageStart` reads `message.id` and `message.model` as optional JSON pointers and calls `observe_usage` with optional usage (lines 122–129); `DeltaText` passes the raw optional `delta.text` value onward (156–161); `MessageDelta` uses the same tolerant usage reader (189–205). `observe_usage` updates counters only when fields convert with `Value::as_u64()` (381–395). The release's own stream-policy fixture includes `message_start` with only an `id` and `message_delta` without usage (443–454).

The Modex change is limited to these traced cases in `src/modex/provider_chat_stream.mojo`. Event ordering, JSON parsing, event-size limits, content-block indexes, and tool/search structure checks remain in place. Extra event-root fields are tolerated for `text_delta` and `input_json_delta`; future delta types retain strict validation.

`tests/test_anthropic_stream_optional_metadata_shared.py` exercises 25 synthetic stream variants through the real `modex super` launch path and the frozen release binaries. It includes one repeated-search stream with an extra event-root field on each `input_json_delta`. Each run uses a temporary home/config, a fake Codex client, loopback upstream traffic, and `synthetic-provider-key`; no credentials or external provider traffic are used. Both oracle binaries are checked against their pinned SHA-256 values:

- Prodex 0.165.1: `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
- Prodex 0.439.2: `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`

For all 25 cases, each release and Modex posts the same request to `/anthropic/v1/messages`, returns HTTP 200, and produces the same normalized response events. The comparison normalizes generated response IDs and timestamps; request bodies and all other response fields are compared exactly. Before the fix, the missing/wrong-type start metadata, usage, and text-delta cases failed in Modex while both releases completed. The new input-JSON root-field probe exercises the real search stream, including its completed output items.

The suite also checks Modex rejects a future delta type, with and without an extra event-root field. Validation passed with `make build`, the shared, repeated-search, and 0.165.1 historical Python stream suites (31 tests), and native `test_provider_chat_stream` and `test_provider_chat_reader` Mojo checks.

Reproduce with `make build` followed by `python3 scripts/ci/run-unittest.py test_anthropic_stream_optional_metadata_shared.py`. Fast and Full CI run this check in the existing cross-release lane after acquiring both pinned oracles.

Known gap: both pinned releases ignore a `citation_delta` event carrying an extra event-root field, while Modex rejects it as unsupported. Citation-delta semantics remain unsupported, and this slice keeps the parser fail-closed for that event type. Supporting it needs complete citation-field tracing and tests. This evidence otherwise covers only the listed message-start, usage, text-delta, and input-JSON event-root shapes; it does not establish parity for other malformed Anthropic event fields, other providers, or the six release targets. The broader inventory remains incomplete.
