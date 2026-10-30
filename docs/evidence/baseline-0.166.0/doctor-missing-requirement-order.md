# Doctor missing-requirement diagnostic order

Reference: official Prodex 0.166.0 at source commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; verified Linux x86-64 oracle
SHA-256 `349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

`DoctorArgs` in `crates/prodex-cli/src/session_context.rs:133-169` declares
`--suggest-policy` and `--json` as requiring `--runtime`; `--bundle` and
`--redacted` require each other. The release uses Clap 4.6.7. Its validator
collects requirements in parsed-option order, expands that graph for missing
requirement usage, and uses only direct requirements for conflict usage.
Modex now mirrors those distinct paths.

`tests/test_inspection_cli_01660.py::InspectionCli01660Tests.test_doctor_requirement_and_conflict_order_matches_release`
compares 34 two- and three-option orderings without `--runtime` against real
Prodex and Modex processes. The 533065d build mismatched 11/34 cases; this
build mismatches 0/34. The matrix omits the valid two-option
`--bundle --redacted` pair.

`test_doctor_runtime_requirement_and_conflict_errors_match_release` covers 18
three-option parse errors containing `--runtime`, plus the two existing
`doctor --runtime --bundle` and `doctor --runtime --redacted` controls. Prodex
and this build match all 20. The 533065d build mismatched 9/18 matrix cases and
both controls matched. Each tested command returns exit 2 with no output files
under the existing isolated sandbox, synthetic HOME, and workspace.

`test_doctor_runtime_json_redacted_passes_parser_but_runtime_is_guarded` checks
all six permutations of `--runtime`, `--json`, and `--redacted` against the
oracle and Modex in Bubblewrap with a cleared environment, synthetic
HOME/workspace, and no network. Prodex accepts each command and writes only
under synthetic HOME. Modex now passes argument validation, then returns its
existing exit-1 unimplemented-command guard without writing files. This closes
the parser gap only; Doctor runtime parity remains unimplemented.

## Checks

- `make BUILD_DIR=/tmp/modex-doctor-acceptance-build build` passed with Mojo 1.2.0.
- Both differential matrices, the two runtime controls, and all five tests in
  `test_inspection_cli_01660` passed, along with the new acceptance/guard test
  (six module tests total).
- `test_active_baseline_01660.ActiveBaseline01660Tests.test_doctor_execution_stays_guarded_without_help`
  passed.
- `python3 scripts/ci/check-product-dependencies.py` passed; 74 Mojo files use
  only standard-library and internal imports.

Reproduce the focused comparison after building Modex and providing verified
local binary paths:

```sh
MODEX_BINARY=/path/to/modex \
PRODEX_ORACLE=/path/to/prodex-0.166.0 \
PYTHONPATH=tests python3 -m unittest \
  test_inspection_cli_01660 \
  test_active_baseline_01660.ActiveBaseline01660Tests.test_doctor_execution_stays_guarded_without_help
```

This covers the tested parse diagnostics only. It does not establish parity for
other `doctor` modes or the remaining release targets.
