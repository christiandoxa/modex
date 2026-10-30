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

The local rewrite now classifies an exact `Upgrade: websocket` header as the
426 fallback even when `Connection: Upgrade` is absent. The fallback closes
Modex's client connection before reading any declared body, preserving its
bounded trust boundary. For a fragmented `Content-Length: 0` followed by
`Content-Length: 100` request pipelined with a valid request, both releases
return 426 and then process the queued request as 200, reaching the synthetic
upstream once. Modex returns 426, closes the connection, and makes no upstream
request. A fragmented non-ambiguous WebSocket request has the same outcomes.
The status classification now matches, while connection reuse and pipeline
dispatch remain intentionally different. Invalid targets still take
precedence with 400, unsupported expectations with 417, and non-WebSocket
`h2c` framing remains 502 with no provider dispatch. Ambiguous framing without
a recognized WebSocket upgrade stays fail-closed.

Reproduce on Linux x86-64 after `make build`:

```sh
MODEX_BINARY="$PWD/build/modex" PYTHONPATH=tests python3 -m unittest -v \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_websocket_upgrade_rejects_before_reading_declared_body \
  test_local_rewrite_01651_oracle.LocalRewrite01651OracleTests.test_fragmented_websocket_pipeline_stays_closed_without_connection_upgrade \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_fragmented_websocket_pipeline_stays_closed_without_connection_upgrade \
  test_local_rewrite_04392_oracle.LocalRewrite04392OracleTests.test_identical_expectation_duplicates_match_and_ambiguous_framing_stays_fail_closed
```

This qualifies the selected loopback controls only. Broader malformed framing,
resource behavior, other targets, and all six release targets remain open.
