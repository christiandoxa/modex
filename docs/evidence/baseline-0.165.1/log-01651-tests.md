# Logging tests against Prodex 0.165.1

`tests/test_log_01651.py` reruns the existing bounded logging cases against the
verified 0.165.1 Linux oracle. It selects the 87-case production log CLI parser
matrix and 36 tests from the shared log snapshot, operational projection,
payload, redaction, runtime, text, timestamp and transcript suites. The
historical 0.439.2 tests remain in their existing lane.

The active oracle is pinned to SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.
The lane ran with a nonexistent `PRODEX_ORACLE`, explicit
`PRODEX_ORACLE_01651` and `MODEX_BINARY` paths, and private `HOME`/`TMPDIR`.
`python3 scripts/ci/run-unittest.py test_log_01651.py test_session_report_01651.py`
passed all 53 cases: 36 logging checks and 17 session-report checks. The 87
real-process CLI cases compare help routing, positional values, option order,
duplicate and attached values, suggestions, delimiters and short-help clusters.
Each process uses the existing synthetic HOME/cwd fixture and the
checksum-verified release. No credentials or provider traffic are used. This
confirms the lane cannot silently fall back to the historical oracle.

The historical lane stayed separate:
`PRODEX_ORACLE=<verified 0.439.2 binary> python3 scripts/ci/run-unittest.py test_logs.py`
passed all 6 `log last` controls, and the same command with
`test_log_transcript.py` passed all 4 transcript controls.

These selected Linux file-log cases do not establish live-source registry
locking/recovery, terminal rendering, or any non-host release target.
