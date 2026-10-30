# Doctor missing-requirement diagnostic order

Reference: official Prodex 0.166.0 at source commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`; verified Linux x86-64 oracle
SHA-256 `349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

`DoctorArgs` in `crates/prodex-cli/src/session_context.rs:133-169` declares
`--suggest-policy` and `--json` as requiring `--runtime`; `--bundle` and
`--redacted` require each other. The parser previously reported several
two-option missing-requirement cases in a different order from Clap, including
`doctor --runtime --redacted` and the reversed option order. Modex now orders
the missing requirements and usage additions from the parsed options' declared
requirements.

`tests/test_inspection_cli_01660.py::InspectionCli01660Tests.test_doctor_missing_requirement_pairs_match_release`
compares eight two-option cases against real Prodex and Modex processes. Both
run under the existing isolated sandbox with a synthetic HOME and workspace;
these parse-error cases create no files.

## Checks

- `make BUILD_DIR=/tmp/modex-offline-cli-166-build build` passed with Mojo 1.2.0.
- The focused test and all four tests in `test_inspection_cli_01660` passed.
- `python3 scripts/ci/check-product-dependencies.py` passed; production imports
  remain limited to Mojo standard-library and internal modules.

Reproduce the focused comparison after building Modex and providing verified
local binary paths:

```sh
MODEX_BINARY=/path/to/modex \
PRODEX_ORACLE=/path/to/prodex-0.166.0 \
PYTHONPATH=tests python3 -m unittest \
  test_inspection_cli_01660.InspectionCli01660Tests.test_doctor_missing_requirement_pairs_match_release
```

This covers the tested parse diagnostics only. It does not establish parity for
other `doctor` modes or the remaining release targets. An exploratory comparison
of 34 invalid two- and three-option orderings without `--runtime` found no
regressions against the prior Modex build and 11 remaining mismatches. A
separate probe found a three-option usage-order mismatch for
`doctor --runtime --suggest-policy --bundle`; it lacks `--redacted`, so both
processes stop at argument validation without running the doctor backend.
