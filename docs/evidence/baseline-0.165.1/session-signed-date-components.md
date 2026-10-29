# Session timestamp components

The frozen 0.165.1 source at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and 0.439.2 source at `72b77478a5198fc5da6b4d2253137f9cdbf43be9` use
`session_rfc3339_sort_key` in `mojo/prodex_core/session_report.mojo`, which
requires decimal digits for each fixed-width date, time and offset component.
Their separate integer timestamp parser accepts signed integers.

Previously Modex accepted signs inside those fixed-width components. For
example, `2026-01-01T+1:00:00Z` incorrectly sorted as a valid timestamp. The
shared parser now rejects signs inside RFC 3339 components while preserving
signed integer timestamps. Invalid timestamp strings remain visible in the
report and ordering falls back to the file modification time.

The production-path regression compares eight signed-component cases and a
valid control against each checksum-verified Linux release using isolated
session fixtures with fixed file times. Both comparisons failed before the
fix and pass after it. Native parser checks, numeric timestamp controls, and
the production import audit also pass. The shared timestamp parser is used by
log formatting and rate-limit projection; their existing focused process
suites were checked separately. This is not full timestamp, session, security
or platform parity.
