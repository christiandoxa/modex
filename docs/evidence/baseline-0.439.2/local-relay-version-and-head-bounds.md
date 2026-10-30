# Local relay request versions and bounded heads

The active frozen reference is Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`; Prodex 0.165.1 is included as a
historical comparison. Both Linux binaries are checksum-pinned by the test
harness. All requests use isolated synthetic homes, a local fake Codex client,
and a loopback provider. No real credentials or provider traffic are used.

## HTTP/2.0 and HTTP/3.0 request lines

The pinned TinyHTTP source in `vendor/tiny_http/src/client.rs` recognizes
`HTTP/2.0` and `HTTP/3.0`. `ClientConnection::next` attempts a 505 response for
versions above 1.1, then continues reading the connection. That branch calls
`Response::raw_print`; its documentation in `vendor/tiny_http/src/response.rs`
says it does not flush the writer. This source trace suggests why the response
is not immediately visible, but the process test below establishes only the
observed wire behavior.

The production test sends each version token followed by a valid, pipelined
HTTP/1.1 request with `Connection: close`. It captures raw socket bytes for
1,200 ms, then checks for closure for up to another 500 ms. The fake client has
a 20-second process bound.

| Request line | Prodex 0.165.1 | Prodex 0.439.2 | Modex |
| --- | --- | --- | --- |
| `HTTP/2.0` | No response bytes; connection remains open; no provider request | Same | `HTTP/1.1 400 Bad Request`, `Content-Length: 0`; connection closes; no provider request |
| `HTTP/3.0` | No response bytes; connection remains open; no provider request | Same | `HTTP/1.1 400 Bad Request`, `Content-Length: 0`; connection closes; no provider request |

This is an observed mismatch. Modex keeps the bounded 400 response and closes
the client instead of retaining a socket while waiting for another request.
The same three-process test verifies successful `HTTP/0.9`, `HTTP/1.0`, and
`HTTP/1.1` controls, plus the malformed `HTTP/1.2` 400 control. The existing
`test_http_0_9_keepalive_and_pipelined_requests_match_oracle` also checks
supported-version reuse and response framing.

## Exact 4 MiB request head

The active test constructs an inbound request head whose `\r\n\r\n` offset is
exactly 4,194,304 bytes. Both pinned releases return 200 and forward the full
`X-Pad` value to the synthetic provider. Modex returns 502 without provider
dispatch because its relay cap is 2 MiB. This test does not claim the releases
reject any larger request.

Raising the Modex cap to 4 MiB would allow up to 152 live head-capture slots at
the current limits: 128 parked connections, up to 12 overflow connections, and
up to 12 active or queued worker requests. Their raw head data alone could
total 608 MiB, compared with 304 MiB at the current 2 MiB cap. This is a
worst-case byte-count estimate, not a measured RSS bound; parser copies,
serialized headers, allocator capacity, bodies, and socket buffers are not
included. No aggregate memory or saturation measurement supports raising the
cap, so Modex retains 2 MiB and this release mismatch remains open.

Reproduce after `rtk make build` on Linux x86-64:

```sh
PYTHONPATH=tests MODEX_BINARY="$PWD/build/modex" rtk proxy python3 -m unittest -v \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_exact_four_mib_head_exposes_release_and_modex_bounds \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_http_2_and_3_tokens_preserve_observed_release_wire_behavior \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_http_0_9_keepalive_and_pipelined_requests_match_oracle
```

These controls cover selected Linux x86-64 behavior only. They do not promote
the six release-target denominator or claim complete relay parity.
