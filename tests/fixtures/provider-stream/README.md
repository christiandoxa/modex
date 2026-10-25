# Frozen provider stream capture

Run `python3 tests/capture_provider_stream.py` to send a fixed catalog of DeepSeek SSE fixtures through the checksum-verified Prodex 0.439.0 Super provider adapter. The harness uses isolated HOME, Codex config, Prodex state, and a synthetic provider key. Its synthetic Codex HTTP client passes Prodex's version and app-server probes, then sends one Responses streaming request through the real local compatibility proxy.

After building `build/tests/provider_chat_stream_driver`, run `python3 -m unittest tests/test_provider_chat_stream.py` for byte comparisons, seeded chunk replay, and clean-runtime checks against committed captures. The catalog stores raw upstream and expected SSE as base64 plus per-response SHA-256 checksums; the test does not need the oracle binary.

The host network remains available. The harness configures and observes only loopback as the provider upstream; it does not claim network isolation or a clean-runtime parity result. No account login or real provider credential is used.

Fixtures cover seeded text with `[DONE]`, text EOF, reasoning, interleaved tool deltas, empty and Unicode-whitespace arguments, floating-point boundaries, malformed arguments and tool shapes, embedded errors, invalid UTF-8, fragmented SSE JSON, tool-search JSON shapes, missing call IDs across chunks, namespace spellings, RTK shell and exec calls, structured and multiline `apply_patch` inputs, late reasoning/usage, repeated finish chunks, and incomplete JSON at `[DONE]` and EOF. Available responses begin with the same text seed so native comparison can recover the captured request ID. The missing-call-ID fixture proves UUIDv7 fallback nondeterminism; raw bytes remain recorded while comparison permits only canonical UUIDv7 differences. Prodex exits before returning SSE for non-object choices and tool entries; the harness preserves the stderr as an explicit gap.

Prodex's Super process exits 1 after the response capture because the synthetic Codex child does not implement the app-server protocol. Each captured HTTP response is recorded and checked separately. A comparison mismatch is reported as `FAIL` but does not discard the oracle captures.

Raw upstream fixtures, oracle SSE responses, native SSE output when available, runtime logs, and checksum manifest are written under the gitignored `test-results/provider-stream-oracle/`. The harness reports exact matches, UUIDv7-normalized matches, and missing oracle captures separately.
