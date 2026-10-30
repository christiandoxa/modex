# Compressed session magic diagnostics

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

Checks on Linux x86-64:

- `PYTHONPATH=tests python3 -m unittest test_session_outputs_01660` with
  `MODEX_BINARY` and `PRODEX_ORACLE` set to the built and verified executables
  — 20 passed. The six new real-process cases compare exit status and exact
  output against the release in isolated homes and confirm the synthetic
  compressed file remains unchanged.
- `mojo build -O3 -I src tests/test_zstd.mojo -o build/tests/test_zstd && build/tests/test_zstd` — passed.
- `mojo build -O3 -I src tests/zstd_driver.mojo -o build/tests/zstd_driver && PYTHONPATH=tests python3 -m unittest test_zstd` — 6 passed, including valid concatenated/skippable frames and truncation cases.

This verifies malformed-frame diagnostics and the existing compressed-session
output cases on Linux x86-64. It does not establish side-effect parity, other
release targets, or overall session/log parity. Fixtures contain no real
credentials and make no provider requests.
