# Numeric loopback base URL authorities (Prodex 0.166.0)

Reference: official Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64
executable SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

## Observed mismatch and fix

The Prodex 0.166.0 local rewrite accepted numeric IPv4 loopback shorthand and
canonicalized the host before connecting. Modex previously required exactly
four decimal octets, so `http://127.1:<port>/v1` was rejected before the
provider request. A real Prodex process completed one synthetic loopback POST
to `/v1/chat/completions`; Modex exited with `HTTP address is not loopback` and
sent no provider request.

`normalize_loopback_ipv4_host` now parses the bounded WHATWG numeric IPv4
forms used by the release: one to four decimal, octal, or hexadecimal parts,
with one optional trailing dot. It checks each component and the assembled
32-bit value, requires the `127/8` loopback range, and returns canonical
dotted decimal. Hostnames and non-loopback addresses never reach name
resolution. The same normalizer is used by `local_rewrite_upstream`,
`loopback_get`, and `LoopbackHTTPStream`. Both HTTP request builders emit the
canonical address and decimal port in `Host`.

## Isolated process comparison

`tests/test_provider_base_url_authority_01660.py` compares the official
release and Modex through the real production DeepSeek relay, using only a
synthetic provider key and loopback fixture. Prodex and Modex both returned
200 and made one provider POST for each of these authorities:

- `127.1`
- `127.0.1`
- `127.0x.1` (an empty hexadecimal component resolves to zero)
- `127.0.0.01`
- `127.000.000.001`
- `0177.0.0.1`
- `0x7f000001`
- `2130706433`
- `127.0.0.1.`

Every request reached the fixture bound only to `127.0.0.1`; the translated
Chat Completions request bodies matched exactly. The test prefixes the
ephemeral port with three zeroes. Both products sent canonical
`Host: 127.0.0.1:<decimal-port>` values, matching the release's URL parsing.
The test also compares a `127.1` Anthropic Messages request: both products
sent one matching body to `/anthropic/v1/messages` with canonical `Host` and
the synthetic `x-api-key`.

Modex rejects `localhost`, `127.1.example`, malformed octal `127.0.0.08`, an
empty numeric component, too many components, standalone `0x` or overflowing hex,
tested addresses in 126/8 and 128/8, and numeric non-loopback aliases before a
loopback request. Direct native GET and streaming transport tests also verify
`127.1` plus zero-padded port normalization and the canonical `Host` field.

The run used the checksum-verified release and Modex build in a rootless user,
mount, and network namespace. It mounted the worktree, oracle, and Mojo
libraries read-only, used a private mode-700 tmpfs for `/tmp`, `HOME`, and
`TMPDIR`, exposed only loopback, and had no IPv4 or IPv6 default route. The
test uses no real credentials, account login, external provider traffic, or
Prodex state.

## Validation

- `make build` passed.
- Focused native Gateway CLI and DeepSeek transport tests passed.
- `test_provider_base_url_authority_01660.py`,
  `test_provider_base_url_scheme_01660.py`, `test_provider_shapes_01660.py`,
  `test_local_compact_gap_01660.py`, `test_loopback_http.py`, and
  `test_loopback_http_stream.py` passed together: 65 tests in 40.223 seconds.
- `test_ci_oracle_routing.py` and `test_ci_test_census.py` passed: 29 tests in
  1.899 seconds.
- A later isolated rerun of the authority matrix passed with `127.0x.1` added;
  the separate preceding 65-test run did not include that alias.
- The active authority comparison is included in both Fast and Full CI lanes.

## Limits

This comparison covers Linux x86-64 and the listed numeric IPv4 spellings.
It does not test other IPv4 numeric spellings, Unicode hosts, or connecting to a different address
within `127/8`. The comparisons in this file used explicit non-default ports.
The separate default-port comparison is recorded in
`docs/evidence/baseline-0.166.0/provider-default-port.md`; selected percent-escaped
numeric hosts are covered in `docs/evidence/baseline-0.166.0/provider-percent-encoded-host.md`.
Expanded IPv6 loopback forms are covered in
`docs/evidence/baseline-0.166.0/provider-ipv6-loopback.md`. This remains a
focused URL compatibility slice, not full provider or release-target parity.
