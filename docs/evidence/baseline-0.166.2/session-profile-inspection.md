# Profile-bound session inspection against Prodex 0.166.2

`tests/test_session_profile_01662.py` runs 15 isolated process checks through
Modex's production `session list` path and the checksum-pinned Prodex 0.166.2
Linux x86-64 oracle (`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`).
Each process receives a fresh synthetic home, session records, and private
`state.json`; the comparisons do not use account credentials or provider
traffic.

Eleven checks compare profile-bound report output or controls across both
processes. They cover `--profile` and query filtering, empty profile/session
identifiers, Unicode and terminal-control display, binding identity and
retention, the 2,048-entry binding retention rule, duplicate JSON binding
keys, large profile/binding maps, and report indexing for 2,048 synthetic
sessions. The remaining four checks characterize Modex's handling of
concurrent atomic state replacement, a corrupt primary with a last-good
backup, unsafe state paths, and writable or publicly hard-linked state. Those
cases include deliberate safe refusals and are not counted as full parity.

The active 0.166.2 profile-binding cases match on Linux x86-64, and this suite
is part of both Fast and Full CI. It does not qualify profile lifecycle
commands, state recovery, lock side effects, other release targets, or full
session parity. In particular, Modex continues to refuse last-good recovery
without the interoperable lifecycle lock; see
`session-state-recovery.md`.
