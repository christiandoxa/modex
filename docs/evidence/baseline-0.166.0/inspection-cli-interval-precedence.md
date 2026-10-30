# Inspection CLI interval-error precedence

The active reference is official Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its Linux x86-64 oracle is pinned
by SHA-256
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

## Source trace

The pinned `crates/prodex-cli/src/lib.rs` derives the command parser with
Clap's `Parser`. `StatusArgs.interval` uses Clap's `u64` parser and range
`1..=60`; the pinned `Cargo.lock` selects Clap 4.6.7. In that parser,
`--interval=value` flows through `react` and validates immediately. The
separated `--interval value` form stores a pending value. A later recognized
option resolves it, while the unknown-option path attempts to resolve it but
ignores that value error before reporting the unknown argument. After `--`, a
literal operand is parsed as trailing input. Modex's shared
`inspection_help_requested` parser has one production caller, `main.main`.

## Process comparison

Attached invalid values take precedence over later errors:
`--interval=bad --once=false`, `--help=bad`, `-x=bad`, and `-- --` all report
the invalid interval; `--interval=0 --unknown` reports the interval range
error. For separated values, `status --interval bad --unknown --help` reports
the unknown option, `status --interval bad -- --interval --help` reports the
literal `--interval`, `status --interval 0 --unknown` reports the unknown
option, and `status --interval bad -- --` reports the literal `--`. Modex
matches the oracle's diagnostics, usage lines, exit statuses, and empty stdout.
Neither process creates files in its synthetic home or workspace.

Controls preserve adjacent precedence: recognized `--once` after a separated
bad interval reports the interval value error first, while `--once=true`
reports its own unexpected-value error.

Reproduce with:

```sh
python3 tests/test_inspection_cli_01660.py -v
```

The test verifies the oracle checksum and runs both real executables in
separate bubblewrap namespaces with isolated homes, workspaces, and networking.
`make build` and the focused two-test module passed on Linux x86-64. This
qualifies only these interval-error precedence cases, not broader CLI or status
parity.
