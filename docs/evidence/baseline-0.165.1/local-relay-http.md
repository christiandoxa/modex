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
arrives. For invalid-target rejections with request bytes still unread, Prodex
keeps the client socket open after its 400; Modex closes it.
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
check buffered HEAD length preservation and keep the generic streamed-HEAD
default free of body chunks and the terminal chunk. They cover HEAD 204/304
with chunked headers and the terminal chunk. The production local relay opts
into the terminal chunk for streamed HEAD responses, matching the release
while leaving other writer callers on the existing default.

Raw production controls compare HEAD 200 SSE and HEAD 204/304 SSE for both
HTTP/1.0 and HTTP/1.1 against checksum-pinned 0.165.1 and 0.439.2 processes.
Both releases return HTTP/1.1 chunked framing with the terminal
`0\r\n\r\n` chunk for these streaming or bodyless SSE responses. GET SSE still
matches, and a pipelined HEAD SSE followed by a translated Responses request
keeps the second response readable. Normal POST SSE chunking and disconnect
cancellation continue to pass.

The frozen TinyHTTP reader accumulates request-head lines without a byte cap.
The local relay now admits selected larger heads with a 1 MiB total capture
limit; other `read_request` callers keep the 65,536-byte default. Both 0.165.1
and 0.439.2 reach a synthetic upstream and return 200 for request heads of
65,535, 65,536 and 65,537 bytes, and for a 128 KiB single field on both
translated Responses and passthrough chat-completions routes. They also accept
a 1 MiB head with 4,096 fields and a mixed-case `Connection` case with 8,192
tokens plus 16,384 fields. Upstream probes compare the forwarded `X-Pad`
values byte-for-byte, confirm nominated hop headers are removed, and exercise
a 1 MiB translated-route `User-Agent` whose two outbound copies are both
preserved.

The 1 MiB cap is intentionally bounded: both releases accept a 1 MiB + 1-byte
head and reach the upstream, while Modex returns 502 `gateway request capture
failed` before dispatch. This remains a reproducible parity gap. The shared
parser still accepts a 65,536-byte head and rejects 65,537 bytes by default;
direct `LoopbackHTTPStream` callers retain their 65,536-byte aggregate and
field defaults. The relay's request-target, header-name, and response-header
limits are unchanged. These cases do not qualify other framing or security
behavior.

Validation for this slice: `make build` and focused native driver builds
passed. Four large-header process tests passed against the pinned 0.165.1 and
0.439.2 binaries, along with the shared-parser 65,536/65,537-byte boundary and
the existing 70 KiB direct-stream rejection check. An earlier 111-test broad
run had 109 passes and two 0.165.1 close-state assertion failures for
`invalid_target_precedes_malformed_chunked_trailer` and
`invalid_target_precedes_missing_chunk_terminator`. Each exact control was
rerun three times; all six observations matched the assertions: both releases
returned 400 without an upstream request, the oracle left the client socket
open, and Modex closed it. Do not treat the broad run as a full-suite pass.
The final production build and three focused native driver builds passed, as
did the 71-file production import audit, Python syntax compilation and
`git diff --check`. No real credentials or paid services were used.

Subsequent repeated probes used the checksum-pinned releases and isolated
synthetic peers. For the half-closed missing-terminator case, 0.165.1 closed
within the 500 ms observation window once and remained open seven times;
0.439.2 remained open eight times and Modex closed eight times. For the
malformed-trailer case, each release remained open eight times and Modex
closed eight times. All 48 responses were 400 with no upstream request. These
samples do not establish a deterministic close state for either release. The
historical test no longer asserts a fixed oracle close state for the observed
variable half-closed case; it still asserts Modex closes. A separate 0.439.2
production test checks the status, error body and lack of upstream traffic for
both cases without asserting oracle close state. Connection lifecycle remains a
known mismatch, and the earlier broad-run failures remain recorded.

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

With `Connection: Upgrade` and non-WebSocket requests, both pinned releases
capture raw bytes through EOF, even when the declared length is shorter or
longer. Modex now does the same on the local relay while retaining the body
limit and request timeout. Process comparisons cover h2c, missing Upgrade
headers, fragmented bodies, an oversized declared length, raw bytes with
`Transfer-Encoding: chunked`, and the first Connection header's case-insensitive
substring rule. The serial relay's 120-second request deadline still allows
an incomplete request to delay other work for that interval. The shared parser still
rejects Upgrade headers by default, and the WebSocket fallback is unchanged.
This is request-body capture, not h2c or HTTP/2 protocol support; other upgrade
and framing behavior remains unverified.

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

