# Root help unknown-command diagnostics

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The active reference is official Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its Linux x86-64 binary is pinned
by SHA-256 `349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

## Source trace

At the pinned commit, `crates/prodex-cli/src/lib.rs` derives `Cli` with Clap's
`Parser` and declares the root command through `#[command(subcommand)]`. The
root command enum declares visible commands, the `s` alias, and four hidden
internal commands. Clap supplies the built-in `help` subcommand; its unknown
operand diagnostic was confirmed with the official process.

## Process comparison

The isolated oracle returns exit 2, empty stdout, and
`error: unrecognized subcommand '<operand>'`, followed by root usage and the
standard help hint. It does not create home or workspace state for
`help statuz`, `help statuz ignored`, `help --unknown`, `help --`, or a custom
executable name.

Before this change, the real Modex binary returned exit 1 with the generic
unimplemented-command diagnostic for unknown `help` operands. The production
dispatcher now preserves declared root command names and returns the oracle's
unknown-subcommand diagnostic for the remaining operands. It reuses the
existing error formatter and adds no production imports or dependencies.
The active process also treats `--help`, `-h`, `--version`, and `-V` as
unknown operands after `help`; those forms now receive the same exit-2
diagnostic. `help help` renders the help-subcommand usage, while a further
operand produces its own exit-2 diagnostic without the root help hint. These
additional forms are compared in the same isolated test.

Reproduce with a built Modex binary and the verified oracle:

```sh
MODEX_BINARY=build/modex \
PRODEX_ORACLE=/path/to/prodex-0.166.0/prodex-x86_64-unknown-linux-gnu \
PYTHONPATH=tests python3 -m unittest test_root_help_errors_01660 -v
```

The test runs both production executables in isolated, network-disabled
namespaces with synthetic homes and compares status, stdout, stderr, and
created paths. `make build` and the focused comparison passed on Linux x86-64.
This qualifies only unknown operands to root `help`; valid but unimplemented
help targets, full CLI behavior, and other release platforms remain open.
