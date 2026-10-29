# Logging tests against Prodex 0.165.1

`tests/test_log_01651.py` reruns the existing bounded logging cases against the
verified 0.165.1 Linux oracle. It selects 36 tests from the shared log snapshot,
operational projection, payload, redaction, runtime, text, timestamp and
transcript suites. The historical 0.439.2 tests remain in their existing lane.

The active oracle is pinned to SHA-256
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`.
The lane ran with a nonexistent `PRODEX_ORACLE`, explicit
`PRODEX_ORACLE_01651` and `MODEX_BINARY` paths, and private `HOME`/`TMPDIR`.
`python3 scripts/ci/run-unittest.py test_log_01651.py test_session_report_01651.py`
passed all 50 cases: 36 logging checks and 14 session-report checks. This
confirms the lane cannot silently fall back to the historical oracle.

The historical lane stayed separate:
`PRODEX_ORACLE=<verified 0.439.2 binary> python3 scripts/ci/run-unittest.py test_logs.py`
passed all 6 `log last` controls, and the same command with
`test_log_transcript.py` passed all 4 transcript controls.

These selected Linux file-log cases do not establish live-source registry
locking/recovery, terminal rendering, or any non-host release target.
