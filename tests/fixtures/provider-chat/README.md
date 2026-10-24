# Chat-compatible provider chunk provenance

These fixtures encode the frozen Prodex 0.439.0 source at
`433aad44bb249d5c25a231a6b06c2fa522a39a1f`:

- `crates/prodex-app/src/runtime_launch/proxy_startup/deepseek_sse.rs`
  calls choice/error decoding before stateful provider event emission.
- `crates/prodex-provider-core/src/translators/deepseek/stream/shaping.rs`
  selects only the first choice, projects metadata/deltas and classifies
  embedded errors through the compiled kernel.
- `mojo/prodex_core/deepseek.mojo` defines the active
  `deepseek_put_stream_choice_metadata`, `deepseek_put_stream_choice_delta`
  and `deepseek_put_stream_error_classification` rules.
- `crates/prodex-provider-core/src/translators/deepseek/stream.rs` supplies
  typed deserializers: wrong-type optional strings become absent and
  wrong-type arrays become empty. Empty delta strings are omitted by the
  kernel; an empty metadata `finish_reason` is retained.

Native and Python test inputs are inline. Their JSON views represent absent
typed fields as `null` and vectors as arrays; this is a test representation,
not a new provider wire schema. Unknown fields in the raw first choice and
selected arrays are preserved. Presence, including explicit `null`, controls
error `type`/`code` and `message`/`detail` fallback. Numeric error codes must
be signed 64-bit integers after upstream JSON number serialization; `-0`
and floating-point spellings are not integer codes.

The source kernel rejects selected non-object choices; the Rust caller
uses `expect` for kernel/projection failure. Modex raises an explicit error.
That failure behavior has not been exercised against the official binary
and is not a parity pass. Absent choices are represented by default views
in the test driver; the baseline caller simply skips choice observation.

The composed test feeds native SSE assembly output to the native chunk
driver with fragmented Unicode and `[DONE]` termination. These are
source-derived foundation checks, not actual provider/release comparisons.
CLI/provider execution does not call these helpers yet. Stateful event
translation, normalized usage, tool lifecycles, completion/error envelopes,
authentication and transport remain unfinished. No live provider is used.
