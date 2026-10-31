# Prodex 0.166.2 native session-root resume

## Release behavior

The official `0.166.2` release notes say local interactive `prodex s <uuid>` resolves parent-owned native V2 workers to their verified root before provider/model selection. V1 direct resumes and independent forks keep their existing target. Missing, cyclic, ambiguous, or conflicting ancestry fails safely. The implementation is in the official source at tag commit `b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`; its `resolve_native_resume_target` reads persisted ancestry and its Super launcher changes only the resume-ID argv slot.

The resolver also includes matching rollout paths found through read-only
`state_*.sqlite` `threads(id, rollout_path)` rows, in addition to walking
`sessions/` and `archived_sessions/`. The fifth synthetic case below keeps both
session files under a separate `indexed/` directory and reaches them only
through that SQLite index.

## Synthetic differential

Run:

```bash
make build
PRODEX_ORACLE_01662=/path/to/prodex-0.166.2 \
MODEX_BINARY="$PWD/build/modex" \
python3 tests/manual_session_root_01662.py
```

On 2026-10-31, the harness compared the local Prodex 0.166.2 binary (SHA-256 `e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`) with Modex built from `c27389af279945075b59f3e756a0b9529c16773f`. The cases use synthetic root/worker IDs, isolated HOME and Prodex/Codex roots, bubblewrap network isolation, no credentials, and no Codex executable. Every command exited before launching Codex and left the entire fixture tree unchanged.

The complete captured outputs are in `session-root-resume-capture.json`.

| Case | Prodex 0.166.2 | Modex |
|---|---|---|
| V2 child with existing root | Resolves to root `01900000-0000-7000-8000-000000000710`, then reaches the expected no-profile guard | Stops at `Super startup is not implemented` |
| Root session | Keeps the root target; reaches the no-profile guard | Stops at `Super startup is not implemented` |
| V1 child | Keeps the child target; reaches the no-profile guard | Stops at `Super startup is not implemented` |
| V2 child with missing parent | Fails closed with `session parent metadata is missing; restore the parent session before resuming` | Stops at `Super startup is not implemented` |
| V2 child indexed outside session directories | Finds the root through a read-only `state_*.sqlite` row, then reaches the no-profile guard | Stops at `Super startup is not implemented` |

The indexed case confirms that the SQLite fallback is observable: the release resolves root and child files stored outside its normal session directories, while Modex does not. This path remains unimplemented under the Mojo standard-library-only constraint; the current Modex guard remains in place. These comparisons establish selected root/V1/fail-closed behavior, not native TUI resume parity: the fixtures intentionally have no profile or Codex binary.
