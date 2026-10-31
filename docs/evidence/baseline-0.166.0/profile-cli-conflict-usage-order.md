# Profile CLI conflict diagnostics (Prodex 0.166.0)

Reference: official Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. The verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

In the pinned `crates/prodex-cli/src/profile.rs`, `RemoveProfileArgs` makes
`--all` conflict with `[NAME]`, while `ExportProfileArgs` makes
`--password-protect` conflict with `--no-password`. The active process reports
conflict options in invocation order. Its usage preserves earlier options in
their invocation order; for an option-option conflict, usage omits the later
conflicting option. For `profile remove`, the `[NAME]` placeholder remains in
usage with `--all`.

Modex now builds those diagnostics from parsed options in the shared
`_profile_conflict` helper. A five-case real-process comparison covers both
`profile remove` option orders, both export option orders, and repeated
`-p/--profile` values before an export conflict. The commands return exit 2
before profile state is read or changed. Each process runs with synthetic
`HOME` and workspace through the existing isolated CLI harness; the test checks
that neither creates files.

Validation on Linux x86-64:

- `make BUILD_DIR=/tmp/modex-parity-slice-f-build build` passed with Mojo
  1.2.0.
- The new differential and three existing active profile/use parser methods
  passed: 4 tests in 1.417 seconds.
- `python3 scripts/ci/check-product-dependencies.py` passed.
- `git diff --check` passed.

Reproduce the focused active comparison after building Modex:

```sh
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
MODEX_BINARY=/tmp/modex-parity-slice-f-build/modex \
PYTHONPATH=tests PYTHONDONTWRITEBYTECODE=1 \
python3 -m unittest -v \
  test_active_baseline_01660.ActiveBaseline01660Tests.test_profile_conflict_diagnostics_preserve_option_order_and_usage_flags
```

This qualifies only the listed profile parser diagnostics. Profile listing,
selection, import, export, and removal execution remain unimplemented or
unqualified; no profile state or lock behavior changed.
