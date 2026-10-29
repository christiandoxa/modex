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

For a valid ID, both releases proceed into managed runtime authorization. In
the isolated empty-home fixture they stop with “no active profile selected”;
Modex instead refuses before launching Codex because it has no managed resume
authorization/launch path. This is intentional fail-closed behavior: direct
Codex spawn would bypass profile ownership, auth selection, runtime management,
and the frozen metadata repair transaction. No Codex process, account login,
network access, or provider traffic is used by the tests.

The same fixtures show two retained state differences. Both releases ignore a
`state.json.lock` marker when the primary state file is absent, while Modex
fails closed before resolving the selector. With a private malformed
`state.json`, both releases fail state loading before checking either a
missing or valid ID, but their diagnostics differ. The stricter Modex behavior
is kept; it does not weaken locking or recovery guards.

Metadata repair, state database-only candidates, profile ownership checks,
and managed Codex launch remain unimplemented. The process comparisons cover
Linux x86-64 only and do not qualify any other release target.

Checks run in the detached `origin/main` worktree with Mojo 1.2.0:

```text
make build
mojo build -O3 --target-cpu=x86-64-v3 -I src tests/test_sessions.mojo -o build/tests/test_sessions
build/tests/test_sessions
PYTHONPATH=tests python3 -m unittest test_session_resume
PYTHONPATH=tests python3 -m unittest test_sessions test_session_report_01651
make ci-dependencies
python3 scripts/ci/check-test-census.py
python3 scripts/ci/run-unittest.py test_session_resume.py
```

The native session checks, five resume process tests, 28 listing/report tests,
and the production import audit passed. The test census found 50 native test
sources and 129 Python modules with one suite owner each. The strict-runner
invocation also passed. `test_session_resume.py` is in the active cross-release
Python shard in both `scripts/ci/run-fast.sh` and `scripts/ci/run-full.sh`.
