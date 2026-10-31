# Local relay response header casing (Prodex 0.166.0)

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

Reference: official Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Source was acquired by
`scripts/ci/reference.py source active` into the verified isolated snapshot at
`~/.cache/modex/references/prodex-9f69e1835808f478f59f12a3ae3fa88027d896a4`;
the Prodex repository was not modified.

The source trace for the passthrough route is
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_response_dispatch.rs`:
upstream `HeaderMap` entries are passed as `name.as_str()` to
`runtime_forward_binary_response_headers` and
`runtime_forward_text_response_headers`. Those forwarding helpers preserve the
provided names. The 0.166.0 process therefore writes forwarded `HeaderMap`
names in lowercase. Generated framing fields remain owned by TinyHTTP's
response writer.

An isolated production-path differential used a synthetic local upstream that
returned HTTP 503 with `Content-Type`, `X-Request-ID`, and
`X-RateLimit-Remaining`, plus its normal `Server` and `Date` fields. Both
Prodex and Modex returned 503 with the exact body, one upstream POST, and the
same generated `Content-Length`. The oracle wrote forwarded names as
`server`, `date`, `content-type`, `x-request-id`, and
`x-ratelimit-remaining`; Modex previously retained the upstream's mixed-case
spellings. HTTP header names are case-insensitive, so this was a wire-format
difference, not a semantic 503 failure.

`src/modex/runtime_local_rewrite.mojo::_response_headers` now emits the
lowercase name after the existing hop-by-hop, nominated-header, and value
validation filters. This shared passthrough path keeps duplicate fields and
their order, and leaves values, status, body, and generated framing unchanged.
The active regression exercises the real Super-to-relay production path with
synthetic fixtures; it does not mock Modex.

Focused validation passed:

- `python3 scripts/ci/run-unittest.py test_provider_passthrough_01660.py` — 2
  active 0.166.0/Modex tests, including the new 503 header-casing regression.
- `python3 scripts/ci/run-unittest.py test_policy_capacity_01660.py` — 3
  active 0.166.0/Modex 503 retry and forwarding tests.
- `make unit UNIT_BUILD_PROGRAMS=test_gateway_cli UNIT_RUNS=test_gateway_cli`
  — the native gateway helper checks passed.
- Historical relay controls, run from `tests/`:

  ```sh
  python3 -m unittest -v \
    test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_response_header_overrides_filtering_and_invalid_values_match_oracle \
    test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_chat_passthrough_response_framing
  ```

  Both tests passed.

This qualifies only the tested Linux x86-64 0.166.0 passthrough 503 response
header spelling. It does not qualify other statuses, other targets, or the
relay's full HTTP/security contract. No dependency or parity-denominator
changes were made; no real credentials or paid provider traffic were used.
