# Stateless session report projection against Prodex 0.166.2

`test_session_output_projection_01662.py` runs the existing session report
suite against the checksum-pinned Linux x86-64 Prodex 0.166.2 oracle. It reuses
the same synthetic fixtures while rebinding only the release binary, so JSON
reports, filters, ordering, metadata fallback, timestamps, and timezone
formatting exercise Modex's production `session list` and `session current`
paths.

The focused suite ran 14 tests: 13 compare release and Modex output, and one
checks Modex-only safe handling of non-object follow-up records. That safety
check is not parity evidence. This qualifies stateless report projection on
Linux x86-64 only. Profile-backed state loading/recovery, session-root resume,
startup side effects, interactive terminal behavior, and the other five release
targets remain outside this evidence. CI resolves the oracle through
`PRODEX_ORACLE`; its pinned SHA-256 is
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`.
