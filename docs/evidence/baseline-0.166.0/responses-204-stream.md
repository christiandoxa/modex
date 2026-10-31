# Responses 204 event-stream handling

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The active reference is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`, with Linux x86-64 oracle SHA-256
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

For a streaming `/v1/responses` request whose synthetic provider returns an
empty HTTP 204 event stream, the reference sends a chunked 204 response with a
`response.failed` event reporting unexpected end of stream. Modex previously
closed before sending response headers. The translated Responses path now
explicitly opts into this 204 event stream; other callers still reject streaming
204 and 304 by default.

The reference sends `Connection: close` but kept its socket open in the
tested keep-alive cases. Modex sends the observed event and terminal chunk,
then actually closes the socket. A pipelined second request does not reach the
provider. This preserves the existing framing boundary and is a documented
connection-lifecycle difference from the reference, not full wire parity.

The active process test covers empty-length and held-open chunked upstream
204s, 304/205 event-stream and 204/304 JSON controls. A separate native-driver
test checks default 204/304 stream rejection. Fixtures use synthetic
credentials, isolated state, private loopback networking, and no external
provider traffic. These observations apply to the tested Linux x86-64 route;
other requests, transports and release targets remain unqualified.
