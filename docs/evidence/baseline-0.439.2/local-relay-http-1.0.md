# Local relay HTTP/1.0 responses against 0.439.2

The released Linux reference `0.439.2` was checksum-verified against
`docs/evidence/baseline-0.439.2/SHA256SUMS` and
`docs/evidence/baseline-0.439.2/reference-verification.json`. A raw synthetic
Codex client, local relay and loopback upstream exercised the production Super
path with isolated HOME, config, data, cache and temporary directories. No
real credentials or paid provider traffic were used.

For valid HTTP/1.0 requests, buffered local-relay responses now use HTTP/1.0
status lines. The tested cases include a translated 200 response, HEAD 200,
unsupported-route 404, invalid-target 400, fragment-target 400, malformed
header 400, `Expect: 100-continue` interim and final responses, unsupported
Expect 417, and upstream 302, 404 and 503 responses. A valid version token
before an extra request-line suffix also produces HTTP/1.0 502. A request line
without a version remains HTTP/1.1 400, matching the reference. Raw final
response heads are captured in the regression harness.

All 16 selected controls match the checksum-verified 0.439.2 and historical
0.439.1 for status line, status, reason, body, stable headers, interim
responses and tested close behavior. The tests run through the real local
rewrite path and use synthetic upstream responses. A slow, unknown-length SSE
response remains streamed: both references and Modex send HTTP/1.1 headers and
the first body byte before upstream EOF. The HTTP/1.0 request does not buffer
or delay the stream.

The local relay now adds TinyHTTP's default `Server: tiny-http (Rust)` and a
current GMT `Date` header when a buffered upstream or error response does not
already provide those fields, case-insensitively. It preserves supplied
duplicates and removes connection-nominated values before adding defaults.
Generated fields precede upstream fields and Content-Length, matching the
release's buffered response writer. SSE streaming keeps its separate framing
path and does not add defaults. The later keep-alive change also removed the
relay's `Connection: close` header, matching this reference response. Before
these changes, the captured raw heads were:

```text
0.439.2: HTTP/1.0 200 OK\r\nServer: tiny-http (Rust)\r\nDate: <runtime date>\r\ncontent-type: application/json; charset=utf-8\r\nContent-Length: 254\r\n\r\n
Modex:   HTTP/1.0 200 OK\r\nContent-Length: 254\r\nConnection: close\r\ncontent-type: application/json; charset=utf-8\r\n\r\n
```

For HEAD 200 and 204/304 event-stream responses, 0.439.2 returns HTTP/1.1 with
`Transfer-Encoding: chunked` and the terminal `0\r\n\r\n` bytes for HTTP/1.0
and HTTP/1.1 requests. The same controls pass against 0.165.1. Modex's
production local relay now returns the same framing. GET SSE controls retain
their event body, and a pipelined HEAD SSE followed by a translated Responses
request confirms the terminal chunk does not hide the next response. The
generic loopback writer keeps its default HEAD suppression; only the
production relay opts in.

TinyHTTP accepts the synthetic method token `G@T` and returns HTTP/1.0 404 for
an unsupported route. Modex rejects that non-token method and returns HTTP/1.1
400. Method-parser admission remains a separate gap; this slice only recovers
the response version when a valid HTTP/1.0 or HTTP/1.1 token is present in the
request line.

Validation: production Modex and the local-rewrite and shared-loopback native
drivers build with Mojo 1.2.0. The focused 0.439.2 oracle module passes eight
tests, including selected response/stream controls, header override/filtering
comparisons, HEAD SSE pipeline safety and the explicit method-admission gap.
The historical 0.165.1 raw relay matrix and focused header controls, 26
shared-loopback tests, 22 local-rewrite tests, native time checks, production
dependency audit, Python compilation and `git diff --check` pass. This evidence
covers selected Linux x86-64 behavior only; it does not promote full platform
or contract parity.
