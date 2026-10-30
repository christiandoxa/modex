# Live runtime log source gap

The reference is frozen Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`, verified Linux binary SHA-256
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.
Its production path is `crates/prodex-app/src/app_commands/log_live.rs`:
`LiveRuntimeLogSource::poll` validates registry admission and source binary
identity, fetches an authenticated bounded snapshot, tracks cursor and dropped
counts, and passes records through `collect_live_log_items`.

The real-process fixture uses a temporary HOME and working directory, a
synthetic `.prodex/runtime-broker-live-direct-test.json` registry and
`.capability` file, a live identity holder process, and a synthetic HTTP server
on `127.0.0.1`. The server accepts only the fixture's synthetic capability
header. Prodex requests `after=0&limit=512` then `after=1`, emits the marker
token event and `dropped=2` gap, and remains alive. Modex exits with status 1
and `Error: live runtime log sources are not implemented`, produces no stdout,
and makes no HTTP request. The capture also checks broker mode, instance reset,
and stale PID, process birth, capability, instance and executable cases; all
eight release/Modex comparisons remain FAIL.

The focused regression is
`tests/test_log_runtime.py::LogRuntimeTests.test_live_broker_log_gap_is_reproduced_against_frozen_release`.
It passes only by confirming the recorded behavior difference; it is not a
parity assertion. The full fixture output is in
`docs/evidence/log-live-mismatch.json`.

Modex stays fail-closed because this path depends on the reference registry
store's lock acquisition, recovery and legacy-artifact handling. The Mojo
standard library does not provide compatible interprocess locking and durable
replacement primitives. The release identity resolver also executes candidate
binaries with `--version`, which Modex is not allowed to do. No registry is
read and no capability is sent by Modex.

Reproduction on Linux x86-64 with Mojo 1.2.0:

```text
make build BUILD_DIR=/tmp/modex-log-live-04392-build
MODEX_BINARY=/tmp/modex-log-live-04392-build/modex \
PRODEX_ORACLE=~/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu \
PYTHONPATH=tests python3 -m unittest -v \
  test_log_runtime.LogRuntimeTests.test_live_broker_log_gap_is_reproduced_against_frozen_release
```

Capture all eight cases and refresh the JSON with:

```text
MODEX_BINARY=/tmp/modex-log-live-04392-build/modex \
PRODEX_ORACLE=~/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu \
PYTHONPATH=tests python3 tests/capture_log_live.py
```
