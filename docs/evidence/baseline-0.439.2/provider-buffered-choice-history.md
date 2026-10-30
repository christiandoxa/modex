# Buffered first-choice history shaping

The buffered DeepSeek response path selects the first `choices` entry for
translation and assistant history. It now rejects a present first entry that
is not an object. Missing or empty `choices` still produce an empty output,
and entries after the first remain ignored.

The release comparison exercises the actual Modex relay with a synthetic
loopback provider and synthetic credentials. Checksum-verified Prodex 0.439.2
(`72b77478a5198fc5da6b4d2253137f9cdbf43be9`, SHA-256
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`) and the
separately identified historical Prodex 0.165.1 control both match Modex for
these selected shapes:

- Null, numeric, and array first choices followed by an object send one
  upstream request and return empty HTTP 500 responses.
- Empty `choices` returns HTTP 200 with an empty output array.
- An object first choice followed by null returns HTTP 200 and preserves the
  first choice's text.

The historical 0.165.1 source at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and frozen 0.439.2 source at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`
translate the response through
`crates/prodex-provider-core/src/translators/deepseek/response.rs` and
`crates/prodex-provider-core/src/bridge/chat_compat/response.rs`. The app then
extracts assistant history in
`crates/prodex-app/src/runtime_launch/proxy_startup/deepseek_rewrite/response.rs`.
That helper calls `DEEPSEEK_CHAT_ASSISTANT_MESSAGES`, whose
`deepseek_chat_assistant_messages` operation returns failure when the first
choice is present but not an object. The process comparison confirms this
failure reaches the client as an empty HTTP 500. Modex now validates the first
choice in its buffered translator with the same error used by its history
shaper; the relay maps it to that status. Other buffered failures retain their
existing 502 mapping. The regression is registered in the fast and full
cross-release CI lists. Its 0.439.2 executable comes directly from
`PRODEX_ORACLE_04392`, with a version-pinned cache fallback; it does not import
the generic active-oracle variable.

Validation on Linux x86-64:

```text
rtk make build BUILD_DIR=/tmp/modex-provider-build — passed
mojo build -O3 --target-cpu=x86-64-v3 -I src tests/test_provider_chat_buffered.mojo -o /tmp/modex-provider-build/tests/test_provider_chat_buffered — passed
/tmp/modex-provider-build/tests/test_provider_chat_buffered — Provider buffered chat checks: PASS
MODEX_BINARY=/tmp/modex-provider-build/modex python3 scripts/ci/run-unittest.py test_provider_buffered_choice_01651_04392.py test_provider_buffered_response_shapes_01651_04392.py — 6 tests passed across both releases and Modex
python3 scripts/ci/check-product-dependencies.py — 71 Mojo files audited
python3 scripts/ci/check-test-census.py — 50 native test sources and 155 Python modules assigned once
git diff --check — passed
```

This qualifies only the listed Linux x86-64 response shapes. It does not
establish full provider parity, unsupported target behavior, or all six
release qualifications.
