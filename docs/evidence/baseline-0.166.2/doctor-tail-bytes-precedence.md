# Doctor tail-bytes parser precedence

The active baseline is Prodex 0.166.2 at
`b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`; its verified Linux x86-64
binary has SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`.

`DoctorArgs::tail_bytes` is a typed `usize` option in the pinned
`crates/prodex-cli/src/session_context.rs`. Modex parses this option in
`src/modex/inspection_cli.mojo::inspection_help_requested`. Before this fix,
an invalid separated value such as `--tail-bytes abc` failed immediately.
Prodex's CLI parser defers that typed-value error while it continues parsing:
a later unknown argument or malformed attached `--help=x` takes precedence.
If parsing reaches an exact help flag or a recognized option, the invalid
tail-bytes value takes precedence. An invalid attached value remains immediate.

Modex now stores separated tail-bytes errors in the same pending validation
slot already used for `--interval`. The active process regression compares
exact stderr and exit code for these boundaries:

- Invalid split values followed by unknown long/short options, a malformed
  attached help value, and positionals after `--` report the later syntax
  error, matching Prodex.
- Invalid split values followed by exact help or a recognized option report
  the invalid tail-bytes value, matching Prodex.
- Invalid attached values still report immediately, and an overflow split
  value also defers to a later unknown option.

Every case runs both binaries with synthetic HOME and a network-isolated
`bwrap --unshare-all` sandbox. They exit 2 with empty stdout and create no
files. The change only affects argument-error ordering; it does not reach
doctor execution, profile state, or runtime logs.

Validation on Linux x86-64 with Mojo 1.2.0 (`2016d0cd`):

- `make BUILD_DIR=build build` — passed with existing unused-variable warnings.
- `MODEX_BINARY=build/modex PRODEX_ORACLE=/path/to/prodex-0.166.2/prodex-x86_64-unknown-linux-gnu python3 scripts/ci/run-unittest.py test_doctor_tail_bytes_precedence_01662.py test_doctor_install_01662.py` — 15 tests passed.
- `python3 scripts/ci/check-test-census.py` — passed; 50 native sources and 239 Python modules have one suite owner.
- `python3 scripts/ci/run-unittest.py test_ci_oracle_routing.py test_ci_test_census.py` — 30 tests passed; both Fast and Full active lanes include the new regression.
- `python3 scripts/ci/check-product-dependencies.py` — passed; 74 Mojo production files use only standard-library and internal imports.

This is selected parser evidence on Linux x86-64, not full Doctor execution or
six-target parity. Stateful Doctor operations remain behind their existing
guards.
