# Local relay HTTP behavior against 0.165.1

Synthetic Codex and loopback peers exercised the real DeepSeek Super local
proxy. Selected malformed request lines and headers produce an empty 400; a
request line with an extra token produces a 502 upstream failure. An exact
WebSocket Upgrade header produces a 426 HTTPS fallback response without an
upstream request. Truncated request bodies close without a fabricated response.
Previously Modex returned 502 for the selected malformed syntax and did not
implement the upgrade fallback.

The native relay now handles these tested cases. Its shared HTTP parser still
rejects upgrades by default; only the local relay opts in for WebSocket. The
0.165.1 oracle regression uses synthetic Codex and loopback peers with the
checksum-pinned release. Production-path controls pass against the pinned release, including
truncated ordinary and WebSocket bodies verified as EOF after half-close.
Separate raw-socket controls exercise the native relay and shared parser.
The integrated production build, native drivers and 42 relay, parser and CI
routing tests passed. No paid services or real accounts are used.

An oversized declared body of 67,108,865 bytes now returns the exact 413
`Payload Too Large` status phrase and error body without an upstream request,
matching the 0.165.1 and historical 0.439.2 binaries. The regression checks
the actual production relay and its shared HTTP response writer.

The relay now validates request targets against the pinned 0.165.1 controls.
Invalid targets take precedence over WebSocket fallback and oversized declared
or chunked-body errors; an 8,192-byte target is accepted and an 8,193-byte
target is rejected. Raw fragment targets rejected by the shared parser now map
to the release's invalid-target JSON on the relay path; direct shared-parser
calls retain the same syntax error. Truncated declared-length bodies without
`Expect` still close without a response. Invalid-target chunked requests return
400 before body capture: controls cover a header-only half-close, truncated
chunk data, a missing zero-chunk terminator, and a delayed nonempty trailer.
The delayed control confirms both binaries reply before the body fragment
arrives. Prodex keeps that client socket open after its 400; Modex closes it.
With invalid targets and `Expect: 100-continue`, both binaries return the final
400 directly for valid and oversized declared body lengths, without an interim
100 response. A two-connection production control gets 400 for the invalid
target, then serves a valid request with 200. The
relay opts into a 65,536-byte request-line cap so the 8,192-byte target can fit
with its method and HTTP version; the shared parser's default 8,192-byte cap
remains unchanged. The rebuilt native parser suite passes all 15 tests,
including exact 8,192/8,193-byte line boundaries.

The production local rewrite now forwards the parsed method unchanged on both
recognized routes. `GET`, `HEAD`, `PUT`, `DELETE`, `OPTIONS` and `X-EXT`, plus
extension methods of 8,192 and 8,193 bytes, reach the synthetic upstream and
match the pinned oracle's 501 response. Outbound method tokens are validated;
the direct CRLF-injection control is rejected. For successful GET requests,
`/v1/responses` returns the same translated JSON body as 0.165.1 and
`/v1/chat/completions` returns the exact upstream JSON body, both with matching
Content-Length framing. GET SSE is chunked on both routes: chat completions
passes through the exact upstream events, while Responses produces matching
translated events after normalizing the generated message ID.

HEAD controls use a method-aware client, send `Connection: close`, and make a
bounded 250 ms socket peek after parsing the response headers. The peek
completes with no response payload bytes for the tested 501, 200 and 502
responses in both binaries. `/v1/chat/completions` returns 200 with
Content-Length 0. `/v1/responses` receives a successful bodyless upstream HEAD
but returns the oracle's 502 translation error with Content-Length 40; Modex
now suppresses that error body on the wire. Direct shared-server controls also
check buffered HEAD length preservation, streamed HEAD without chunk data or a
terminator, and HEAD 204/304 with chunked headers but no terminator. Independent
raw oracle probes, now reproducible in the oracle matrix, found that HEAD 204
and 304 with `text/event-stream` include `Transfer-Encoding: chunked` and the
terminal `0\r\n\r\n` chunk in 0.165.1. A HEAD 200 SSE response emits the same
terminal chunk. Modex suppresses those terminators for HEAD, so raw-wire parity
for HEAD event-stream cases is not claimed. Normal POST SSE chunking and
disconnect cancellation continue to pass.

Large request heads remain a parity gap. A 32,768-byte `X-Pad` header reaches
the upstream in both binaries. At request-head lengths before the terminating
`\r\n\r\n` of 65,535, 65,536 and 65,537 bytes, 0.165.1 reaches the upstream and
gets 200; Modex returns 502 without an upstream request. Its body is `upstream
request failed` at 65,535 and 65,536 bytes, and `gateway request capture
failed` at 65,537 bytes. These probes document selected boundaries; broader
header framing remains unqualified.

