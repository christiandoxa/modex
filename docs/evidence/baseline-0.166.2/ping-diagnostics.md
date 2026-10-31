# Offline ping group diagnostics

The checksum-verified Prodex 0.166.2 Linux oracle and the production Modex
binary were compared with isolated synthetic homes and no provider traffic.
For `ping` without a subcommand (including a trailing `--`), both now print the
same group help to stderr and exit 2. Unknown long and short flags and unrecognized subcommands (including
suggestion and `--` cases) produce the same error, usage, and exit status. Neither process created state in the test.

For `ping openai`, first unknown options and positional arguments also match;
valid `--json` and `--profile` options remain behind Modex's unimplemented
operation guard. `tests/test_ping_diagnostics_01662.py` covers these cases. The existing
0.166.0 ping help regression also passed. This does not implement `ping openai`,
validate other argument combinations, or establish full ping parity.
