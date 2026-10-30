# Logout help on Prodex 0.166.0

The active reference is official Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64 oracle
SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

At the pinned source, `crates/prodex-cli/src/lib.rs` declares the top-level
`Logout(LogoutArgs)` command and its about text; `crates/prodex-cli/src/profile.rs::LogoutArgs`
defines the positional name and `--profile` option. Clap prints the command's
static help for `logout --help`, `logout -h`, and `help logout`. Modex
previously routed these help requests to its generic unimplemented-command
error.

The production dispatcher now serves the same static help for those forms and
keeps Clap's observed help precedence: invalid or missing values before the
help flag remain errors, while arguments after a valid help flag are ignored.
The regression also covers compact `-hfoo`, attached and separated profile
values, duplicate values, extra operands, custom `argv0`, and the literal `--`
operand to `help logout`. Every compared process exits before logout handling
and creates no files. A Modex-only non-help control still reaches the existing
unimplemented-command guard without state changes.

`test_root_help_errors_01660.py` runs the real processes with cleared
environment, synthetic HOME/workspace, empty PATH, and unshared user, mount,
and network namespaces. It checks output, exit status, and created paths. The
oracle comparison for `logout -- --help` is excluded because it invokes the
real logout handler; a Modex-only control confirms that this literal form
still reaches the unimplemented-command guard without running logout. This
slice does not qualify logout execution or profile behavior.

Reproduce after building Modex with Mojo 1.2.0:

```sh
make build
MODEX_BINARY=build/modex \
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
python3 scripts/ci/run-unittest.py test_root_help_errors_01660.py
python3 scripts/ci/check-product-dependencies.py
```

The focused active-lane module passed all three methods on Linux x86-64, and
the production dependency audit passed. This covers only logout help and
selected parser precedence on that target; logout execution and the other five
release targets remain unqualified.
