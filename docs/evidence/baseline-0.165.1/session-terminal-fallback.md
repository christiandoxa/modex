# Session terminal fallback against Prodex 0.165.1

In the frozen source at commit `10ae15b5d1806302b60f051e4e6fec788044f4c2`,
`crates/prodex-app/src/app_commands/session.rs` renders an inline terminal
view only when `try_inline_stdout_terminal` allows it. That helper in
`crates/prodex-app/src/app_commands/shared.rs` disables the inline view when
`CODEX_CI` is present or `PRODEX_TUI_STRICT` is truthy; `PRODEX_FORCE_TUI`
takes precedence. When the inline terminal cannot be created,
`render_session_reports_tui` writes the ordinary session report to stdout.

Modex previously failed every text-mode session command when stdout was a
terminal. The production path now uses the same environment gates and emits
the ordinary report for the two verified fallback cases. It keeps the error
for an ordinary TTY while interactive terminal rendering remains
unimplemented. The state-file guard still runs before output selection; a
synthetic `state.json.lock` without a primary state file remains fail-closed.

`tests/test_session_text.py` uses real pseudo-terminals, isolated homes and
synthetic session data. It compares raw stdout, stderr and exit status against
both pinned Linux binaries for `CODEX_CI=1`, an empty-but-present `CODEX_CI`,
and truthy `PRODEX_TUI_STRICT`. False and unset strict controls retain
Modex's ordinary-TTY error, and a separate case verifies that the fallback
does not bypass the state guard.

- Prodex 0.165.1: SHA-256 `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.
- Prodex 0.439.2: SHA-256 `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

Validation passed with Mojo 1.2.0 on Linux x86-64:

```text
make build
python3 scripts/ci/run-unittest.py test_session_text.py
PYTHONPATH=tests python3 -m unittest -v test_session_report_01651
PYTHONPATH=tests python3 -m unittest -v test_session_text.SessionTextTests.test_table_columns_truncation_and_full_ids test_session_text.SessionTextTests.test_empty_panels_and_wrapping test_sessions.SessionOutputTests.test_populated_json test_sessions.SessionOutputTests.test_filters_limits_and_machine_output_modes
make ci-dependencies
python3 scripts/ci/check-test-census.py
```

The complete 16-test text suite and all 15 inherited/0.165.1 report tests
passed. The import audit passed for 71 Mojo files; the test census found 50
native test sources and 129 Python modules with one suite owner each. This
does not implement the interactive TUI or qualify non-Linux targets.