Buffered local-relay responses now add the frozen TinyHTTP defaults when the
upstream or error response has no case-insensitive `Server` or `Date` field:
`Server: tiny-http (Rust)`, followed by an RFC 7231 IMF-fixdate `Date` in GMT.
The date comes from the official Mojo realtime clock and is formatted with the
existing Gregorian calendar helpers. Caller values, including duplicate
mixed-case upstream fields, remain byte-for-byte ordered and suppress defaults
per field. Invalid or folded upstream text fields are discarded by the
existing response-header filter; connection-nominated `Server` and `Date` are
removed before defaults are added. Streaming SSE responses do not receive
these defaults, matching the release's separate response-writer path. The
opt-in belongs only to local-relay connections; standalone loopback callers
retain their prior headers.

The live raw-socket matrix compares all selected buffered success, parser
error, upstream error, HEAD and bodyless-response paths against the
checksum-verified 0.165.1 process and checks the emitted Date against the test
wall-clock window. A separate synthetic upstream matrix covers duplicate
mixed-case overrides, nominated fields, malformed control bytes and obsolete
folding. Fixed native formatter vectors include pre-epoch time, the Unix epoch,
leap day, and the RFC example. A 65,500-byte custom response header confirms
generated defaults and framing stay within the existing 65,536-byte response
head cap. The 0.165.1 oracle module and 26 shared loopback tests pass on Linux
x86-64. TLS/DNS, non-host targets, broader HTTP behavior and complete security
equivalence remain unqualified.

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
response. TinyHTTP emits `0\r\n\r\n` after its HEAD event-stream response; the
local relay now matches that terminal chunk and the test drains it before
parsing the next response. In `LoopbackHTTPStream._read_head`,
`src/modex/loopback_http.mojo` sets HEAD length to zero and finishes response
reading before nonempty bytes can reach downstream
`LoopbackHTTPConnection.write_chunk`; this fixture therefore does not confirm
the review's proposed disconnect path. Native
`test_head_stream_cancellation_is_still_detected` and
`test_peer_reset_is_detected_and_connection_move_keeps_ownership` continue to
verify RST cancellation. The shared loopback suite confirms the generic stream
writer keeps its default HEAD suppression. The production relay explicitly
opts into the release's terminal chunk, verified by the raw 0.165.1 and
0.439.2 process controls above.

Validation for this framing change: production Modex and both native drivers
build with Mojo 1.2.0. The 0.165.1 oracle module passes 16 tests; the active
0.439.2 oracle module passes seven. Shared loopback and local-rewrite tests
pass 48 tests together. The dependency audit covers 71 Mojo files, and Python
compilation plus `git diff --check` pass. These process comparisons use
synthetic loopback traffic on Linux x86-64 only.

Follow-up: the frozen TinyHTTP source does not set a total request-head limit.
`client.rs::read_next_line` appends bytes to a `Vec` through CRLF, and
`client.rs::read` appends headers to another `Vec` until the blank line.
Modex keeps a bounded production capture limit at 2 MiB; shared parser callers
retain the 65,536-byte default. This is an explicit resource bound, not full
parity with the unbounded reference. The existing outbound writer still caps
aggregate headers at 2 MiB + 2,048 bytes and each field at 1 MiB.

The checksum-pinned production controls now accept 1 MiB + 1-byte and exactly
2 MiB many-field heads through `/v1/responses`; exactly 2 MiB also reaches the
upstream through `/v1/chat/completions`. At 2 MiB + 1 byte, Prodex still
dispatches and returns 200 while Modex returns 502 before upstream dispatch.
An exactly 1 MiB User-Agent field is duplicated to the synthetic upstream by
both products; a 1 MiB + 1-byte field still reaches the Prodex upstream but
Modex rejects it under its existing outbound per-field limit. Larger reference
heads and some header distributions that expand during outbound translation
remain unqualified and may fail earlier than the aggregate inbound cap.

Validation on Linux x86-64: the full 16-test 0.165.1 production oracle module
passed, including the new 1 MiB + 1-byte, 2 MiB, and 2 MiB + 1-byte many-field
controls and exact 1 MiB / 1 MiB + 1-byte User-Agent controls. `rtk make build`
passed. Both focused native drivers built, and the local-rewrite and shared
loopback suites passed 48 tests. Controls use isolated temporary state, a
synthetic Codex peer, and a synthetic loopback upstream with the checksum-pinned
oracle; no credentials or paid services were used.

