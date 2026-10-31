# Prodex 0.166.2 native session-root resume

## Release behavior

The official `0.166.2` release notes say local interactive `prodex s <uuid>` resolves parent-owned native V2 workers to their verified root before provider/model selection. V1 direct resumes and independent forks keep their existing target. Missing, cyclic, ambiguous, or conflicting ancestry fails safely. The implementation is in the official source at tag commit `b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`; its `resolve_native_resume_target` reads persisted ancestry and its Super launcher changes only the resume-ID argv slot.

## Synthetic differential

Run:

```bash
make build
PRODEX_ORACLE_01662=/path/to/prodex-0.166.2 \
MODEX_BINARY="$PWD/build/modex" \
python3 tests/manual_session_root_01662.py
```

On 2026-10-31, the harness compared the local Prodex 0.166.2 binary (SHA-256 `e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`) with Modex built from `db16b2f8cca3580bb942ca5664d58b0118ea53ae`. The cases use synthetic root/worker IDs, isolated HOME and Prodex/Codex roots, bubblewrap network isolation, no credentials, and no Codex executable. Every command exited before launching Codex and left the entire fixture tree unchanged.

The complete captured outputs are in `session-root-resume-capture.json`.

| Case | Prodex 0.166.2 | Modex |
|---|---|---|
| V2 child with existing root | Resolves to root `01900000-0000-7000-8000-000000000710`, then reaches the expected no-profile guard | Stops at `Super startup is not implemented` |
| Root session | Keeps the root target; reaches the no-profile guard | Stops at `Super startup is not implemented` |
| V1 child | Keeps the child target; reaches the no-profile guard | Stops at `Super startup is not implemented` |
| V2 child with missing parent | Fails closed with `session parent metadata is missing; restore the parent session before resuming` | Stops at `Super startup is not implemented` |

This establishes the launcher mismatch and confirms the oracle's root/V1/fail-closed selection behavior. It does not establish native TUI resume parity: Modex has no connected native resume launch path, and the fixture intentionally has no profile or Codex binary. A resolver added without that path would be dead code, so no unused resolver was added.
