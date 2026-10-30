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

## Post-`exec` parsing

The 0.165.1 runtime tail parser in
`crates/prodex-cli/src/runtime_args/super_tail_extract.rs` splits reminder
values on commas and maps any invalid unsigned element to
`expected comma-separated unsigned integers`. Pinned 0.439.2 process checks
produce the same runtime diagnostic. Modex now maps parse failures to that
message only after the positional `exec` command; valid integers still pass
through the existing parser unchanged.

`tests/test_super_cli.py::SuperCliTests.test_positional_rollout_budget_reminder_error_preserves_state_effects`
compares empty and nonnumeric elements across both references and Modex. It
asserts no Codex launch, provider request, or leftover overlay. The references
create `profile-lifecycle.json.lock` and `runtime-housekeeping.lock`; 0.165.1
also creates its Codex-aligned update cache. Housekeeping may create
`runtime-housekeeping.last-run`. Modex continues to create no locks and retains
its existing startup guard for valid post-`exec` values. A valid `1,2` control
confirms both references pass the same reversed reminder list to Codex.
One initial combined-worktree run failed the required-artifact assertion for
both invalid cases without recording which path was missing. The assertion
now includes the binary and observed paths; 21 repeated runs and the final
full Super CLI module passed. The original failure remains unexplained and
hosted stability is not established.

Linux x86-64 validation with Mojo 1.2.0:

- `rtk make build BUILD_DIR=/tmp/modex-parity-session-build-20261030` — passed.
- `python3 scripts/ci/run-unittest.py test_super_cli.py` — 9 passed.
- `rtk python3 scripts/ci/check-product-dependencies.py` — 71 Mojo files passed.
- `rtk python3 scripts/ci/check-test-census.py` — 50 native sources and 155 Python modules have one suite owner.
- `git diff --check` — passed.

These checks qualify only the listed pre-command and post-`exec` reminder
diagnostics and the observed side effects on Linux x86-64. Other typed-value
edge cases, complete Super launch behavior, and the other release targets
remain unqualified.
