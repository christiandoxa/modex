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
checksum-pinned release. Ten production-path controls pass against the pinned release, including
truncated ordinary and WebSocket bodies verified as EOF after half-close.
Separate raw-socket controls exercise the native relay and shared parser.
The integrated production build, native drivers and 42 relay, parser and CI
routing tests passed. No paid services or real accounts are used.

The relay remains serial; a separate two-request probe found Prodex accepts both
upstream requests concurrently while Modex serializes them. WebSocket transport
is not implemented; the 426 fallback is not WebSocket parity. Non-WebSocket
upgrade handling, the 413 reason phrase, and broader framing, timeout and
security behavior remain unverified or different.
