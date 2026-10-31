# Provider relay `100 Continue` headers

The active reference is the checksum-verified Prodex 0.166.2 Linux x86-64
release (`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`).
`tests/test_provider_relay_01662.py::ProviderRelay01662Tests.test_expect_continue_interim_defaults_match_without_release_content_length`
compares both real Super launch paths against a synthetic provider on loopback.

The client sends an HTTP/1.1 chat-completions request head with
`Expect: 100-continue`, waits for the interim response, then sends its synthetic
JSON body. Prodex returns `Server: tiny-http (Rust)`, `Date`, and
`Content-Length: 0` on `100 Continue`; Modex previously returned only the
status line. The production relay now includes the same `Server` and `Date`
fields when its normal response defaults are enabled. It omits the oracle's
`Content-Length: 0` because [RFC 9110 section 8.6](https://www.rfc-editor.org/rfc/rfc9110.html#section-8.6)
forbids that field on all 1xx responses. Both clients then receive HTTP 200,
and the peer records exactly one request with the complete body.

The focused process comparison passed in a private filesystem and network
namespace with loopback-only traffic, temporary HOME/config/state, and no real
credentials. The test checks Date syntax rather than exact seconds. This
qualifies one HTTP/1.1 case on Linux x86-64. The release's invalid interim
content length remains an explicit wire difference. Other expectation
combinations, request versions, and all five other release targets remain
unqualified. Run the focused test using the namespace driver documented in
`provider-relay-routes-bodyless.md`.
