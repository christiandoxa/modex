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
The inventory contains 60 coarse contracts and 360
platform obligations; 1 Linux obligation passes, and 0 complete cross-platform
contracts pass. Inventory expansion remains necessary; no parity percentage is
valid.

Validation: `make test` (3 Mojo unit programs, a test-only JSON driver, and 29
Python black-box/runtime tests PASS, including 500 deterministic generated
JSON values plus malformed UTF-8/syntax/boundary vectors and numeric/local
session time comparisons, including future recurring rules through 2100,
transition-second boundaries, and explicit/invalid POSIX TZ strings),
`python3 tests/probe_capabilities.py` (3 positive programs PASS,
4 expected public-API gaps reproduced). `python3 tests/session_mismatches.py`
retains 3 FAIL cases and one unapproved safe difference for a baseline panic.
Actual compiler diagnostics and commands are in `docs/evidence/capabilities/`.

The frozen help inventory now contains 35 routes and 326 option mentions,
including four hidden commands and both Super exposure/short aliases. Capture
command: `python3 tests/capture_cli.py`; all help routes exit 0 with empty stderr
and no state mutations. Help mentions still require source validation for
registered flags, hidden flags, defaults, precedence and passthrough.

Session help and argument diagnostics now match 39 captured official-release
cases, including missing/invalid/overflow values, duplicate/conflicting flags,
help precedence, stdout/stderr, exit codes and absence of state mutations on
help/error paths. Reproduce with `python3 tests/capture_session_cli.py` and
`python3 -m unittest discover -s tests -p test_session_cli.py`.
Evidence: `docs/evidence/baseline/session-cli.json` and
`docs/evidence/session-cli-tests.txt`. Suggestions, short-flag clusters,
complex argument combinations and valid resume execution remain unfinished.

Detached plain session text output now matches 71 official-release scenarios:
table columns, truncation and full-ID details, optional cells, multiple rows,
list/current filters, empty panels, long-token wrapping, widths 1 through 300,
and valid/invalid `PRODEX_TERM_COLUMNS` overrides. `COLUMNS` is ignored as in
the release. Tests compare raw bytes in identical disposable homes.
The initial slice covers printable ASCII; terminal dimensions and the
interactive view remain unimplemented. Evidence:
`docs/evidence/session-text-tests.txt`. The text mismatch reproducer now records
matching output separately from the remaining startup side-effect differences.

Plain rendering now measures display cells and preserves UTF-8 for supported
Latin, Greek, Cyrillic, CJK, kana and Hangul ranges, combining accents and soft
hyphens. The suite compares 239 raw-output scenarios, including Unicode range
edges, truncation, padding, full IDs and Unicode/paragraph path wrapping.
Other scripts, emoji sequences and remaining control cells still fail
explicitly. Evidence: `docs/evidence/session-unicode-tests.txt`.

The active release staging/smoke path imports the JavaScript gateway SDK.
Its module-import compatibility is BLOCKED by the Mojo-only/no-adapter policy,
not removed from scope. `docs/packaging-audit.json` preserves conflicting
source/publishing/README evidence.

Next work: trace hidden/default/precedence flag contracts, complete remaining
Unicode display widths and the terminal view, and evaluate official stdlib mechanisms
for state loading and recovery. Current stateful, compressed and leap-second
paths fail explicitly. Future recurring timezone rules and POSIX TZ strings are
implemented; their current evidence is `docs/evidence/recurring-time-tests.txt`.
Startup effects still differ. Details and the baseline
panic are in `docs/known-gaps.md`; no session contract is PASS.

Mojo's public process API has no stdio-redirection, process-group, or
environment-isolation options. Its networking package currently exposes only
internal building blocks. The official stdlib source at the pinned release
must be checked before interpreting missing public APIs as impossible native
implementations. No dependency exception has been introduced.

Native Windows and Intel macOS are not supported by the pinned compiler's
documented platform contract. Linux glibc and CPU minimums are stricter than
the baseline release. These obligations remain in scope as platform gaps.
