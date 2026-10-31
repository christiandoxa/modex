# Offline redeem help routes (Prodex 0.166.0)

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

In pinned source, `crates/prodex-cli/src/lib.rs::Commands::Redeem` supplies the
static help through `cli_after_help(CliHelpKind::Redeem)`. Dispatch reaches
`crates/prodex-app/src/app_commands/redeem.rs::handle_redeem` only after Clap
finishes parsing; that handler loads profile state before any quota probe or
reset-credit request. Modex now matches the real Linux x86-64 oracle for
`redeem --help`, `redeem -h`, `help redeem`, and help after valid synthetic
options and a profile argument.

`tests/test_redeem_help_01660.py` compares checksum-verified oracle and Modex
processes with cleared environments, synthetic HOME and XDG directories,
private temporary storage, and an unshared network namespace. Each invocation
leaves the synthetic home unchanged; no credentials or provider traffic are
used. It also compares the unknown-option-before-help diagnostic. A Modex-only
control confirms stateful redemption remains fail-closed without creating
state or reaching a provider.

Short-option clusters `-yh`, `-hy`, `-hfoo`, `-yyh`, and `-yfoo` are also
compared before help. The tests check both help and duplicate/unknown option
diagnostics with no state creation.

Reproduce after building with Mojo 1.2.0:

```sh
make BUILD_DIR=/tmp/modex-redeem-help-build build
MODEX_BINARY=/tmp/modex-redeem-help-build/modex \
  PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
  PYTHONPATH=tests python3 -m unittest -v test_redeem_help_01660
python3 scripts/ci/check-product-dependencies.py
```

This qualifies only the listed Linux x86-64 help routes and one invalid-option
diagnostic. Reset-credit execution, other parser diagnostics, and the other
five release targets remain unqualified.
