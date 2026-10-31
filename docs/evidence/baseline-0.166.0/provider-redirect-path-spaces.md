# Redirect path and query spaces (Prodex 0.166.0)

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

Reference: official Prodex 0.166.0 at source commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. The verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

The 0.166.0 local rewrite uses its shared `reqwest` client through
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_transport.rs`.
For a same-origin loopback redirect with `Location` path and query spaces,
Prodex follows the redirect and sends `%20` in both components. Modex previously
rejected the raw space before its existing URL-component encoder ran. The
redirect parser now permits ordinary spaces through that encoder, explicitly
rejects spaces in the authority, and retains rejection of raw controls, DEL,
and backslashes. The canonical numeric-loopback authority and port check still
guards every followed redirect.

`test_provider_passthrough_01660.py::ProviderBufferedMetadata01660Tests.test_redirect_path_query_spaces_encode_without_weakening_authority_guards`
compares a real Modex Super relay and the checksum-verified release with a
synthetic loopback provider and API key. Both send the redirected GET to
`/v1/redirect%20path?label=two%20words` with the configured synthetic bearer
key. Both reject an authority containing a space before a second request.
Modex also keeps its stricter rejection of a spaced scheme, spaced userinfo,
raw tab, CR, and LF controls. The release treats a spaced scheme as a relative
path, accepts the tested spaced userinfo, and removes the tab before following;
those stricter Modex controls remain visible compatibility differences. In
Modex, malformed CR/LF response headers fail before redirect dispatch.

The test ran in the repository's active-release bubblewrap setup with isolated
HOME and temporary storage, read-only workspace and oracle, and a private
loopback-only network namespace. No real credentials or external provider
traffic were used. The process comparison qualifies this redirect behavior on
Linux x86-64 only; it does not establish full provider parity or the other
release targets.

## Apostrophes in redirect queries

The 0.166.0 process also percent-encodes an apostrophe in the query component
of a same-origin redirect as `%27`, while leaving an apostrophe in the path
literal. Existing `%20` escapes in either component stay unchanged. Modex
previously left query apostrophes literal; `_deepseek_redirect_target` now
encodes them after query-component encoding. This changes only the request
target representation and leaves authority parsing, redirect checks, and
control rejection untouched.

`test_provider_passthrough_01660.py::ProviderBufferedMetadata01660Tests.test_redirect_query_apostrophe_encoding_preserves_path_and_escapes`
compares the real Modex relay and verified release with a synthetic loopback
provider. It verifies path-vs-query apostrophe handling, existing `%20` escape
preservation, the synthetic bearer key, and the completed response. The
existing `test_redirect_path_query_spaces_encode_without_weakening_authority_guards`
continues to cover authority spaces, userinfo, scheme, and raw control
rejections.

The active comparison ran in a private bubblewrap network namespace with
isolated HOME and temporary storage, read-only workspace, binary, and oracle
mounts, and loopback only. The production build and all 20 tests in
`test_provider_passthrough_01660.py` passed with Mojo 1.2.0 on Linux x86-64.
This qualifies only the listed redirect query behavior; other URL forms,
targets, and full provider parity remain open.
