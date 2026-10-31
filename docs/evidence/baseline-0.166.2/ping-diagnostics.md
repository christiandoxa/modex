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
`--foo=x`. After option syntax succeeds, empty and whitespace-only `--model`
values and C0, DEL, or C1 control characters return Prodex's
`Error: --model must be nonempty and contain no control characters` with exit
1. Help and option-syntax errors keep their earlier precedence. Nonempty model
values without control characters still reach Modex's guarded operation error;
the operation remains unimplemented and no provider request or state change is
made. `tests/test_ping_diagnostics_01662.py` covers both boundaries against the
pinned oracle.
