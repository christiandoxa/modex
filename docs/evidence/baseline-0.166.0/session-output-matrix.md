# Session output comparisons

`tests/test_session_outputs_01660.py` runs the existing session-output fixture
against the checksum-verified Prodex 0.166.0 Linux binary and Modex. Selected
cases compare populated listings, filters, JSON metadata, archived children,
malformed records, Unicode and timestamp/timezone output, and equal-timestamp
report ordering. One inherited non-object-record check exercises Modex alone.
The invalid-JSON path and plain-table title tests record intentional safer
differences; neither establishes parity.

The equal-timestamp case creates six synthetic records with identical timestamp
keys, mixed ASCII and Unicode IDs, and duplicate IDs at distinct paths. Both
processes order by ascending ID, then ascending path for duplicate IDs. The
reference implements this in `session_report_order` in
`crates/prodex-mojo-core/src/json/session_report.rs`; Modex uses the same keys
in `SessionReport.__lt__` in `src/modex/sessions.mojo`. The real-process outputs
match, so this probe required no production change.

The plain-table control case uses the synthetic title `\x1b[31mN\nX` under a
private process sandbox. Prodex emits the raw escape and newline; Modex prints
`\\x1b[31mN\\x0aX`, and the fixture file remains unchanged. A focused run of
the new test passed on Linux x86-64. This preserves safer display behavior
without claiming output parity.

All 22 test methods passed on Linux x86-64 in a private user, mount and network
namespace with isolated HOME and temporary storage, loopback only and no
default routes. The shared fixture normalizes temporary root paths and the
product name in resume commands. It checks output; it does not compare startup
locks or housekeeping, profile recovery, live session behavior, other targets,
or complete parity. Those gaps remain recorded in `docs/handoff.md`.
