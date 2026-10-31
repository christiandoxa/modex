# Modex development rules

- Write all new project content and communication in English. Preserve exact
  baseline strings, compatibility identifiers, user content, and multilingual
  test inputs when required for compatibility.
- Implement the product in Mojo 1.2.0 (2016d0cd), using only its official standard
  library. No third-party application libraries, new native bindings, Python
  interop, external implementation helpers, or Prodex runtime delegation.
- Python standard library is allowed only in separate complex test harnesses.
  Production builds must not depend on Python test code or code generation.
- The active reference is officially released Prodex 0.166.2 at
  `b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`. Prodex 0.166.1, 0.166.0, 0.165.1 and
  0.439.x are historical regression references only. Inspect Git objects or
  an isolated snapshot outside this repository. Never modify the Prodex repository.
- Keep all six baseline release targets in the parity denominator. Unsupported
  compiler targets and unverified security behavior remain visible gaps.
- Trace the baseline, implement a complete slice, connect its production path,
  test it, audit dependencies, and update evidence. Compile-only checks and mocks
  of Modex itself do not establish parity.
- Never use real credentials, paid provider traffic, or account login in tests.
  Isolate HOME, environment, config, storage, and ports using synthetic fixtures.
- Regular development commits and normal pushes to
  `https://github.com/christiandoxa/modex.git` on `main` are authorized. Review
  explicit staged paths, run focused checks, update evidence, push, and verify
  the remote commit. Never force-push, rewrite published history, publish a
  release, or create release tags without separate authorization.
- Never count incomplete inventory or successful assertions as full parity.
  Record unfinished work and reproducible mismatches in `docs/handoff.md`.
- Use GPT-6.1 Sol at MAX effort for primary implementation work and GPT-6 Luna
  subagents at MAX effort in parallel for independent implementation,
  validation, and review tasks. Assign workers concrete code and test changes.
  Keep file ownership disjoint; integrate and verify the combined result
  before committing or pushing.
