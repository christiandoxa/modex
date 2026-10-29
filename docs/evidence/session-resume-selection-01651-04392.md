# Session resume selection slice

The source traces for both frozen releases show the same production sequence:
`handle_session_resume` loads app state, repairs eligible rollout metadata,
checks whether a candidate is too incomplete to repair, resolves the session
report by exact or unique partial ID, then routes `codex resume <resolved-id>`
through the managed `handle_run` runtime. The 0.439.2 trace is at
`crates/prodex-app/src/app_commands/session.rs`; the 0.165.1 trace is at the
same path in the historical checkout. Their resolver delegates to
`prodex-session-store::resolve_session_report_by_id_in_store`, whose selector
planner checks case-insensitive exact matches before prefixes.

The Linux oracle SHA-256 values were checked before the test run:

- 0.165.1: `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
- 0.439.2: `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`

The production CLI now resolves IDs from the existing `session list --id-only`
session reader, preserving its app-state permission and lock checks. It matches
ASCII case-insensitively, prefers exact IDs over longer prefix candidates,
trims whitespace, and retains duplicate IDs so duplicate exact matches stay
ambiguous. Missing and ambiguous errors match both releases exactly. Synthetic
real-process controls cover uppercase IDs, ASCII and Unicode surrounding
whitespace, whitespace-only selectors, exact-versus-prefix precedence,
ambiguous prefixes, and duplicate IDs across active and archived session paths.

For a valid ID with no `state.json` and no shared-home `config.toml`, both
releases report that no profile is selected. Modex now matches that status and
diagnostic after the existing session/state guards pass. Side effects differ:
both releases create session repair and maintenance locks plus application
housekeeping files; Modex creates only the private application directory. A
shared-home config selected through `PRODEX_SHARED_CODEX_HOME` can provide a
profileless runtime; Modex keeps the managed-launch refusal when that config is
present. Synthetic state supplied through `PRODEX_HOME` also blocks the
no-profile fallback. With active-profile state, both releases update state and
create state/session locks before failing at Codex discovery under an empty
`PATH`. Modex retains its explicit managed-authorization refusal and leaves
that state unchanged. This is fail-closed behavior: direct Codex spawn would
bypass profile ownership, auth selection, state transactions, runtime
management, and metadata repair. No account login, network access, provider
traffic, or credentials are used by the tests. See
`docs/evidence/baseline-0.165.1/session-managed-resume.md` for the reproducible
status, output, environment, config, and filesystem comparisons.

The same fixtures show two retained state differences. Both releases ignore a
`state.json.lock` marker when the primary state file is absent, while Modex
fails closed before resolving the selector. With a private malformed
`state.json`, both releases fail state loading before checking either a
missing or valid ID, but their diagnostics differ. The stricter Modex behavior
is kept; it does not weaken locking or recovery guards.

Metadata repair, state database-only candidates, profile ownership checks,
and managed Codex launch remain unimplemented. The process comparisons cover
Linux x86-64 only and do not qualify any other release target.

The 2026-10-29 update rebuilt production Modex and ran
`python3 scripts/ci/run-unittest.py test_session_resume.py`; all 8 resume
process tests passed. `make ci-dependencies` passed for 71 Mojo files, and the
test census found 50 native test sources and 130 Python modules with one suite
owner each. Earlier native session and listing/report checks remain as
recorded at their run. `test_session_resume.py` is in the active cross-release
Python shard in both `scripts/ci/run-fast.sh` and `scripts/ci/run-full.sh`.
