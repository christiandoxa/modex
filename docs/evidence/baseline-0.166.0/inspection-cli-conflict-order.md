# Doctor JSON and bundle conflict ordering

The active reference is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; its verified Linux x86-64 oracle
SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

In the pinned `crates/prodex-cli/src/session_context.rs`, `DoctorArgs.json`
requires `runtime` and conflicts with `bundle`; `DoctorArgs.bundle` requires
`redacted`. Clap reports the first conflicting option in argv order and builds
usage from the parsed options plus any required companion option. Modex
previously always reported `--json` first and omitted the appropriate usage
context when `--bundle` appeared first.

`test_inspection_cli_01660.py` compares ten argument orderings through the
production CLI and the pinned release. Exit status, empty stdout, stderr after
the executable-name normalization, and empty synthetic-home/workspace changes
match for both conflict orders. The cases run in separate Bubblewrap
namespaces with an empty environment, no network, and a private temporary
filesystem. No credentials or provider requests are used.

Reproduce after building Modex:

```sh
MODEX_BINARY=build/modex \
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
PYTHONPATH=tests python3 -m unittest -v \
  test_inspection_cli_01660.InspectionCli01660Tests.test_doctor_json_bundle_conflict_diagnostics_follow_argument_order
```

This qualifies only the listed Linux x86-64 doctor parser errors; it does not
qualify doctor execution, other CLI behavior, or the remaining release targets.
