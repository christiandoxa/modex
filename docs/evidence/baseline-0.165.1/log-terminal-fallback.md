# Log follower terminal fallback (2026-10-30)

## Release trace

The pinned 0.165.1 source commit is
`10ae15b5d1806302b60f051e4e6fec788044f4c2`; frozen 0.439.2 is
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. At both commits, `log stream`
dispatches to `stream_token_usage_events` in
`crates/prodex-app/src/app_commands/log_command_tui.rs`, while `log upstream`
dispatches to `stream_upstream_payload_events` in
`crates/prodex-app/src/app_commands/log_upstream.rs`. Both select interactive
terminal rendering only when JSON is off, `NO_COLOR` is absent, and both stdout
and stdin are terminals. `NO_COLOR` is checked by environment-variable
presence; stderr does not select these TUIs. The relevant source files are
identical at both commits.

The Linux x86-64 release executables were verified by SHA-256:

- Prodex 0.165.1: `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
- Prodex 0.439.2: `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`

## Process checks

`tests/test_log_tty_fallback.py` compares isolated follower processes for both
commands across 0.165.1, 0.439.2, and Modex. Its plain-path cases cover:

- stderr-only TTY with `NO_COLOR` absent;
- stdout-only TTY with `NO_COLOR` absent;
- stdin-only TTY with `NO_COLOR` absent;
- stdin and stdout TTYs with `NO_COLOR` present.

For each case, all three processes produce matching results and the fixture
payload. With stdin and stdout attached to a controlling PTY and `NO_COLOR`
absent, both releases enter and restore the alternate screen, hide and restore
the cursor, and exit cleanly after `q`. Modex exits with its explicit
unsupported-TUI error. A synthetic live runtime registry continues to fail
closed before following the file fixture.

## Verification

- `make build` passed.
- `python scripts/ci/run-unittest.py test_log_tty_fallback.py test_log_stream.py test_log_upstream_follow.py test_log_stream_escaped_event_01651_04392.py test_log_upstream_selection_01651_04392.py` passed 15 tests.
- `python scripts/ci/run-unittest.py test_ci_oracle_routing.py` passed 9 tests.
- `python scripts/ci/check-product-dependencies.py` passed for 71 Mojo files.
- `python scripts/ci/check-test-census.py` found one suite owner for each of 50 native test sources and 151 Python modules.
- `git diff --check` passed.

Interactive TUI rendering and live runtime registries remain unsupported in
Modex. These checks qualify only Linux x86-64 behavior and do not change parity
statuses or the six-target denominator.
