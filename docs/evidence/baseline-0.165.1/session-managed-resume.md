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
credentials. The comparisons cover Linux x86-64 only. They do not establish
managed launch, state-lock parity, metadata-repair parity, interactive TUI
parity, or support for the other five release targets. All six targets remain
in the parity denominator.

Validation on 2026-10-29 with Mojo 1.2.0:

```text
make build
python3 scripts/ci/run-unittest.py test_session_resume.py
make ci-dependencies
python3 scripts/ci/check-test-census.py
```

The production build passed. All 8 session-resume process tests passed against
the pinned 0.165.1 and 0.439.2 Linux oracles. The production import audit
passed for 71 Mojo files; the test census found 50 native test sources and 130
Python modules with one suite owner each.
