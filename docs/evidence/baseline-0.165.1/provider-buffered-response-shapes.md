# Buffered provider response JSON shapes

`tests/test_provider_buffered_response_shapes_01651_04392.py` compares the
production Super route in Modex with checksum-pinned Prodex 0.165.1 and 0.439.2
Linux processes. The providers receive synthetic responses and synthetic API
keys through loopback peers; no real credentials or paid provider traffic are
used.

| Route and upstream response | Prodex 0.165.1 | Prodex 0.439.2 | Modex |
| --- | --- | --- | --- |
| DeepSeek JSON root `null`, scalar, or array | 500, empty body | Same | Same |
| DeepSeek valid buffered object | 200; translated response matches | Same | Same |
| DeepSeek malformed JSON | 502, `provider response could not be processed` | Same | Same |
| Anthropic JSON root `null`, scalar, array, or malformed JSON | 502, `provider response could not be processed` | Same | Same |
| Anthropic valid buffered message | 200; translated response matches | Same | Same |
| Either route: retryable HTTP 503, then valid response | 200 after rotating to key B | Same | Same |

The DeepSeek response kernel now rejects a parsed response root that is not an
object. `_serve` maps this and the existing non-object first-choice failure to
the releases' bodyless 500 response. The 0.439.2 source at commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9` parses the buffered response in
`crates/prodex-provider-core/src/translators/deepseek/response_transform.rs`
and selects the first choice in
`crates/prodex-provider-core/src/translators/deepseek/response.rs`. The
historical 0.165.1 source at commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2` follows the same paths. The exact
bodyless 500 behavior is established by the three-process comparisons, not
inferred from the translation helper alone.

Oracle SHA-256 values: 0.165.1
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`; 0.439.2
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`. The
Modex executable used in the focused run had SHA-256
`68d1d11ee00267a464f8d2d276204082a0ae1009be0f70ba78aa025b9efac4b9`.

The four-method response-shape suite and ten-method CI oracle-routing suite
passed on Linux x86-64. Reproduce with the pinned local binaries and a built
Modex executable:

```sh
MODEX_BINARY="$PWD/build/modex" \
PRODEX_ORACLE_04392="$HOME/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu" \
PRODEX_ORACLE_01651="$HOME/.cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu" \
python3 scripts/ci/run-unittest.py test_provider_buffered_response_shapes_01651_04392.py
```

This qualifies only the listed buffered shapes and retry case on Linux x86-64.
It does not establish full provider parity, cover streaming responses, or
reduce the six-release denominator.
