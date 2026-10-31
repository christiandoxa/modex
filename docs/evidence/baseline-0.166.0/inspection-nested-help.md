# Nested inspection help on Prodex 0.166.0

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The active reference is official Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64 oracle
SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

The oracle accepts `help current`, `help info`, `help status`, and `help doctor`
as aliases for each command's direct `--help` route. Modex now renders those
routes through its existing inspection help functions. Trailing operands keep
the release's unrecognized-subcommand diagnostic and command usage. The checks
also cover custom executable names. All compared processes exited without
creating files in isolated homes and workspaces.

Reproduce after building Modex with Mojo 1.2.0:

```sh
make build
MODEX_BINARY=build/modex \
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
python3 scripts/ci/run-unittest.py test_inspection_cli_01660.py
python3 scripts/ci/check-product-dependencies.py
```

The focused active-oracle suite and production dependency audit passed on Linux
x86-64. This covers only nested inspection help and selected operand handling;
the inspection commands' execution behavior and the other five release targets
remain unqualified.
