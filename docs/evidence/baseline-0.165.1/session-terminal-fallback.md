# Session terminal output against Prodex 0.165.1 and 0.439.2

## Baseline trace

In frozen 0.165.1 source commit `10ae15b5d1806302b60f051e4e6fec788044f4c2`,
`crates/prodex-app/src/app_commands/session.rs` selects an inline terminal
view when stdout is a TTY and `try_inline_stdout_terminal` succeeds. The helper
in `crates/prodex-app/src/app_commands/shared.rs` disables that view when
`CODEX_CI` is present or `PRODEX_TUI_STRICT` is truthy; `PRODEX_FORCE_TUI`
takes precedence. If the inline terminal cannot be created, the command prints
the ordinary session report.

Frozen 0.439.2 source commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9` follows the same production path:
`crates/prodex-app/src/app_commands/session.rs` dispatches terminal output to
`render_session_reports_tui`, which uses the inline TUI when it can create a
terminal and otherwise writes the plain report.

## Modex behavior

Default `session list` text output now always uses Modex's existing plain
report renderer, including on a TTY. This removes the previous terminal error
without changing session scanning, state validation, or report formatting.
The report path remains read-only and escapes control characters in profile
names.

With a fully attached PTY, both release binaries render the interactive
`Prodex Sessions` screen and wait for a key. Modex prints its plain report and
exits. This is a safe output fallback, not interactive TUI parity; scrolling,
selection, keyboard navigation, and the release screen layout remain
unimplemented. When the inline TUI is disabled or cannot start, the tested
fallback output still matches both releases exactly. The state-file guard runs
before output selection, so the fallback does not bypass it.

## Reproduction

`tests/test_session_text.py` uses isolated homes and synthetic session data.
Its attached-PTY case answers the release cursor-position query and sends `q`
after the screen is drawn. It checks the two release screens against each
other and separately checks that Modex returns a successful plain report.
Other process cases compare fallback stdout, stderr, and exit status against
both references for `CODEX_CI=1`, an empty-but-present `CODEX_CI`, truthy
`PRODEX_TUI_STRICT`, and TTY stdout with non-TTY stdin. Synthetic profile
control characters remain escaped, and a synthetic held state lock still
fails closed before the report is written.

- Prodex 0.165.1: SHA-256
  `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.
- Prodex 0.439.2: SHA-256
  `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

Validation on Mojo 1.2.0, Linux x86-64:

```text
rtk make build
PYTHONPATH=tests MODEX_BINARY=build/modex python3 -m unittest -v test_session_text
rtk make ci-dependencies
```

The 17-test session-text suite passed. The production import audit passed for
71 Mojo files, all using standard-library or internal imports. Interactive TUI
parity remains incomplete; the other five release targets remain unqualified.
