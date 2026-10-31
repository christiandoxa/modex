# DeepSeek redirect authority canonicalization (Prodex 0.166.0)

Reference: official Prodex 0.166.0 at source commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. The verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

## Source trace and mismatch

The 0.166.0 local rewrite builds provider requests with its shared `reqwest`
client in `crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_transport.rs`.
Its standard URL parser canonicalizes equivalent numeric host spellings before
redirect handling. A synthetic active-oracle run followed a 302 from
`[::1]` to the equivalent expanded IPv6 spelling
`[0:0:0:0:0:0:0:1]` on the same port.

Modex previously compared redirect authority text to the configured address.
It therefore returned the original 302 instead of following a same-origin
redirect whose IPv6 spelling differed. The production redirect path now
canonicalizes numeric IPv4 loopback spellings and strict IPv6 loopback literals
along with their port, then follows only when both canonical endpoints match.
It reuses the existing IPv4 parser and the shared strict IPv6 loopback check.
No DNS lookup or broader network access was added.

## Isolated process comparison

`tests/test_provider_passthrough_01660.py` exercises the real Modex Super relay
and the official 0.166.0 process with synthetic credentials and loopback
providers. Both now follow same-endpoint redirects from `127.1` to its
canonical dotted IPv4 form and from `[::1]` to its expanded IPv6 spelling.
The redirected GET reaches the expected provider path with the configured
synthetic bearer key, and both processes return the same translated response.

Modex-only controls retain the original 302 after one provider request for a
different IPv6 address, unspecified and zero IPv6 addresses, a different port,
userinfo, HTTPS, malformed IPv6, and an encoded authority colon. A redirect
cycle through the equivalent expanded IPv6 address remains bounded: both
processes make 11 provider requests and return 502. Encoded numeric host forms
such as percent-encoded dots were not qualified and remain rejected by Modex.

The active process test ran with the repository's bubblewrap helper, a private
network namespace with no default routes, private temporary state, and
read-only workspace, binary, and oracle inputs. It used no real credentials or
external provider traffic.

## Validation

- `make BUILD_DIR=<scratch>/build build` passed with Mojo 1.2.0.
- `make BUILD_DIR=<scratch>/build unit UNIT_BUILD_PROGRAMS="test_provider_deepseek_transport test_gateway_cli" UNIT_RUNS="test_provider_deepseek_transport test_gateway_cli"` passed both native checks.
- The focused redirect regression passed against Prodex 0.166.0 and Modex.
- `python3 scripts/ci/run-unittest.py test_provider_passthrough_01660.py` passed all 16 active relay tests in the private bubblewrap network namespace.
- `make ci-dependencies` passed: all 74 production Mojo files use only standard-library or internal imports.
- `git diff --check` passed.

This comparison qualifies only the tested numeric-loopback redirect spellings
and bounded redirect case on Linux x86-64. It does not qualify other redirect
host encodings, targets, or complete provider parity.
