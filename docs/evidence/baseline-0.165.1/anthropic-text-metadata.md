# Buffered Anthropic text-block metadata

The pinned Prodex 0.165.1 and 0.439.2 Linux processes accept extra fields on
Anthropic `text` content blocks. They project the string `text` into Responses
output and omit `citations` and other fields. Before this change, Modex rejected
those same responses with HTTP 502.

## Baseline trace

At Prodex 0.439.2 commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`,
`crates/prodex-provider-core/src/translators/anthropic/messages/response.rs`
lines 15-25 classifies blocks using `type`, whether `text` is a string, and
tool-specific fields. Lines 72-98 pass the original content blocks to the
response kernel. `mojo/prodex_core/anthropic_request.mojo` lines 1503-1567
validates each message block's `type` and `text`, then writes only
`{"type":"output_text","text":...}`. This drops citations and arbitrary
text-block metadata while still rejecting a missing or non-string `text`.

The historical 0.165.1 source is not used as implementation evidence. Its
checksum-pinned process was compared directly alongside 0.439.2.

## Production comparison

`tests/test_anthropic_mixed_tools_01651.py` uses synthetic Codex and loopback
provider peers, an isolated temporary HOME/state/config, and a synthetic API
key. It compares the request body and normalized complete response from Modex
with both oracles. Only `created_at` is normalized.

Cases cover a text-only response with a valid character citation and unknown
metadata, malformed citation values (object, string, and number), a web-search
result followed by cited text, and cited text preceding a function call. All
three processes return HTTP 200, preserve text, and omit citations and unknown
fields. Missing and non-string text still return the same HTTP 502 response in
all three processes.

Pinned oracle SHA-256 values:

- Prodex 0.165.1: `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
- Prodex 0.439.2: `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`

## Validation

- `mojo --version`: `Mojo 1.2.0 (2016d0cd)`
- `rtk make build`: passed; Linux x86-64-v3 `build/modex` SHA-256
  `56313e5cf8197192ce842a469ec6485d1bdf6733fe6bb4994fa42c06cdd8af85`
- `python3 scripts/ci/run-unittest.py test_anthropic_mixed_tools_01651.py`:
  37 tests passed, including the citation/extra-field matrix and malformed
  text controls.
- `test_provider_tools_04392_characterization.py` keeps its citation comparison
  0.439.2-only for the Fast CI phase; its focused assertion passed. The 0.165.1
  comparison remains in the cross-release mixed-tools suite.
- The product dependency audit and `git diff --check` passed.

This qualifies only the tested buffered text-block shapes on Linux x86-64.
Citation annotations remain omitted to match both releases; streaming behavior,
other provider response blocks, and other compiler targets remain outside this
slice.
