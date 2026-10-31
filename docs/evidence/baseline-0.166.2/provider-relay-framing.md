# Provider relay response framing

The active reference is the checksum-verified Prodex 0.166.2 Linux x86-64
release. `tests/test_provider_framing_01662.py` runs the compiled Modex and the
release through the existing synthetic Super launch and Codex client, with a
raw loopback peer serving these response cases:

- close-delimited HTTP/1.1 JSON;
- `103 Early Hints` followed by a fixed-length JSON response;
- chunked JSON with a trailer;
- a truncated fixed-length JSON response.

The recorded local run placed the test process and both binaries in a private
network namespace; only its synthetic loopback peer was reachable.

The first three cases produce matching status and translated JSON. The
truncated body produces matching 502 responses. The peer records one provider
POST per process and uses synthetic request data and credentials. No
production change was indicated by these probes.

This is limited Linux x86-64 differential coverage of four framing cases. It
does not establish full provider relay, transport-failure, security, or
cross-platform parity.
