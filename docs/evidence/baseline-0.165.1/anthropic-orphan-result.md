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
when there is no unsupported block or search call. It validates each result
identifier and source shape, then leaves the result out of output. Existing
search-result association, tool-use validation, and fail-closed behavior for
unsupported blocks remain in place. These are selected buffered provider
cases, not general Anthropic or release parity.

Reproduce the comparison with:

```sh
make build
PYTHONPATH=tests python3 -m unittest \
  test_anthropic_orphan_result_01651_04392 \
  test_anthropic_buffered_payload_04392 \
  test_provider_stream_01651_characterization.ProviderStream01651CharacterizationTests.test_anthropic_buffered_image_response_stays_rejected_like_release \
  test_provider_tools_04392_characterization.ProviderTool04392CharacterizationTests.test_anthropic_buffered_image_response_is_rejected_like_pinned_release -v
```

All four process methods passed. The native `test_provider_chat_buffered`
program, production import audit, test census and diff check passed as well.
All six release targets and remaining provider shapes stay in the parity
denominator.
