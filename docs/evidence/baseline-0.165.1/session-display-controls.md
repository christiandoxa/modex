# Safe session text rendering

## Frozen source trace

Prodex 0.165.1 at `10ae15b5d1806302b60f051e4e6fec788044f4c2` maps session
IDs, timestamps, thread names, working directories, profile names, and paths
directly into `SessionReportDisplay` in
`crates/prodex-app/src/reports/session.rs`. The text table passes those values
to `pad_cell` and writes the full ID and profile details directly in
`crates/prodex-terminal-ui/src/session.rs`. The empty `session current` panel
also receives the requested directory as a raw string. The same rendering
path exists in frozen Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`.

## Modex behavior

The human-readable session table, full-ID and profile details, and the empty
`session current` panel now render C0 and C1 control characters as lowercase
`\xNN`. This prevents newlines and terminal escape sequences in session
metadata or `--cwd` from changing the terminal display. Ordinary Unicode,
column widths, and truncation are unchanged. JSON, `--id-only`,
`--resume-command`, selector matching, and session storage remain unchanged.

The pinned releases emit these controls raw. The escaped output is an
intentional safety difference and is not counted as parity. Machine-output
modes preserve exact identifier bytes; consume those modes as data rather than
displaying their output in a terminal.

## Reproduction

`tests/test_session_text.py::SessionTextTests.test_untrusted_session_controls_are_escaped_in_text`
runs the pinned Linux 0.165.1 and 0.439.2 binaries and Modex with synthetic
JSONL fields containing all C0/C1 controls, a control-bearing filename, and a
control-bearing `--cwd`. At widths 1, 20, 110, and 300, Modex emits no raw
control characters in human-readable output; the wide case checks each
`\xNN` mapping, while the pinned releases emit the original control bytes.
The fixtures use isolated homes and no credentials or provider traffic.

The tested Linux x86-64 binaries are checksum-pinned:

- Prodex 0.165.1: `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
- Prodex 0.439.2: `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`

On Mojo 1.2.0, the production build passed. The focused session report,
profile, state, text, and CLI suites passed 68 tests; Unicode query and resume
selection suites passed 13 more. The 71-file production import audit, test
census, and `git diff --check` passed.

This does not establish interactive TUI parity or qualify the other five
release targets.
