# Verified gaps

The goal remains complete behavioral and feature parity with all six Prodex
0.439.0 release targets. Current tests establish narrow local facts, not that
goal. `docs/parity.json` records the initial inventory and platform obligations.

Session machine-output tests cover populated and archived plain JSON/JSONL,
metadata precedence, timestamp ordering, Unicode whitespace and query behavior,
parent filtering, limits, exact JSON formatting, ID/resume command output, and
symlink exclusion. The product rejects existing state rather than reading
without the required lock/recovery. Compressed rollouts, leap-second timezone
files, text/terminal output, argument-error wording, profile bindings,
and startup lifecycle/housekeeping effects remain unfinished.

Numeric and file-modification timestamps now match the release in UTC,
Asia/Jakarta, America/New_York and Europe/London for the tested dates, including
daylight offsets, negative epochs, expanded years and Chrono's range limits.
The Mojo implementation parses OS TZif files using standard file APIs.
References: [TZif format](https://www.rfc-editor.org/rfc/rfc9636.html) and
[Chrono 0.4.44 date limits](https://docs.rs/chrono/0.4.44/chrono/naive/struct.NaiveDate.html).
Recurring TZif footer rules now handle future dates, northern/southern seasons,
half-hour daylight changes, Julian/ordinal/month-week dates and signed extended
transition times. Explicit POSIX TZ strings use the release's narrower syntax;
invalid values fall back to UTC as observed in the official artifact. Sources:
[POSIX TZ grammar](https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap08.html)
and [glibc timezone documentation](https://sourceware.org/glibc/manual/latest/html_node/Proleptic-TZ.html).
The current differential suite checks dates through 2100 and exact transition
seconds in six named zones. Leap-second TZif files remain unimplemented.

`python3 tests/session_mismatches.py` records both executables' output, exit
status and new files. The output-focused tests explicitly exclude those
side-effect failures from their claims. No session contract is PASS.

The official baseline panics with exit 101 when a valid JSONL session contains
a subsequent valid non-object JSON value such as `[]` or `null`.
`crates/prodex-session-store/src/report.rs::apply_session_value` calls an
object-only Mojo planner with `expect`. Modex safely ignores those follow-up
values. This is an unapproved safe behavioral difference, preserved in mismatch
evidence, and not counted as parity. Proposed resolution: approve the safe
behavior and separately fix the baseline; neither action has been assumed.

Platform and foundation gaps are in `docs/capabilities.json`. No TLS,
cryptography, native Windows, Intel macOS, process-tree, locking, or clean
distribution claim is implied by the current Linux probes.

The baseline release's npm smoke path actively stages and imports a JavaScript
gateway SDK, despite the checked-in package being private and the exact version
currently missing from npm. Native JavaScript import compatibility conflicts
with the Mojo-only/no-adapter policy. That obligation remains BLOCKED; see
`docs/packaging-audit.json`. Its historical admin endpoint documentation does
not by itself establish active gateway server routes.
