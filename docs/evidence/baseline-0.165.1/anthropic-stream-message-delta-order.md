# Anthropic stream message-delta ordering

References: Prodex 0.165.1 at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and official Prodex 0.439.2 at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`.
The Linux oracle SHA-256 values are
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` and
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

## Observed behavior

A synthetic Anthropic SSE body containing `message_delta` with
`stop_reason: "end_turn"` and `output_tokens: 5`, followed by `message_stop`
without a preceding `message_start`, reached the local provider fixture in all
three processes. Prodex 0.165.1 and 0.439.2 returned only one
`response.completed` event with empty output and no usage or finish metadata.
Modex returned an extra `response.created` event, finish metadata, and usage
with zero input tokens and five output tokens.

The baseline stream reader dispatches `message_delta` through the Anthropic
event policy and completes on `message_stop`. Modex already tracks whether a
message started to filter earlier content-block events, but had not applied
that guard to `message_delta`. It now ignores that event until
`message_start`; `message_stop` then completes the empty response as the
references do.

The regression test uses the production Super path, isolated synthetic state,
loopback provider traffic, and checksum-verified Linux binaries. It compares
the complete normalized event sequence and captured request against both
releases. The existing valid message-delta stop-reason matrix remains a
control. No real credentials, account login, or paid provider traffic is used.

## Validation

- `rtk make build` — pass with Mojo 1.2.0; existing unused-variable warnings remain.
- `python3 -m unittest test_provider_stream_cross_release_characterization.ProviderStreamCrossReleaseCharacterizationTests.test_anthropic_message_delta_before_message_start_is_ignored test_provider_stream_01651_characterization.ProviderStream01651CharacterizationTests.test_anthropic_message_delta_stop_fields_match_release -v` — both pass.
- `python3 scripts/ci/check-product-dependencies.py` — pass; all 71 Mojo production files use standard-library or internal imports.
- `python3 scripts/ci/check-test-census.py` — pass; all 50 native test sources and 148 Python test modules have one suite owner.
- `git diff --check` — pass.

This qualifies only the tested out-of-order event sequence on Linux x86-64.
Other Anthropic stream orders and all six baseline release targets remain
unqualified.
