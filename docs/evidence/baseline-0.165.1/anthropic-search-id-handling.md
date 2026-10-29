# Anthropic web-search IDs in streamed and buffered responses

References: Prodex 0.165.1 at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and official Prodex 0.439.2 at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`.
The Linux oracle hashes are `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
and `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

## Source trace and behavior

Both pinned `anthropic_messages_sse_reader` implementations default an absent
or non-string `server_tool_use.id` to `web_search_<index>`. The streamed index
defaults to zero when absent or non-numeric. String IDs, including the empty
string, are retained. Results are selected by string `tool_use_id`; a missing,
non-string, or unmatched ID is ignored before its source content is parsed.
Duplicate IDs select the earliest matching index, including a completed search
when a result ID is repeated; duplicate block indices replace the active search
at that index.

Buffered responses use a different rule: `id` and `tool_use_id` must be
strings, but an empty string is valid. The 0.439.2
`anthropic/messages/web_search.rs` passes a string ID to the response kernel
without requiring a non-empty value. The earlier Mojo response kernel likewise
classifies the field by string type.

## Production comparison

Before the fix, streamed missing, null, numeric, or empty search IDs failed in
Modex, while the pinned releases completed the search. Modex also failed
unmatched streamed results that both releases ignore. In buffered mode, Modex
rejected an empty string ID even though both releases accepted it. Buffered
missing, null, and numeric IDs return 502 in all three processes.

Modex now applies the release’s streamed fallback only to absent or non-string
IDs, retains empty strings, and ignores unmatched or non-string results before
source parsing. Matched result content remains validated. Buffered validation
continues to require string IDs while preserving empty strings. Existing
buffered response-size and content-block limits remain in force.

`test_search_id_fallback_and_result_matching_match_both_releases` compares
complete normalized event streams and captured provider requests across
checksum-verified 0.165.1, 0.439.2, and Modex processes. It covers missing,
null, numeric, and empty search IDs; missing block indices; interleaved results
at non-monotonic indices; duplicate IDs; duplicate indices; a collision
between a generated and explicit ID; and missing, null, numeric, and unknown
result IDs with malformed unmatched content. `test_buffered_search_ids_require_strings_but_preserve_empty_strings`
checks buffered status and output for valid, empty, missing, null, and numeric
IDs across the same three processes.

The fixtures use synthetic provider keys, isolated temporary homes and storage,
and loopback upstreams. They make no account login or paid provider request.

## Validation

- `rtk make build` — pass with Mojo 1.2.0; existing unused-variable warnings remain.
- `python3 -m unittest test_anthropic_stream_optional_metadata_shared` — 25 tests pass against both pinned releases and the production Modex binary.
- `python3 -m unittest test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_buffered_search_ids_require_strings_but_preserve_empty_strings test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_buffered_content_block_limit_for_function_only_replies test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_buffered_content_block_limit_for_mixed_replies` — pass against both pinned releases and production Modex.
- `python3 -m unittest test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_buffered_content_block_limit_for_function_only_replies test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_buffered_content_block_limit_for_mixed_replies test_deepseek_key_rotation_01651_04392.DeepSeekKeyRotationTests.test_native_anthropic_does_not_replay_after_first_event_commit` — pass.
- `python3 scripts/ci/check-product-dependencies.py` — pass; 71 Mojo production files use only standard-library or internal imports.
- `python3 scripts/ci/check-test-census.py` — pass; both modified modules already have suite ownership in `scripts/ci/run-fast.sh` and `scripts/ci/run-full.sh`.
- `git diff --check` — pass.

This qualifies selected Linux x86-64 provider behavior only. It does not claim
general Anthropic or provider parity, and all six baseline release targets
remain in the parity denominator.
