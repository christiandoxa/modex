# 0.166.2 passthrough Accept-Encoding

The verified Linux x86-64 Prodex 0.166.2 release oracle has SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`.

The active process forwards inbound `Accept-Encoding` values on native
`/v1/chat/completions` passthrough after its default `identity` value, preserving
duplicates and order. Both processes filter a caller value nominated by the
inbound `Connection` header. The real-process comparison also confirmed that
buffered gzip and gzip SSE response bytes retain `Content-Encoding: gzip`, that
the existing 4 MiB limit applies to encoded response-body bytes, that gzip 429 responses
are returned without retry, and that compressed 401/503 responses retry using
the next configured synthetic key. A Responses continuation control was
unchanged.

One socket behavior is intentionally not claimed as equivalent. In the tested
compressed 401/503 cases, Prodex retries with key B over the socket used for key
A. Modex opens a new socket when retrying with a rotated credential, preserving
its credential-scoped pool isolation. Keep this security behavior visible as a
baseline difference.

Verification on Linux x86-64:

- `rtk make build unit` — passed.
- `PRODEX_ORACLE_01662=<verified-oracle> python3 scripts/ci/run_provider_upstream_pool_01662.py` — 21 tests passed in a Bubblewrap loopback-only namespace.
- `python3 scripts/ci/run-unittest.py test_provider_passthrough.py` — 3 tests passed, including the existing bounded-streaming/cap cases.
- `python3 scripts/ci/check-product-dependencies.py` — 74 production Mojo files use only standard-library or internal imports.

These checks qualify only the selected 0.166.2 transport cases on Linux x86-64;
they do not establish full provider parity or qualify the other release targets.