Validation for this slice: the production build passed; the 0.165.1 oracle
matrix passed; all 20 shared loopback-server tests, 22 local-rewrite tests and
26 provider transport tests passed. The provider native checks and production
dependency audit passed. No real credentials or paid services were used.

The relay remains serial; a separate two-request probe found Prodex accepts both
upstream requests concurrently while Modex serializes them. WebSocket transport
is not implemented; the 426 fallback is not WebSocket parity.

Production-path controls now cover `Upgrade: h2c` without `Connection: Upgrade`,
mixed-case `H2C`, and `Upgrade: example/1`. Prodex and Modex return the same 200
response and make one upstream POST for each; the upstream receives no `Upgrade`
header. Modex treats these as ordinary framed HTTP requests and strips the
hop-by-hop upgrade metadata.

Chunked request controls cover a plain body with an empty trailer section and
an extension on the data chunk; both return 200 and make one upstream POST in
Prodex and Modex. With a nonempty valid `X-Trace` trailer or a malformed
`X-Trace synthetic` trailer, Prodex returns 502 `gateway request capture
failed` without an upstream request. Modex previously accepted the valid
trailer and returned 200, and mapped the malformed trailer to 400. The local
relay now opts into rejecting nonempty trailers during capture, matching the
release; the shared parser's default still accepts valid trailers for its
other callers.

The source trace reaches TinyHTTP's `Request::capture`, which reads the
`Transfer-Encoding: chunked` body through `chunked_transfer::Decoder`. The
decoder is pinned at 1.5.0 in Prodex's `Cargo.lock`; after the zero-size chunk,
it requires an immediate empty CRLF and treats trailer fields as a decode
error. This does not change Modex's support for chunk extensions or empty
trailer sections.

With both `Connection: Upgrade` and `Upgrade: h2c`, the pinned Prodex returns
200 and makes one upstream POST after the synthetic client half-closes after its
body. Modex keeps this case fail-closed: it returns 502 `gateway request capture
failed` and makes no upstream request. The baseline reader consumes this
connection as an upgraded stream through EOF; Modex's bounded HTTP parser does
not implement that stream framing. This remains a documented transport
mismatch. No h2c, HTTP/2 prior-knowledge, or other protocol upgrade transport is
claimed. The regression also retains WebSocket fallback and duplicate Upgrade /
Connection controls.

Validation for the Upgrade-header change: the production build and both focused
Mojo drivers compiled; the two-test 0.165.1 oracle suite passed, including its
full raw HTTP matrix; all 22 local-rewrite tests and 20 shared loopback-server
tests passed. The production dependency audit and `git diff --check` passed.
These controls use synthetic loopback traffic and no real credentials or paid
services.

The raw oracle matrix also checks trailer boundaries split across sends. A
fragmented nonempty trailer is rejected after its first byte; an empty trailer
terminator split between CR and LF is accepted. Half-closed missing terminators
return 502 instead of closing without a response. Invalid-target chunked
controls return 400 before delayed or truncated bodies are read. For complete
requests without `Connection: close`, Prodex leaves the client socket open
after these 400 and 502 responses and after an accepted 200; Modex closes it
after each response, a separate connection-lifecycle mismatch.

Validation for the chunked-trailer change: `rtk make build`, both focused Mojo
drivers, the two-test 0.165.1 oracle suite, all 22 local-rewrite tests and all
20 shared loopback-server tests passed. The loopback suite confirms default
shared-parser trailer support. The production dependency audit,
`python3 -m py_compile tests/test_local_rewrite_01651_oracle.py` and
`git diff --check` passed.

Broader framing, timeout and security behavior remain unverified or different.

HTTP/1.1 connection reuse now matches selected 0.165.1 controls. TinyHTTP's
`ClientConnection::next` keeps HTTP/1.1 alive by default, stops after
`Connection: close` or `Connection: upgrade`, and requires `keep-alive` for
HTTP/1.0. The Modex local relay now reuses a completed client socket for
sequential requests and omits the previous forced `Connection: close` header.
Only the local relay opts into persistence; shared loopback-server callers
still close by default and emit `Connection: close`. It parks up to 128 idle
sockets in FIFO order, polls one new connection before each parked-socket
readiness scan, and checks the parent channel between requests. At the cap one
accepted overflow socket waits while ready requests are serviced; then the
oldest socket with no request bytes is evicted to admit it. Parked sockets have no idle
expiry; disconnected sockets are reclaimed. A partial request on a reused
socket blocks other clients until it completes or the socket closes; parent EOF
does not interrupt an in-progress read. The request read has a 120-second
deadline. Active request handling remains serial.

