# Super rollout reminder element diagnostics

Prodex 0.165.1 source commit `10ae15b5d1806302b60f051e4e6fec788044f4c2`
declares `--rollout-budget-reminders` as `Vec<u64>` with Clap's
`value_delimiter = ','` in `crates/prodex-cli/src/runtime_features.rs`.
Clap parses each comma-separated value independently and identifies the
invalid element in its diagnostic.

Modex dispatches `super` to `parse_super_arguments` in `src/main.mojo`. Its
pre-command parser validates each reminder element in
`src/modex/super_cli.mojo`; it now uses that element for the diagnostic as well
as integer parsing. Previously it parsed each element but reported the whole
input string.

`tests/test_super_cli.py::SuperCliTests.test_rollout_budget_reminders_identify_the_invalid_element`
compares production processes for 0.165.1, 0.439.2, and Modex with isolated
homes. It covers empty middle, first, and last elements, plus a nonnumeric
middle element. For example, `--rollout-budget-reminders=1,,2 --help` now
reports `invalid value ''` in all three processes. These parser failures create
no additional filesystem state and make no provider request.

Linux x86-64 validation with Mojo 1.2.0:

- `rtk make build BUILD_DIR=/tmp/modex-parity-session-build-20261030` — passed.
- `python3 scripts/ci/run-unittest.py test_super_cli.py` — 8 passed.
- `rtk python3 scripts/ci/check-product-dependencies.py` — 71 Mojo files passed.
- `rtk python3 scripts/ci/check-test-census.py` — 50 native sources and 155 Python modules have one suite owner.
- `git diff --check` — passed.

This qualifies only the listed pre-command parser diagnostics. Post-`exec`
runtime behavior, other typed-value edge cases, and the other release targets
remain unqualified.
