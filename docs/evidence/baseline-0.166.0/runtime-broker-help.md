# Hidden runtime broker help

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

Prodex 0.166.0 at `9f69e1835808f478f59f12a3ae3fa88027d896a4` declares the
hidden `__runtime-broker` command with empty `RuntimeBrokerArgs`. Clap exposes
the same static help through `help __runtime-broker`, `--help`, and `-h`.
Modex already accepted the hidden command as a root help target, but then fell
through to its generic unimplemented-command error.

Modex now prints the matching usage for those help routes, formats extra
`help` operands as the release does, and reports the selected `--help=value`
parser error. It does not implement runtime broker startup; that command
remains fail-closed.

`tests/test_root_help_errors_01660.py::RootHelpErrors01660Tests.test_hidden_runtime_broker_help_matches_without_mutations`
compares the checksum-verified 0.166.0 Linux oracle and Modex in isolated
Bubblewrap processes with synthetic HOME and workspace directories. It covers
the help alias, both help flags, a custom executable name, an extra operand,
and an invalid attached help value. All cases leave the fixtures unchanged.

Validation on Linux x86-64: `make build` passed; the focused test passed; all
eight tests in `test_root_help_errors_01660` passed. This qualifies only this
static help surface; runtime broker behavior, other hidden helpers, other
release targets, and overall CLI parity remain unqualified.
