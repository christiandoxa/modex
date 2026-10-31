# At-signs in numeric-loopback provider paths

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The active reference is official Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

Prodex accepts `http://127.0.0.1:<port>/v1/a@b` and sends
`/v1/a@b/chat/completions` to the configured provider. Modex previously
rejected this valid path because its credential check searched the whole URL
for `@`. The relay now checks the parsed authority for credentials, then
applies its existing numeric-loopback validation. Literal `\@` remains
rejected at the ambiguous backslash boundary. Strict beta URLs retain their
existing whole-value `@` rejection.

`test_provider_base_url_scheme_01660.py` compares the active oracle and the
real Modex process with a synthetic loopback provider. Both send one request
to `/v1/a@b/chat/completions` with the synthetic bearer key. Modex-only
controls reject literal and percent-encoded userinfo, an encoded `@` host,
and a backslash-`@` path before any provider request. The existing authority
matrix retains non-loopback, malformed, and percent-encoded host rejection.

The process tests ran in a private user, mount, and network namespace with
only loopback and no default routes. A nested bubblewrap sandbox shared that
isolated network, mounted the workspace and oracle read-only, and used private
temporary storage and `HOME`. No real credentials, account login, or external
provider traffic were used.

## Validation

- `make build` passed with Mojo 1.2.0.
- `make UNIT_BUILD_PROGRAMS=test_gateway_cli UNIT_RUNS=test_gateway_cli unit`
  passed (`Gateway argument checks: PASS`).
- The active `test_provider_base_url_scheme_01660` and
  `test_provider_base_url_authority_01660` modules passed: 15 tests in 24.867
  seconds against the checksum-verified oracle and Modex.
- `make ci-dependencies` passed; 74 production Mojo files use only
  standard-library or internal imports.
- `git diff --check` passed.

This qualifies only the listed HTTP path and rejection controls on Linux
x86-64. Other provider behavior and the remaining five release targets remain
unqualified.
