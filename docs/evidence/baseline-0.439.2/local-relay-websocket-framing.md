# Local rewrite WebSocket framing precedence

The frozen 0.165.1 source is commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2`; the active frozen 0.439.2 source
is commit `72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Both versions implement
the local rewrite fallback in
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_pipeline_websocket.rs`.
Their request wrapper identifies `Upgrade: websocket` in
`local_rewrite_request.rs`, and the pipeline returns 426 with
`provider adapter requires HTTPS Responses transport fallback` without a
provider dispatch.

The real-process comparison in
`test_websocket_upgrade_rejects_before_reading_declared_body` sends raw
requests through the Modex Super CLI and both checksum-pinned release binaries.
All homes, ports, and provider responses are synthetic and isolated. A
conflicting `Content-Length: 0` / `Content-Length: 100` request with both
`Connection: Upgrade` and `Upgrade: websocket` now returns the same 426 status,
reason, response headers (apart from generated `Date`), and body in all three
processes. The test appends a complete second request to that ambiguous head.
All three close before reusing it; none dispatches to the synthetic provider.
A synthetic Authorization value is not echoed in the response or process
diagnostics.

Negative controls preserve validation precedence: an invalid absolute target
with the same conflicting lengths returns 400 in all three processes, and an
unsupported `Expect` returns 417 without a 100 interim response. An `h2c`
upgrade remains outside the WebSocket fallback and does not dispatch upstream;
both releases return 502 `upstream request failed`, while Modex returns 502
`gateway request capture failed`.

The local rewrite classifies an exact `Upgrade: websocket` header as the 426
fallback even when `Connection: Upgrade` is absent. Modex now follows TinyHTTP's
body-capture order: a no-Connection request with a positive `Content-Length` up
to 1,024 bytes, no `Expect`, and no transfer encoding is read before the
adapter returns 426. If that body ends early, TinyHTTP closes without a
response; Modex now does the same. Bodyless requests, `Connection: Upgrade`,
chunked requests, `Expect` requests, and fixed bodies over 1,024 bytes still
reach the fallback before body capture. Invalid targets still take precedence
with 400, unsupported expectations with 417, and non-WebSocket `h2c` framing
remains 502 with no provider dispatch. Ambiguous framing with a recognized
WebSocket upgrade remains fail-closed in Modex.

For a fragmented `Content-Length: 0` followed by `Content-Length: 100` request
pipelined with a valid request, both releases return 426 and then process the
queued request as 200, reaching the synthetic upstream once. Modex returns 426,
closes the connection, and makes no upstream request. A fragmented
non-ambiguous WebSocket request has the same status and connection-reuse gap.
The body-order change does not alter that pipeline behavior.

## TinyHTTP eager body-capture boundary (2026-10-30)

At both frozen source commits, `vendor/tiny_http/src/request.rs::new_request`
uses the first `Connection` field and treats any case-insensitive value
containing `upgrade` as a raw connection. Otherwise it preloads a fixed body
only when its first `Content-Length` is 1–1,024 and `Expect: 100-continue` is
absent. The local rewrite later identifies the WebSocket header and returns
426 without provider dispatch. This ordering explains the short-body behavior.

The 3-way process matrix in
`test_websocket_body_capture_order_matches_both_releases` covers body lengths
0, 1, 1,024, and 1,025 with delayed complete bodies and half-closed partial
bodies. The exact regression (`Content-Length: 10` with one byte and a
half-close) now yields no response on Prodex 0.165.1, Prodex 0.439.2, and
Modex. The controls also cover valid and unsupported `Expect`, chunked framing,
`Connection: Upgrade`, comma and substring upgrade values, duplicate
`Connection` fields, and zero-first conflicting length or CL/TE framing. All
three products return the same expected response for these controls and make
no upstream request.

One deliberate fail-closed difference remains: with no `Connection: Upgrade`,
`Content-Length: 2`, then `Content-Length: 1`, one body byte, and half-close,
both releases close without a response because their first-length reader
expects two bytes. Modex returns its 426 fallback before reading the ambiguous
body. It still makes no upstream request. This case is not counted as parity.

A low-load production control holds one no-Connection one-byte WebSocket body
partial while another preconnected idle socket receives a valid 200, then
completes the partial body and receives 426. The partial and idle clients are
not evicted in this control. The production request deadline remains 120,000
ms; listener capacity, timeout, and saturation policy did not change. The
known saturated-pool eviction and pipeline gaps remain open. Validation used
synthetic loopback traffic on Linux x86-64 only; all six release targets and
the separate runtime-proxy WebSocket transport remain unqualified.

Reproduce on Linux x86-64 after `make build`:

```sh
MODEX_BINARY="$PWD/build/modex" PYTHONPATH=tests python3 -m unittest -v \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_websocket_body_capture_order_matches_both_releases \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_positive_first_conflicting_websocket_length_stays_fail_closed \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_websocket_body_wait_keeps_one_idle_and_partial_client \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_websocket_upgrade_rejects_before_reading_declared_body \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_fragmented_websocket_pipeline_stays_closed_without_connection_upgrade \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_fragmented_websocket_pipeline_stays_closed_without_connection_upgrade \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_identical_expectation_duplicates_match_and_ambiguous_framing_stays_fail_closed
```

This qualifies the selected loopback controls only. Broader malformed framing,
resource behavior, other targets, and all six release targets remain open.
