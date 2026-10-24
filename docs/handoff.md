# Current work

The destination repository began empty. The frozen tag and official Linux
release checksum have been verified. Reference source and the oracle are kept
outside the Modex source and build graph, under `~/.cache/modex/`.

The current bootstrap implements product version output. It passes isolated
official-release differential checks with the narrow documented identity
mapping. A clean filesystem/network namespace contains only Modex and the
platform/official Mojo runtime libraries; version output works without Python,
Node, Rust, or Prodex. Other commands fail explicitly. This is not a completed
feature implementation. The inventory contains 59 coarse contracts and 354
platform obligations; 1 Linux obligation passes, and 0 complete cross-platform
contracts pass. Inventory expansion remains necessary; no parity percentage is
valid.

Validation: `make build`, `python3 tests/probe_capabilities.py` (3 positive
programs PASS, 4 expected public-API gaps reproduced), and
`python3 -m unittest discover -s tests -p 'test_*.py' -v` (3 tests PASS).
Actual compiler diagnostics and commands are in `docs/evidence/capabilities/`.

Next slice: implement native Mojo JSON parsing and session inspection, connect
the production CLI, and compare populated/empty/malformed/filtered fixtures
with the official release. Preserve startup side effects and state validation;
do not claim an output-only comparison proves the complete session contract.

Mojo's public process API has no stdio-redirection, process-group, or
environment-isolation options. Its networking package currently exposes only
internal building blocks. The official stdlib source at the pinned release
must be checked before interpreting missing public APIs as impossible native
implementations. No dependency exception has been introduced.

Native Windows and Intel macOS are not supported by the pinned compiler's
documented platform contract. Linux glibc and CPU minimums are stricter than
the baseline release. These obligations remain in scope as platform gaps.
