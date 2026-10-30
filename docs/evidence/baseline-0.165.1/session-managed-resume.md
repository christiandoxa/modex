# Managed session resume boundary

Prodex 0.165.1 at `10ae15b5d1806302b60f051e4e6fec788044f4c2` handles
`session resume` in `crates/prodex-app/src/app_commands/session.rs`. It loads
application state, repairs eligible rollout metadata, resolves the selected
session report, then routes `codex resume <resolved-id>` through the managed
runtime launch path. The pinned Linux oracle is verified by
`reference-verification.json` and the checksum assertion in
`tests/test_session_resume.py`.

Modex now matches the release status and diagnostic when a valid session ID is
selected, application `state.json` is absent, and the selected shared Codex
home has no `config.toml`. Existing session/state guards run before this
branch. Any shared-home config keeps the managed-launch refusal because
Prodex can select a profileless runtime from config. The branch does not launch
Codex. On a synthetic empty home with a prefix-collision session, both release
oracles create
`home/.codex/.prodex-session-repair.lock`,
`home/.codex/sessions/.prodex-maintenance.lock`, a repair backup, and several
`home/.prodex` housekeeping files. Modex creates only the private
`home/.prodex` directory. This lock, repair, and housekeeping mismatch remains
open.

A second control supplies synthetic active-profile state and a session binding
through both the default app root and an explicit `PRODEX_HOME`, with no
credentials and an empty `PATH`. Both release oracles update state, create
`state.json.lock`, state backup and session locks, then fail at Codex discovery.
Modex returns `Error: session resume requires managed profile authorization and
launch, which are not implemented`; its state file remains byte-identical and
it creates no lock files. The Modex refusal stays in place because it has no
managed resume authorization, state transaction, metadata repair, or runtime
launch path. Directly spawning Codex would skip those controls.

Shared-home config controls cover the default `$HOME/.codex` path, an absolute
`PRODEX_SHARED_CODEX_HOME`, and a relative override resolved under `PRODEX_HOME`.
Each synthetic `config.toml` selects `prodex-deepseek`. Both releases detect
that profileless provider and reach Codex discovery; Modex preserves its
managed-launch refusal. No API key is supplied and the network is unshared.
This prevents the no-state diagnostic from masking a profile source outside
`state.json`.

The process fixtures use temporary HOME, synthetic session JSONL and state,
`bwrap --unshare-all`, empty `PATH`, and no account login, provider traffic, or
credentials. New real-process controls also move a synthetic rollout outside
the session tree and replace its original path with a symlink. Prodex 0.165.1,
0.439.2, and Modex all ignore the symlink and report the selector as unresolved;
the link and its target remain unchanged.

A separate control points `state.json` at a valid synthetic state file through
a symlink. Both releases reject it with a symlink-specific diagnostic and
leave the target and link unchanged, but create
`profile-lifecycle.json.lock`, `runtime-housekeeping.lock`, `state.json.lock`,
and `update-check.lock` before failing. Modex also rejects it and leaves both
paths unchanged, before creating any lock files. The safety result matches;
the diagnostic and side effects do not, so this is not counted as parity.

The official Mojo 1.2.0 stdlib cannot express the baseline's safe repair
transaction: `std.sys._libc` does not export `flock` or `fsync`,
`FcntlCommands` has no `F_SETLK`, `FileHandle` has neither `flush` nor
`sync_all`, `std.os` and `std.os.path` expose no atomic rename/replace, and
`std.sqlite` is unavailable. The baseline's `SessionRepairTransaction` uses
`File::lock`, identity checks, an exclusive private backup, atomic replacement,
file sync, and parent-directory sync; resume resolution also consults the
Codex state database. A `mkdir` marker or guessed `fcntl` command would not
coordinate with Prodex's `flock` users, and a plain write would not preserve
the transaction's crash-safety. Under the current stdlib-only rule, the safe
next implementation step is to add these primitives to the official Mojo
stdlib, including SQLite access, before porting the state load/recovery and
session repair transactions. Then connect report/state-database resolution to
managed profile selection and runtime launch, and verify with synthetic
concurrent-process, crash-recovery, symlink, hard-link, and compressed-session
fixtures. No Codex stub or replacement TUI was used here.

These comparisons cover Linux x86-64 only. They do not establish managed
launch, state-lock parity, metadata-repair parity, interactive TUI parity, or
support for the other five release targets. All six targets remain in the
parity denominator.

Validation on 2026-10-29 with Mojo 1.2.0:

```text
make build BUILD_DIR=/tmp/modex-session-recovery-build
MODEX_BINARY=/tmp/modex-session-recovery-build/modex \
  PRODEX_ORACLE_01651=/home/test-user/.cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu \
  python3 -m unittest test_session_resume
make ci-dependencies
python3 scripts/ci/check-test-census.py
```

The production build passed. All 10 session-resume process tests passed,
including the new symlinked rollout and state controls against the pinned
0.165.1 and 0.439.2 Linux oracles. The stdlib limitation probes were temporary
Mojo files under `/tmp`; they are not product or test dependencies.
