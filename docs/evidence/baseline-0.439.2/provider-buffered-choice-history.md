# Buffered first-choice history shaping

The buffered DeepSeek response path selects the first `choices` entry while
building assistant history. It now rejects a present first entry that is not
an object. Missing or empty `choices` still produce empty history, and entries
after the first remain ignored.

The release comparison exercises the actual Modex relay with a synthetic
loopback provider and synthetic credentials. Checksum-verified Prodex 0.439.2
(`72b77478a5198fc5da6b4d2253137f9cdbf43be9`, SHA-256
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`) and the
separately identified historical Prodex 0.165.1 control both match Modex for
these selected shapes:

- A null first choice followed by an object sends one upstream request and
  returns an empty HTTP 500 response.
- Empty `choices` returns HTTP 200 with an empty output array.
- An object first choice followed by null returns HTTP 200 and preserves the
  first choice's text.

The Modex history shaper raises on the malformed first choice. The relay maps
that case to the release's empty HTTP 500 response; the other buffered failures
retain their existing 502 mapping. The regression is registered in the fast
and full cross-release CI lists. Its 0.439.2 executable comes directly from
`PRODEX_ORACLE_04392`, with a version-pinned cache fallback; it does not import
the generic active-oracle variable.

Validation on Linux x86-64:

```text
rtk make build — passed
mojo build -O3 --target-cpu=x86-64-v3 -I src tests/test_provider_chat_buffered.mojo -o build/tests/test_provider_chat_buffered — passed
build/tests/test_provider_chat_buffered — Provider buffered chat checks: PASS
python3 scripts/ci/run-unittest.py test_provider_buffered_choice_01651_04392.py — 1 test passed across both releases and Modex
python3 scripts/ci/check-product-dependencies.py — 71 Mojo files audited
bash -n scripts/ci/run-fast.sh scripts/ci/run-full.sh — passed
git diff --check — passed
```

This qualifies only the listed Linux x86-64 response shapes. It does not
establish full provider parity, unsupported target behavior, or all six
release qualifications.
