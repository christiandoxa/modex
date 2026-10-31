# Active 0.166.0 `log last --json` slice

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The pinned source at `9f69e1835808f478f59f12a3ae3fa88027d896a4` connects
`handle_log` in `crates/prodex-app/src/app_commands/log_command_tui.rs` to the
latest transcript, upstream payload and token usage events. Transcript text
passes through secret redaction and safe-text normalization in
`crates/prodex-app/src/app_commands/log_transcript.rs`.

`ActiveBaseline01660Tests.test_log_last_matches_synthetic_transcript_and_runtime_events`
compares real 0.166.0 and Modex processes using the checksum-verified Linux
oracle (`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`).
The bwrap fixture clears the environment, isolates HOME and the network, and
provides one synthetic session message plus one upstream payload and one token
usage record. The test checks exit status, stderr, exact JSON output, extracted
event fields, removal of a synthetic bearer token, unchanged session bytes, and
the observed `.prodex` directory-only side effect in both processes.

Reproduce from this checkout after building Modex:

```sh
MODEX_BINARY="$PWD/build/modex" \
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
python3 tests/test_active_baseline_01660.py \
  ActiveBaseline01660Tests.test_log_last_matches_synthetic_transcript_and_runtime_events
```

This qualifies only the tested Linux x86-64 snapshot projection and redaction
case. It does not qualify live logging, other record shapes, profile lifecycle,
the six release targets, or overall runtime parity. No credentials or provider
requests are used.

## Candidate window

In these fixtures, `log last` selects 32 recently modified session files or 32
runtime log files. `ActiveBaseline01660Tests.test_log_last_ignores_session_event_outside_32_candidate_window`
and `ActiveBaseline01660Tests.test_log_last_ignores_runtime_event_outside_32_candidate_window`
compare real processes against the verified oracle. Each private fixture has
33 ordered files, with its only readable event in the oldest file; both
processes return empty JSON output. Each test then moves that event into the
window and confirms the expected event is emitted. These cases qualify the two
file-window boundaries on Linux x86-64 only.

Reproduce after building Modex:

```sh
MODEX_BINARY="$PWD/build/modex" \
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
PYTHONPATH=tests python3 -m unittest \
  test_active_baseline_01660.ActiveBaseline01660Tests.test_log_last_ignores_session_event_outside_32_candidate_window \
  test_active_baseline_01660.ActiveBaseline01660Tests.test_log_last_ignores_runtime_event_outside_32_candidate_window
```