Synthetic raw-socket comparisons cover two sequential requests on one socket,
explicit `Connection: close`, fragmented request headers, a second client
while the first is idle, and parent shutdown while a helper retains the idle
socket. Regression controls fill the 128-socket pool and confirm a new client
is admitted by evicting the oldest idle socket, preserve a partial request on
the oldest socket while admitting an overflow client, and keep ready parked
clients moving during new-client churn. A partial-header control on a reused
socket confirms the second client is served after the partial socket closes. A
prior coalesced two-request probe found a pipelining gap: Modex returned 502
`gateway request capture failed` before any upstream request. That mismatch is
resolved by the buffered-request handling recorded below. The local rewrite's
WebSocket route still returns the baseline 426 fallback; that does not qualify
the separate runtime-proxy WebSocket transport. See
`docs/evidence/baseline-0.165.1/local-websocket-prerequisites.md`.

Validation on Linux x86-64: `rtk make build` passed, as did
`rtk make unit-build UNIT_BUILD_PROGRAMS='local_rewrite_driver loopback_server_driver'`.
The complete focused relay suite passed 59 tests. After the latest source
change, the rebuilt native drivers passed all 45 direct local-rewrite and
loopback tests. The production dependency audit passed for 71 Mojo files and
`git diff --check` passed. Tests use synthetic loopback peers, with no
credentials or paid traffic. All six release targets and broader
framing/security behavior remain unqualified.

Pipelined local relay requests now preserve request boundaries across the
existing bounded socket buffer. `read_request` removes only the captured
headers and body, retains bytes belonging to later requests, and carries the
remaining byte count into the next parse. `request_ready` services buffered
bytes before peeking the socket; response completion no longer clears them.
This is enabled only on connections accepted by the local relay, which opts in
to keep-alive. Shared loopback-server callers retain their previous strict
single-request behavior. HTTP body limits, malformed framing and nonempty
chunked trailers still reject before provider dispatch.

Source trace: frozen commit `10ae15b5d1806302b60f051e4e6fec788044f4c2` uses
TinyHTTP `ClientConnection::next` in
`~/.cache/modex/prodex-0.165.1/vendor/tiny_http/src/client.rs`. Its buffered
`next_header_source` reads successive request heads; `no_more_requests` stops
after `Connection: close`/`upgrade` or HTTP/1.0 without keep-alive. Each
`Request` gets a sequenced writer, and the server's `recv` dispatches requests
to the local rewrite handler, which captures each body before relay dispatch.
The Linux oracle is checksum-pinned in
`docs/evidence/baseline-0.165.1/reference-verification.json`.

The production-path oracle matrix compares coalesced fixed-length and bodyless
requests, fragmented chunked framing with the next request coalesced after the
terminal CRLF, distinct bodies, ordered HEAD/error/SSE/buffered responses,
`Connection: close`, and an oversized second body. Two pipelined requests reach
the synthetic upstream in the correct forms; the oversized follow-up retains
the 64 MiB body cap and does not dispatch upstream. The full 14-test 0.165.1
oracle module passed on Linux x86-64 before the final pipelined cases were
added; the expanded matrix, including oversized-body and HEAD SSE half-close
controls, passed separately. The 45 native local-rewrite and shared loopback
tests passed, along with production
build and driver builds. Parent shutdown, idle fairness, the existing body
limit suite, duplicate framing, and strict trailer controls also passed in the
full oracle run. Requests remain serial; only request buffering and ordering
are qualified. Other release targets and broader framing/security behavior
remain unqualified.

A real-process HEAD SSE control sends a complete pipelined POST with and
without `shutdown(SHUT_WR)`. The pinned 0.165.1 oracle and Modex both dispatch
both requests and return the HEAD response followed by the buffered request's
response. TinyHTTP emits `0\r\n\r\n` after its HEAD event-stream response;
Modex suppresses that terminal chunk, so the test drains and records the raw
oracle framing before parsing the next response. This is the existing HEAD SSE
wire mismatch, not lost buffered input. In `LoopbackHTTPStream._read_head`,
`src/modex/loopback_http.mojo` sets HEAD length to zero and finishes response
reading before nonempty bytes can reach downstream
`LoopbackHTTPConnection.write_chunk`; this fixture therefore does not confirm
the review's proposed disconnect path. Native
`test_head_stream_cancellation_is_still_detected` and
`test_peer_reset_is_detected_and_connection_move_keeps_ownership` continue to
verify RST cancellation. The 23-test shared loopback suite passed after the
probe change.
