# Current work

The destination repository began empty. The frozen tag and official Linux
release checksum have been verified. Reference source and the oracle are kept
outside the Modex source and build graph, under `~/.cache/modex/`.

The current bootstrap implements product version output. It passes isolated
official-release differential checks with the narrow documented identity
mapping. A clean filesystem/network namespace contains only Modex and the
platform/official Mojo runtime libraries; version output works without Python,
Node, Rust, or Prodex. Native JSON decoding and development `session list` /
`session current` machine-output paths are connected to the production binary.
The inventory contains 59 coarse contracts and 354
platform obligations; 1 Linux obligation passes, and 0 complete cross-platform
contracts pass. Inventory expansion remains necessary; no parity percentage is
valid.

Validation: `make test` (2 Mojo unit programs and 11 Python black-box/runtime
tests PASS), `python3 tests/probe_capabilities.py` (3 positive programs PASS,
4 expected public-API gaps reproduced). `python3 tests/session_mismatches.py`
retains 3 FAIL cases and one unapproved safe difference for a baseline panic.
Actual compiler diagnostics and commands are in `docs/evidence/capabilities/`.

Next work: close session argument and text-rendering gaps, expand adversarial
JSON checks, and evaluate official stdlib mechanisms for lock/recovery and
protected file handling. Current stateful, compressed, and local numeric-time
paths fail explicitly. Startup effects still differ. Details and the baseline
panic are in `docs/known-gaps.md`; no session contract is PASS.

Mojo's public process API has no stdio-redirection, process-group, or
environment-isolation options. Its networking package currently exposes only
internal building blocks. The official stdlib source at the pinned release
must be checked before interpreting missing public APIs as impossible native
implementations. No dependency exception has been introduced.

Native Windows and Intel macOS are not supported by the pinned compiler's
documented platform contract. Linux glibc and CPU minimums are stricter than
the baseline release. These obligations remain in scope as platform gaps.
