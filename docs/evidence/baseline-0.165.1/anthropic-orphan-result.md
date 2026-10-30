# Orphan Anthropic search results against 0.165.1 and 0.439.2

Frozen references: Prodex 0.165.1 source commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and Prodex 0.439.2 source commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Their Linux oracle SHA-256 values
are `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51` and
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`,
respectively.

Both release sources classify `web_search_tool_result` as its own response
block in `crates/prodex-provider-core/src/translators/anthropic/messages/response.rs`
and plan output from the sequence of classified blocks in
`crates/prodex-mojo-core/src/rich/anthropic_messages.rs`. The planner does not
require a result block to match an earlier search block. Real-process probes
confirm that a structurally valid orphan result is ignored while adjacent text
is returned.

The test runs the production Super provider path with a synthetic
`web_search_preview` request and local Anthropic Messages fixture. The fixture
returns either one text block followed by `web_search_tool_result`, or only the
orphan result, with `tool_use_id: "missing_search"`. Both pinned releases
return 200, preserving the text response in the first case and producing an
empty output array in the second. Modex previously returned 502 after the same
single upstream POST. It now matches the complete normalized payload,
including usage and stop metadata; only generated `created_at` is normalized.
The synthetic credential is not printed and no external request or login
occurs.

The production validator now admits text/thinking content interspersed with
well-formed orphan result blocks, or a response containing only orphan results,
when there is no unsupported block or search call. The response projection
attaches source data only when a string result ID matches a search ID; it
ignores missing, non-string, and unmatched IDs. Existing search-result
association, tool-use validation, and fail-closed behavior for unsupported
blocks remain in place. These are selected buffered provider cases, not general
Anthropic or release parity.

## Missing and non-string result identifiers

The 0.165.1 source snapshot at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and the frozen 0.439.2 source at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9` both skip a
`web_search_tool_result` when `tool_use_id` is absent or not a string. Their
`mojo/prodex_core/anthropic_request.mojo:1693-1697` response-output kernels
continue before looking up a matching search. A valid string result ID still
attaches its sources to the matching search.

Modex previously rejected these responses with HTTP 502. It now ignores
missing, null, and numeric result IDs before association, including when a
preceding search has the valid empty-string ID. That guard prevents a missing
or null result ID from being coerced to `""` and incorrectly attaching its
sources. `test_nonstring_buffered_search_result_ids_are_ignored` compares the
production Super request and normalized response across both pinned releases
and Modex. Its cases cover a numeric ID, missing and null IDs against an empty
search ID, and a matched string-ID control.

The synthetic test uses isolated process state, synthetic credentials, and a
loopback provider. It makes no account login or external provider request.

Reproduce the comparison with:

```sh
make build
PYTHONPATH=tests python3 -m unittest \
  test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_nonstring_buffered_search_result_ids_are_ignored \
  test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_search_result_sources_project_release_fields \
  test_anthropic_mixed_tools_01651.AnthropicMixedTool01651Tests.test_search_result_content_shapes_match_both_releases \
  test_anthropic_orphan_result_01651_04392 \
  test_anthropic_buffered_payload_04392 \
  test_provider_stream_01651_characterization.ProviderStream01651CharacterizationTests.test_anthropic_buffered_image_response_stays_rejected_like_release \
  test_provider_tools_04392_characterization.ProviderTool04392CharacterizationTests.test_anthropic_buffered_image_response_is_rejected_like_pinned_release -v
```

All four existing process methods passed. The new three-process identifier
matrix and the selected source/content-shape/orphan-result tests also passed.
The production import audit, test census and diff check passed as well.
All six release targets and remaining provider shapes stay in the parity
denominator.
