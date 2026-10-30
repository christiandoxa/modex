# DeepSeek streamed text-item IDs

Reference: official Prodex 0.166.0, commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. The verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

## Baseline trace

In `crates/prodex-app/src/lib.rs`, Prodex builds each runtime request ID from
UUIDv7 entropy and the local sequence. `runtime_proxy_request_id_from_entropy`
hashes both values with `DefaultHasher`, uses the high 32 bits as a prefix, and
keeps the low 32 bits of the local sequence. The sequence seed starts at one.
`crates/prodex-app/src/runtime_launch/proxy_startup/deepseek_sse.rs` passes the
request ID through the SSE state. Provider-core delegates the text item ID to
the Mojo stream policy, whose mode 1 formats `msg_{provider}_{request}`. The
resulting item ID is `msg_deepseek_<decimal UInt64>`.

Modex now composes the low 32 bits of its local sequence with the low 32 bits
of a fresh UUIDv7. Its production local-rewrite path passes that value to the
same `msg_deepseek_<decimal UInt64>` formatter. It matches the observed ID
shape and local sequence field, but not Prodex's exact high bits: Modex uses a
UUIDv7 suffix instead of Prodex's `DefaultHasher` result.

## Process comparison

`tests/test_deepseek_stream_ids_01660.py` runs the verified Prodex binary and
the built Modex binary through their real local-rewrite processes. A synthetic
loopback provider returns two streamed chat completions in one process. For
both binaries, each response uses the same item ID in its `output_item.added`
and `output_item.done` events, the decimal value fits in `UInt64`, and its low
32 bits are 1 then 2. After normalizing only the numeric item ID, the SSE
responses match byte-for-byte. A second process starts at local sequence 1 and
produces a different full item ID for each binary. The fixture checks one
upstream POST per request and uses only synthetic authorization data.

These samples establish the tested shape and observed uniqueness cases. The
random 32-bit prefix can collide across processes, and the low sequence field
repeats after 2^32 requests. IDs are not a security token or a global
collision-free identifier; exact Prodex high-bit parity remains open.

## Checks

- `make build` passed with Mojo 1.2.0.
- `make unit UNIT_BUILD_PROGRAMS=test_uuid7 UNIT_RUNS=test_uuid7` passed,
  including UUIDv7 suffix bounds and invalid-input cases.
- With the pinned oracle in `PRODEX_ORACLE` and the built binary in
  `MODEX_BINARY`, `python3 scripts/ci/run-unittest.py
  test_deepseek_stream_ids_01660.py test_deepseek_reasoning_01660.py
  test_local_rewrite.py` passed 26 tests.
- With `PRODEX_ORACLE_04392` unset and `HOME=/proc/self/nonexistent`, the
  active stream-ID process test passed using only the pinned 0.166.0 oracle.
- `python3 scripts/ci/run-unittest.py test_ci_oracle_routing.py` passed 14
  tests, including active-suite routing for the new process test.
- `make ci-dependencies` passed; 72 Mojo files use only standard or internal
  imports.

This is evidence for the synthetic Linux x86-64 process cases only. It does not
establish exact high-bit parity, global uniqueness, or qualification across all
six release targets.
