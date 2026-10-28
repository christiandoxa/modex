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

The server's generated headers remain different. In the sampled buffered 200,
TinyHTTP sends `Server: tiny-http (Rust)` and a `Date` header without
`Connection: close`; Modex omits Server and Date and sends `Connection: close`.
The stable response headers, body and close result match for the tested case.
The captured raw heads were:

```text
0.439.2: HTTP/1.0 200 OK\r\nServer: tiny-http (Rust)\r\nDate: <runtime date>\r\ncontent-type: application/json; charset=utf-8\r\nContent-Length: 254\r\n\r\n
Modex:   HTTP/1.0 200 OK\r\nContent-Length: 254\r\nConnection: close\r\ncontent-type: application/json; charset=utf-8\r\n\r\n
```

For HTTP/1.0 HEAD 204/304 event-stream responses, both references return
HTTP/1.1 with `Transfer-Encoding: chunked` and the terminal `0\r\n\r\n` bytes.
Modex returns the same HTTP/1.1 status and chunked header, but suppresses the
terminal bytes. This remains a known mismatch.

TinyHTTP accepts the synthetic method token `G@T` and returns HTTP/1.0 404 for
an unsupported route. Modex rejects that non-token method and returns HTTP/1.1
400. Method-parser admission remains a separate gap; this slice only recovers
the response version when a valid HTTP/1.0 or HTTP/1.1 token is present in the
request line.

Validation: production Modex and the local-rewrite and shared-loopback native
drivers build with Mojo 1.2.0. The focused 0.439.2 oracle module passes both
tests, including 16 selected response/stream controls and the explicit header
and method-admission gaps. The historical 0.165.1 raw relay module, shared
loopback-server tests and local-rewrite tests pass 48 methods together. The
production dependency audit, Python compilation and `git diff --check` pass.
This evidence covers selected Linux x86-64 behavior only; it does not promote
full platform or contract parity.
