# Super missing option values against 0.165.1

`tests/test_cli_01651.py` compares real Prodex 0.165.1 and Modex processes in
isolated homes. Each pre-positional missing-value case exits before creating
application state. The pinned Linux oracle SHA-256 is
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

This qualifies selected Super CLI diagnostics on Linux x86-64. It does not
establish full CLI parity. A negative integer value such as
`--context-window -1` remains different: Prodex exits 2 with a Clap invalid
value diagnostic, while Modex exits 1 with `Error: invalid digit found in
string`. Other typed-value diagnostics and the remaining release targets are
unqualified.
