# Quota CLI diagnostic precedence

The connected quota help parser now matches selected offline diagnostics from
Prodex 0.166.2. A malformed `--help=value` takes precedence over a pending
split option value. When an earlier option was accepted, error usage includes
the release's full quota option group; an invalid attached boolean still wins
over a later malformed help value.

`tests/test_quota_cli_diagnostics_01662.py` compares the existing six parser
cases and three help controls with the checksum-pinned Linux x86-64 oracle
(`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`). An
independent parser-safe argument sweep found a precedence mismatch when a
missing split value was followed by a malformed attached boolean option. The
production parser now reports that option's attached-value error, matching the
release. A generated 60-case matrix covers all five value-taking quota switches
against six malformed no-value switches, both with and without an earlier
accepted option; two ordinary missing-value cases guard the adjacent behavior.
Every invocation exits during parsing and leaves the synthetic home unchanged.
Three Modex-only valid-option controls also confirm quota requests still stop at
the no-state execution guard; these are safety checks, not parity evidence.

A follow-up 24-case matrix matches malformed `--help=value` usage for all
quota value-taking options in split and attached forms, including empty
attached values and both `-p` forms, plus all five boolean options, missing
split values, and multi-option controls. A lone split value option
(`--profile NAME`, `-p NAME`, `--auth AUTH`, `--provider NAME`, or
`--base-url URL`) produces `Usage: modex quota --help`; attached values,
boolean options, or another accepted option retain the option-group usage.
The pending-value control still retains the group, as in
`--profile NAME --provider --help=value`. Every case checks exact status,
stdout, stderr, and absence of filesystem changes against the release.

The synthetic homes contain no profiles or credentials, and the sandbox has no
network. The suite is registered in Fast and Full CI. The separate
`test_quota_help_history_04392.py` preserves the three historical help routes
against Prodex 0.439.2 (`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`).

Verified on 2026-10-31 with `make build` and the active quota diagnostic suite;
all five test methods passed on Linux x86-64. The focused test command was:

```sh
PRODEX_ORACLE=/path/to/prodex-0.166.2 \
MODEX_BINARY="$PWD/build/modex" \
python3 scripts/ci/run-unittest.py test_quota_cli_diagnostics_01662.py
```

This qualifies only the listed parser diagnostics and help routes. Quota
execution remains guarded. In a separate synthetic probe, `quota --profile=`
reached Prodex's stateful profile lookup, which acquired lifecycle and
housekeeping locks before reporting the empty profile as missing. Modex keeps
its unsupported-command guard; no profile lookup or lock bypass was added
because Mojo 1.2.0's standard library does not provide the required lifecycle
lock contract.
