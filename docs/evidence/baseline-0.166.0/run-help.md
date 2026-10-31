# Prodex 0.166.0 run help routes

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The pinned source at `9f69e1835808f478f59f12a3ae3fa88027d896a4` declares
`Run(RunArgs)` with trailing Codex arguments and uses the `Run` CLI help
section. The verified Linux x86-64 oracle has SHA-256
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

In separate Bubblewrap fixtures with synthetic empty homes, the 0.166.0 oracle
returns its run help with exit 0 for `run --help`, `run -h`,
`run --help --unknown`, `run --full-access --help`, and `help run`. Modex now
returns matching output and status for those routes, changing the executable
name only in the usage line. `run --help=bad` and `help run --help` retain the
oracle's typed parser errors. All oracle help cases leave the home and
workspace untouched. A Modex-only `run -hfoo` control stays on the guarded
non-help path; the pinned `RunArgs` marks Codex arguments as trailing and
allows hyphen values, but no oracle `-hfoo` process was run because it leaves
the help-only path. A Modex-only `run` control also reaches the existing
unimplemented-runtime guard without state changes; run execution and its
general option parser remain unfinished.

Reproduce from the repository root with Mojo 1.2.0:

```sh
make BUILD_DIR=build build
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
  MODEX_BINARY=build/modex PYTHONPATH=tests \
  python3 -m unittest -v test_root_help_errors_01660.RootHelpErrors01660Tests.test_run_help_routes_match_release_without_starting_runtime
```

The process test verifies the oracle checksum and uses isolated synthetic
fixtures without credentials or provider traffic. It checks a custom `argv0`
and a valid `--full-access` option before help, without launching Codex. This
qualifies only the listed help routes on Linux x86-64; other pre-help option
combinations, run argument parsing, launch, and the other release targets
remain unverified.
