# Percent-encoded numeric loopback hosts

The active reference is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; its Linux x86-64 oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

The active release accepts percent-encoded numeric loopback hosts such as
`127%2e1` and sends a canonical `127.0.0.1` Host header to the provider. The
prior Modex build rejected them. The DeepSeek URL boundary now decodes the host
with the existing URL helper and then applies the numeric `127/8` parser;
raw transport addresses still use normalized numeric literals. Hostnames,
encoded separators and controls, malformed escapes, and non-loopback
destinations remain rejected before a connection.

`tests/test_provider_base_url_authority_01660.py` compares the checksum-pinned
release and Modex through real Super processes, synthetic credentials, and a
loopback provider. It covers five encoded numeric forms in Chat Completions,
one in Anthropic Messages, canonical Host and request bodies, and selected
rejected malformed or non-loopback forms. These cases do not qualify Unicode
hosts, all URL spellings, other providers, or other release targets.

The production build and dependency audit passed. In a private user, mount,
and loopback-only network namespace, the active authority, scheme, and
session-history modules passed 12 tests; a subsequent authority-module rerun
with additional malformed-escape controls passed all three tests. The manual
default-port comparison also passed, and the native Gateway checks passed.
Full native `make unit` passed on
`89d1dc406ca2a8325e23e2889cedd43340542abf`; this is not a full CI verdict.
