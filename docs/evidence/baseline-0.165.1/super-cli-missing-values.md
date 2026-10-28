# Super parser diagnostics against 0.165.1

`tests/test_cli_01651.py` compares real Prodex 0.165.1 and Modex processes in
isolated homes. The same focused cases in `tests/test_cli.py` use historical
0.439.2. Each parser-only case exits before creating application state. The
pinned Linux oracle SHA-256 is
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.

Before the fix, Prodex exited 2 with Clap's `a value is required for
'--option <VALUE>'` diagnostic. Modex exited 1 with `Error: --option requires
a value`. Production Modex now returns the pinned diagnostic for all 27 value
option spellings tested, including `-p`, `--local-model`,
`--local-context-window` and `--local-auto-compact-token-limit`.

The process comparisons also cover a missing value followed by another option,
`--help` or `-h`; an explicit empty provider value; a dash-prefixed provider
value; and help/error ordering. Empty and dash-prefixed values remain values,
not missing-value cases. The same missing-value and boundary controls pass
against historical 0.439.2. No credentials or upstream requests are used.

After the positional `exec` tail starts, the references instead report
runtime-style exit-1 errors and create Prodex lock state. Modex retains its
pre-existing exit-1 parser errors without state mutations. For
`super exec --model --help`, Prodex reaches startup and reports no active
profile, while Modex reports that Super startup is unimplemented. These
post-tail outcomes are captured against both releases and remain incomplete
runtime/state parity.

## Unsigned values

The pinned Prodex source at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
declares context and auto-compact limits as `usize` options in
`crates/prodex-cli/src/runtime_args/launch_args.rs`; rollout and current-time
limits are `u64` fields in `crates/prodex-cli/src/runtime_features.rs`.
Modex now returns the matching
Clap invalid-value diagnostic before positional `exec` for negative values on
`--context-window`, `--auto-compact-token-limit`, `--rollout-budget-tokens`,
`--rollout-budget-reminders` and `--current-time-reminder-interval`, including
the local context and auto-compact aliases. Tests compare exit, stdout,
stderr and filesystem mutations against 0.165.1 and historical 0.439.2.

Boundary controls cover zero, U64 max and `+1` as accepted values, attached
values and aliases, overflow and whitespace errors, and help ordering. Valid
values are followed by help to isolate parsing from later required-option
validation; each output is compared with that executable's own help control.
These controls create no state. After positional `exec`,
`--context-window -1` still follows the pre-existing exit-1 runtime parser
path: Prodex creates its lock files and Modex creates none.

This qualifies selected Super CLI diagnostics on Linux x86-64; it does not
establish full CLI parity. The custom `--sub-agent-max-concurrency` parser is
covered separately in
`docs/evidence/baseline-0.165.1/super-sub-agent-concurrency.md`. Other typed
and ranged value diagnostics and the remaining release targets are
unqualified.
