# DeepSeek streamed text-item IDs

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

Reference: official Prodex 0.166.0, commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. The verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

## Baseline trace

In `crates/prodex-app/src/lib.rs`, Prodex builds each runtime request ID from
UUIDv7 entropy and the local sequence. `runtime_proxy_request_id_from_entropy`
hashes both values with `DefaultHasher`, uses the high 32 bits as a prefix, and
keeps the low 32 bits of the local sequence. The pinned Rust 1.99.1
`DefaultHasher::new()` is zero-key SipHash-1-3; on these little-endian targets,
the locked `uuid` crate's big-endian `as_u128()` value is written as its lower
word, upper word, then the full `u64` sequence. The final hash uses a 24-byte
message. `runtime_proxy_request_sequence_seed` derives a nonzero instance
prefix from UUID, process, thread, and log-path identity and sets its low bits
to one; `fetch_add` returns that seed for the first request and wraps at
`u64::MAX`.
`crates/prodex-app/src/runtime_launch/proxy_startup/deepseek_sse.rs` passes the
request ID through the SSE state. Provider-core delegates the text item ID to
the Mojo stream policy, whose mode 1 formats `msg_{provider}_{request}`. The
resulting item ID is `msg_deepseek_<decimal UInt64>`.

Modex's production local-rewrite path hashes UUIDv7 entropy and the full local
sequence using the same pinned input order and SipHash-1-3 rounds, then formats
`msg_deepseek_<decimal UInt64>`. Its counter starts at 1 and takes the current
value under the existing lock before incrementing with wrapping arithmetic,
matching the first returned value and wrap behavior of `fetch_add`. The locked
counter remains thread-safe. `tests/test_uuid7.mojo` checks three fixed outputs
generated with Rust 1.99.1 `DefaultHasher::new()` for UUID
`017f22e2-79b0-7cc3-98c4-dc0c0c07398f`:

| Sequence | Request ID |
| --- | --- |
| `1` | `3c2a7a9d00000001` |
| `0x123456789abcdef0` | `9a52489a9abcdef0` |
| `u64::MAX` | `14e68c0dffffffff` |

The native test also checks six distinct UUIDv7 values against the same pinned
Rust toolchain, including zero, `2^32 - 1`, `2^32`, and `u64::MAX` sequence
boundaries and uppercase hexadecimal input. These additional vectors exercise
both UUID words; they do not determine the runtime instance seed.

These checks verify the deterministic hash mapping for the supplied UUID and
sequence inputs. Modex still lacks Prodex's full per-instance seed, which hashes a
fresh UUID, process ID, current thread ID, and log path. The audited public
Mojo 1.2 `std.os.process` and `std.runtime` interfaces expose no PID or
current-thread-ID getter; a compile probe confirmed the shipped
`std.sys._libc` also exports neither POSIX `getpid` nor `pthread_self`. Project
rules disallow adding native bindings, so exact seed parity remains blocked
with the audited interfaces. Each request still uses independent UUIDv7
entropy; process observations do not establish seed parity or exact
cross-process IDs.

## Process comparison

`tests/test_deepseek_stream_ids_01660.py` runs the verified Prodex binary and
the built Modex binary through their real local-rewrite processes. A synthetic
loopback provider returns two streamed chat completions in one process. For
both binaries, each response uses the same item ID in its `output_item.added`
and `output_item.done` events, the decimal value fits in `UInt64`, and its low
32 bits are 1 then 2. A concurrent two-request observation also checks that
those sequence values are unique under load. After normalizing only the numeric
item ID, the serial SSE responses match byte-for-byte. A second process starts
at local sequence 1 and produces a different full item ID for each binary.
The fixture checks one upstream POST per request and uses only synthetic
authorization data.

These samples establish the tested shape and observed uniqueness cases. The
random 32-bit hash prefix can collide across processes, and the low sequence
field repeats after 2^32 requests. IDs are not a security token or a global
collision-free identifier. The deterministic vector check does not qualify
the upstream instance-seed derivation or exact cross-process ID parity. The
sequence-take helper checks that `u64::MAX` is returned before stored state
wraps to zero; process-level overflow was not exercised end-to-end.

## Checks

- `make build` passed with Mojo 1.2.0 after the fetch-add ordering change.
- `make unit BUILD_DIR=/tmp/modex-request-id-01660-unit UNIT_BUILD_PROGRAMS=test_uuid7 UNIT_RUNS=test_uuid7`
  passed, including the fixed Rust hash vectors and assertions that the final
  sequence value is returned before the stored sequence wraps to zero.
- `make build` and `make unit-build BUILD_DIR=build UNIT_BUILD_PROGRAMS=local_rewrite_driver`
  passed with Mojo 1.2.0.
- Under `unshare -Urnm`, with loopback as the only interface, no default route,
  a private tmpfs `/tmp`, read-only worktree and pinned oracle, and sanitized
  environment, `python3 scripts/ci/run-unittest.py
  test_deepseek_stream_ids_01660.py test_deepseek_reasoning_01660.py
  test_local_rewrite.py` passed all 26 tests. The process fixture used only
  synthetic authorization data and a loopback provider.
- With `PRODEX_ORACLE_04392` unset and `HOME=/proc/self/nonexistent`, the
  active stream-ID process test passed using only the pinned 0.166.0 oracle.
- After adding the concurrent-ID case, both tests in
  `test_deepseek_stream_ids_01660.py` passed against the pinned oracle and
  Modex under user, mount, and network namespaces, with private tmpfs `/tmp`,
  loopback only, and synthetic provider credentials. The concurrency fixture
  held both requests until both reached the synthetic provider.
- `python3 scripts/ci/run-unittest.py test_ci_oracle_routing.py` passed 14
  tests, including active-suite routing for the new process test.
- `make ci-dependencies` passed; 72 Mojo files use only standard or internal
  imports.

This evidence covers the fixed hash vectors and synthetic Linux x86-64 process
cases only. It does not establish upstream instance-seed parity, global
uniqueness, or qualification across all six release targets.
