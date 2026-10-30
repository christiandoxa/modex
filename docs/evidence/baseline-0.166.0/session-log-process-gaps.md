# Active 0.166.0 session and log process gaps

The pinned source is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Process checks use the verified
Linux oracle with SHA-256
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735` and
synthetic isolated homes.

## Log redaction

The source path for `log last --json` is `handle_log` in
`crates/prodex-app/src/app_commands/log_command_tui.rs`, then
`latest_transcript_event` and `transcript_safe_text` in
`crates/prodex-app/src/app_commands/log_transcript.rs`. It applies the
Prodex secret-like text redactor before rendering. Modex routes the same
command through `log_last` and `redact_log_text` in
`src/modex/logs.mojo` and `src/modex/log_redaction.mojo`.

The active comparison uses a synthetic `password=` message with a tab and
Unicode whitespace before a quoted sentinel. Prodex 0.166.0 retains the
sentinel suffix in its JSON log output. Modex masks the ambiguous suffix. This
is an intentional safety-preserving mismatch; matching this output would
expose the synthetic secret shape. No real credential or provider request is
used.

Reproduce after building Modex:

```sh
MODEX_BINARY="$PWD/build/modex" \
PRODEX_ORACLE="/home/doxa/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
python3 tests/test_active_baseline_01660.py \
  ActiveBaseline01660Tests.test_log_last_keeps_ambiguous_unicode_secret_tail_masked
```

## Session startup side effects

`session list --json` returns identical `[]` output and exit status in both
processes with an empty synthetic home. The active release also creates
`profile-lifecycle.json.lock` and `update-check.lock`; Modex creates only the
`.prodex` directory. Repeated observations also saw
`runtime-housekeeping.lock` and sometimes `runtime-housekeeping.last-run`;
housekeeping runs in a background thread, so those two files can race the
command exit.

The pinned source maps `Session` to the `Other` startup class in
`crates/prodex-app/src/command_dispatch.rs`. The Mojo startup policy in
`mojo/prodex_core/app_command_policy.mojo` enables update notice, profile
lifecycle recovery, and auto housekeeping for that class. Before dispatch,
`run_command` in `crates/prodex-app/src/lib.rs` performs the update check and
schedules housekeeping. The update checker acquires `update-check.lock`; the
housekeeping worker acquires `runtime-housekeeping.lock` and may write its
last-run stamp. During dispatch, `command_dispatch::execute_command` runs
`recover_pending_profile_lifecycle`, which acquires the profile lifecycle
lock before `handle_session` loads session reports. Modex `inspect_sessions`
creates its private root and reads state, but does not implement those startup
lock, update-check, and housekeeping actions. This is a real filesystem
mismatch; empty placeholder files would not implement the required lock or
recovery semantics, so this observation remains a gap rather than a partial
fix.

Reproduce after building Modex:

```sh
MODEX_BINARY="$PWD/build/modex" \
PRODEX_ORACLE="/home/doxa/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
python3 tests/test_active_baseline_01660.py \
  ActiveBaseline01660Tests.test_session_list_keeps_startup_file_gap_visible
```

These two Linux x86-64 cases characterize safe redaction and one session
startup path. They do not establish overall CLI, session, logging, security,
or six-target parity.
