# DeepSeek streaming idle diagnostics

Both pinned source releases preserve the upstream stream-idle timeout as
`runtime upstream stream idle timed out` in
`crates/prodex-app/src/runtime_launch/proxy_startup/local_rewrite_upstream.rs`
(0.165.1 commit `10ae15b5d1806302b60f051e4e6fec788044f4c2`; frozen 0.439.2
commit `72b77478a5198fc5da6b4d2253137f9cdbf43be9`). Modex's
`DeepSeekExchange.read_events` previously replaced every body-read failure with
`error decoding response body`. It now preserves the timeout-specific message
when its loopback reader reports an idle timeout, while retaining the generic
message for framing and other read failures.

Three-process loopback comparisons use synthetic credentials, isolated homes,
and a 100 ms stream-idle timeout. Before any provider bytes arrive, both
releases and Modex return 502 with no event. After a synthetic text event, one
capture returned the same 200/event sequence for all three processes; 0.165.1
reported `error decoding response body`, while 0.439.2 and Modex reported
`runtime upstream stream idle timed out`. A repeated controlled run observed
the 0.165.1 binary report the timeout-specific message too. The two release
paths race between their timeout-specific and generic body-read diagnostics;
the single differing capture is retained as an observed mismatch, not a stable
release-level rule.

The post-commit test asserts Modex's timeout-specific message on the direct idle
read path. The 0.165.1 and 0.439.2 comparisons retain both source-observed
diagnostics to allow the transport race. Empty pre-commit and text post-commit
controls run against both releases. Truncated content-length and chunked-body
controls also compare all three processes and retain the generic decoding
diagnostic.

Linux x86-64 checks passed:

- `rtk make build`
- `build/tests/test_provider_deepseek_transport`
- `PYTHONPATH=tests python3 -m unittest -v test_provider_deepseek_transport.ProviderDeepSeekTransportTests.test_idle_timeout_emits_failure`
- `PYTHONPATH=tests python3 -m unittest -v test_deepseek_continuation.DeepSeekContinuationTests.test_stream_precommit_idle_and_lookahead_deadlines_match_release`
- `PYTHONPATH=tests python3 -m unittest -v test_deepseek_precommit_boundaries_04392.DeepSeekPrecommitBoundaryTests.test_empty_and_truncated_eof_shapes_match_release`

All requests used loopback peers and synthetic keys. No account login or paid
provider traffic was used. This qualifies selected timeout paths only and does
not establish general stream or cross-target parity.
