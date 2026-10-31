# Quota CLI diagnostic precedence

The connected quota help parser now matches selected offline diagnostics from
Prodex 0.166.2. A malformed `--help=value` takes precedence over a pending
split option value. When an earlier option was accepted, error usage includes
the release's full quota option group; an invalid attached boolean still wins
over a later malformed help value.

`tests/test_quota_cli_diagnostics_01662.py` compares six parser cases and three
help controls with the checksum-pinned Linux x86-64 oracle
(`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`). The
synthetic homes contain no profiles or credentials. The process sandbox has no
network, and all tested parser/help invocations leave the fixture tree
unchanged. The suite is registered in Fast and Full CI. The separate
`test_quota_help_history_04392.py` preserves the three historical help routes
against Prodex 0.439.2 (`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`).

This qualifies only the listed parser diagnostics and help routes. Quota
execution remains guarded. In a separate synthetic probe, `quota --profile=`
reached Prodex's stateful profile lookup, which acquired lifecycle and
housekeeping locks before reporting the empty profile as missing. Modex keeps
its unsupported-command guard; no profile lookup or lock bypass was added
because Mojo 1.2.0's standard library does not provide the required lifecycle
lock contract.
