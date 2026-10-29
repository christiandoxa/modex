# Session profile details in text output

## Frozen source trace

Prodex 0.165.1 at `10ae15b5d1806302b60f051e4e6fec788044f4c2` and the frozen
Prodex 0.439.2 at `72b77478a5198fc5da6b4d2253137f9cdbf43be9` both map
`SessionReport.profile` into `SessionReportDisplay.profile` in
`crates/prodex-app/src/reports/session.rs`. The terminal renderer marks any
`Some` profile as present, then prints `  profile: <name>` after the optional
full-ID line in `crates/prodex-terminal-ui/src/session.rs`. The renderer has no
control-character escaping. Its detail plan is in
`mojo/prodex_core/terminal_layout.mojo`.

## Process checks

`tests/test_session_profile_04392.py` compares production processes for both
release binaries and Modex with isolated homes, synthetic session files, and
synthetic state. Cases cover an absent binding, a bound empty profile name,
long mixed-width Unicode names at width 20, multiple rows, full-ID/profile
detail order, and private profile/binding state sentinels. Ordinary UTF-8
output matches both releases.

Both release binaries emit C0 and C1 profile controls directly, including LF,
ESC, NUL, TAB, CR, DEL, and U+0085. Modex escapes U+0000–U+001F and
U+007F–U+009F as lowercase `\xNN` in text details. This intentional safe
difference prevents newline injection and terminal escape sequences while
preserving other Unicode. Redirected output and the `CODEX_CI=1` pseudo-TTY
fallback both assert that profile control bytes do not reach Modex output. The
PTY harness converts line feeds to CRLF through its terminal output processing.

The tested binaries are the checksum-pinned Linux x86-64 releases:

- Prodex 0.165.1: `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
- Prodex 0.439.2: `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`

Validation with Mojo 1.2.0:

```text
make build
PYTHONPATH=tests python3 -m unittest -v test_session_profile_04392 test_session_text
```

The build succeeded and all 31 tests passed. This characterizes selected
Linux process behavior; it does not establish parity for other release
targets.
