# Offline ping group diagnostics

The checksum-verified Prodex 0.166.2 Linux oracle and the production Modex
binary were compared with isolated synthetic homes and no provider traffic.
For `ping` without a subcommand (including a trailing `--`), both now print the
same group help to stderr and exit 2. Unknown long and short flags and unrecognized subcommands (including
suggestion and `--` cases) produce the same error, usage, and exit status. Neither process created state in the test.

For `ping openai`, first unknown options and positional arguments also match;
missing values for `--profile`/`-p`, `--model`, `--effort`, and `--base-url`
match, as do duplicate value options and duplicate `--json`/`--no-proxy` flags.
These parse errors exit 2 without creating files. Valid `ping openai` invocations
remain behind Modex's unimplemented-operation guard and make no provider request.
`tests/test_ping_diagnostics_01662.py` covers these cases against the pinned
oracle. The existing 0.166.0 ping help regression also passed. This does not
implement `ping openai`, validate other argument combinations, or establish
full ping parity.

Arguments after `--` are reported literally, including values such as
`--foo=x`. Empty `--model` values (`--model ""` and `--model=`) reach a later
Prodex validation step and return `Error: --model must be nonempty and contain
no control characters` with exit 1. Modex remains behind its generic operation
guard for these inputs, so this semantic validation is a recorded mismatch,
not part of the parser slice.
