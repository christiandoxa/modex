# Session mtime fallback before Unix epoch

Prodex 0.166.0 at `9f69e1835808f478f59f12a3ae3fa88027d896a4` converts the
session file modification time through `SystemTime::duration_since(UNIX_EPOCH)`
in `crates/prodex-session-store/src/lib.rs::file_modified_epoch`. A time before
the epoch yields `None`; `read_session_report` then passes `0` to
`SessionReport::from_path`, which formats the fallback as `1970-01-01`.

Modex previously used the raw negative `st_mtimespec.tv_sec` in
`read_session`, so a synthetic session with no timestamp and mtime `-1` was
reported one second before the epoch. The production path now clamps that
fallback to zero. Parsed session timestamps still take precedence.

The isolated differential uses the checksum-verified Linux oracle
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`, a
temporary HOME and workspace, and a synthetic session file. Before the fix,
Prodex returned `1970-01-01 00:00:00 +00:00` and Modex returned
`1969-12-31 23:59:59 +00:00`; after the fix the new regression and all 15
methods in `test_session_outputs_01660` pass on Linux x86-64. Its inherited
non-object-followup safety control is Modex-only, not differential evidence.
The regression also compares `.json`, `.jsonl`, and `.jsonl.zst` files at
one second and one nanosecond before epoch and at epoch itself. For each it
checks both the fallback and an explicit record timestamp; the fixture verifies
that the filesystem retained the requested nanosecond mtime.

Reproduce after building Modex:

```sh
PYTHONPATH=tests \
MODEX_BINARY=build/modex \
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
python3 -m unittest -v \
  test_session_outputs_01660.SessionOutputs01660Tests.test_pre_epoch_file_time_falls_back_to_unix_epoch
```

This qualifies only the file-time fallback for pre-epoch mtimes on Linux
x86-64. It does not cover startup lock or housekeeping parity, session-state
recovery, other release targets, or complete session parity.
