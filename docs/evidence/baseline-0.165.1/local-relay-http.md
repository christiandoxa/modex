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
calls retain the same syntax error. Truncated bodies without `Expect` still
close without a response. With invalid targets and `Expect: 100-continue`, both
binaries return the final 400 directly for valid and oversized declared body
lengths, without an interim 100 response. A two-connection production control
gets 400 for the invalid target, then serves a valid request with 200. The
relay opts into a 65,536-byte request-line cap so the 8,192-byte target can fit
with its method and HTTP version; the shared parser's default 8,192-byte cap
remains unchanged. The rebuilt native parser suite passes all 15 tests,
including exact 8,192/8,193-byte line boundaries.

Oversized method and header behavior remains a parity gap. With custom methods
of 8,192 and 8,193 bytes, 0.165.1 forwards to the synthetic upstream, which
returns 501; Modex returns 404 `unsupported_provider_route`. A 32,768-byte
`X-Pad` header reaches the upstream in both binaries. At request-head lengths
before the terminating `\r\n\r\n` of 65,535, 65,536 and 65,537 bytes, 0.165.1
reaches the upstream and gets 200; Modex returns 502 without an upstream
request. Its body is `upstream request failed` at 65,535 and 65,536 bytes, and
`gateway request capture failed` at 65,537 bytes. These probes document
selected boundaries; method limits and broader header framing remain
unqualified.

The relay remains serial; a separate two-request probe found Prodex accepts both
upstream requests concurrently while Modex serializes them. WebSocket transport
is not implemented; the 426 fallback is not WebSocket parity. Non-WebSocket
upgrade handling and broader framing, timeout and
security behavior remain unverified or different.
