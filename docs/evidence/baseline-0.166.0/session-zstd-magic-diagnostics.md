# Compressed session magic diagnostics

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

Prodex 0.166.0 is pinned at `9f69e1835808f478f59f12a3ae3fa88027d896a4`.
Its session reader uses `zstd::stream::read::Decoder` for `.jsonl.zst` files in
`crates/prodex-session-store/src/session_file.rs`. With isolated synthetic
session files, the release reports `Unknown frame descriptor` for impossible
short magic prefixes such as `x` and `28 00`; Modex previously reported
`incomplete frame` because it requested all four magic bytes before checking
the available prefix.

`src/modex/zstd.mojo` now rejects a prefix as soon as it can match neither a
Zstandard frame nor a skippable frame. Valid partial Zstandard and skippable
prefixes still report `incomplete frame`; a valid magic followed by a truncated
frame header also remains `incomplete frame`. Native checks decode a small
valid Zstandard frame, including after a valid skippable frame.

The pinned lock resolves `zstd` 0.14.3 to `zstd-sys` 2.1.2+zstd.1.5.7. Its
session reader uses `zstd::stream::read::Decoder`. That release accepts the
existing synthetic Huffman fixture with SHA-256
`cd6cd6c87dd74d4d71d147bbe0b03488d408ef89d0806797f8a0365be7c1aa70` and reaches
UTF-8 validation; Modex rejects it as `Data corruption detected`. [RFC 8878
§4.2.2](https://www.rfc-editor.org/rfc/rfc8878.html#section-4.2.2) requires
exact bitstream consumption, so Modex retains rejection: these are unconsumed
bits, not permitted padding. The real-process comparison also checks a
truncated checksummed frame and a declared-size overrun, which both readers
reject, and verifies each fixture remains unchanged. This is a deliberate
security-preserving compatibility gap.

Checks on Linux x86-64:

- `PYTHONPATH=tests python3 -m unittest test_session_outputs_01660` with
  `MODEX_BINARY` and `PRODEX_ORACLE` set to the built and verified executables
  — 21 passed. The compressed Huffman case records both exact outcomes and
  verifies the input remains unchanged; truncated and overfull controls reject.
- `mojo build -O3 -I src tests/test_zstd.mojo -o build/tests/test_zstd && build/tests/test_zstd` — passed.
- `mojo build -O3 -I src tests/zstd_driver.mojo -o build/tests/zstd_driver && PYTHONPATH=tests python3 -m unittest test_zstd` — 7 passed, including strict rejection of the noncanonical frame, valid concatenated/skippable frames, and malformed/truncated controls.

This verifies malformed-frame diagnostics and the existing compressed-session
output cases on Linux x86-64. It does not establish side-effect parity, other
release targets, or overall session/log parity. Fixtures contain no real
credentials and make no provider requests.