The shared size and field controls also pass against the checksum-pinned
0.439.2 oracle: it accepts the tested 2 MiB + 1-byte head and 1 MiB + 1-byte
User-Agent field, while Modex retains its explicit capture and outbound field
bounds. Both focused 0.439.2 large-head oracle tests passed.

## Request-line version handling

The frozen 0.165.1 TinyHTTP source parses versions in
`vendor/tiny_http/src/client.rs::parse_http_version`: it recognizes HTTP/0.9,
1.0, 1.1, 2.0, and 3.0. `parse_request_line` reads only its first three
space-separated fields. Unknown tokens such as HTTP/1.2 become
`WrongRequestLine`; `ClientConnection::next` emits an empty HTTP/1.1 400 and
closes. The frozen 0.439.2 source has the same parser and dispatch structure.

The production relay now opts into HTTP/0.9 and first-three-field parsing while
the shared loopback parser keeps its strict default. The checksum-pinned 0.165.1
and 0.439.2 processes and Modex match on HTTP/0.9 JSON requests, malformed
headers, and `Expect: 100-continue`: each response and interim response uses
the request's HTTP/0.9 line. An HTTP/0.9 connection with no `Connection`
header also carries two pipelined requests; all three processes return both
responses in order and honor `Connection: close` on the second. A request line
with two version-looking fields uses the first field, as TinyHTTP does. Leading
spaces and tabs are trimmed on the production relay, matching TinyHTTP and
preserving the HTTP/1.0 response line. HTTP/1.2 returns the same empty 400 in
both releases and Modex without provider I/O.
For an HTTP/0.9 request whose declared body ends early, all three close without
a response or upstream request.

HTTP/2.0 and HTTP/3.0 remain unqualified. TinyHTTP recognizes those tokens and
has a later HTTP-version branch, while Modex classifies them as unsupported and
returns 400; the isolated raw-process probe did not produce a stable release
response within its five-second client timeout. A repeat probe against the
checksum-verified 0.165.1 and 0.439.2 Linux binaries also timed out without a
response for either token. Do not count this as parity. All results are Linux
x86-64 process controls with synthetic credentials, isolated homes, and
loopback-only provider traffic.

Validation: the production build passed. The 0.165.1 raw HTTP matrix and the
0.9 keep-alive/pipeline control passed; the 0.439.2 matrix and the same
keep-alive/pipeline control passed. The truncated HTTP/0.9 body control also
passed against both releases and Modex. The leading-whitespace request-line
control passed against both releases and Modex. The shared loopback suite passed
all 27 tests, including its explicit check that HTTP/0.9 remains rejected by
default.

## Bodyless invalid-target `Expect` connection reuse

The checksum-pinned 0.165.1 and 0.439.2 processes both answer an invalid-target
HTTP/1.1 request with `Expect: 100-continue` and either no body framing or
`Content-Length: 0` with a 400 and no interim 100. Both keep the same socket
usable: a following valid request receives 200, both when sent after the 400
and when pipelined with the rejected request. Modex now matches those controls
and discards only the rejected header while retaining any buffered next
request.

For invalid-target requests with a nonzero declared body or chunked framing,
both releases also leave the socket open after the 400, while Modex closes it.
Those bodies remain unread when the target is rejected, so Modex retains the
safer close behavior instead of attempting to parse body bytes as another
request. This remains a documented difference, not full connection parity.

Validation on Linux x86-64: the full 16-test 0.439.2 production relay module
passed, including both bodyless framing variants, sequential and pipelined
reuse, and the nonzero and chunked fail-closed controls against both
checksum-verified releases and Modex. The production build and shared loopback
suite (27 tests) passed. The 71-file production import audit and the test
census (50 native, 139 Python) passed with no dependency changes. The synthetic
Codex peer, provider, credentials, homes and ports were isolated; no real
provider or account was used.

## Non-ASCII request-head bytes

The 0.165.1 and 0.439.2 TinyHTTP sources convert each completed request line to
`AsciiString` before trimming. A non-ASCII header-name or value byte therefore
fails line reading and produces no response. Modex previously returned an
empty 400; its production relay now closes on this parser error without
dispatching upstream. The cross-release controls check ordinary, fragmented,
and half-closed requests, plus a valid request pipelined before an invalid one.
See `docs/evidence/baseline-0.439.2/local-relay-header-whitespace.md` for the
source commits, wire observations, test command, and remaining framing gaps.
