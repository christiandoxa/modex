# Log CLI suggested-option usage against Prodex 0.439.2

The frozen Prodex 0.439.2 source at commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9` declares `LogArgs.mode` as an
optional positional with a default and `json` as a boolean `--json` option in
`crates/prodex-cli/src/session_context.rs`. When an unknown option resembles
`--json` after a positional token, the released Clap parser reports usage as
`modex log --json <MODE>`. Modex previously rendered `[MODE]` in that usage,
because its suggestion branch did not account for an already parsed
positional value.

`src/modex/log_cli.mojo` now selects `<MODE>` usage when a positional value has
already been parsed. `tests/test_log_cli.py` adds three real process
regressions: `log last --jso`, `log bad --jso`, and `log - --jso`. They match
the checksum-pinned 0.439.2 Linux binary after executable-name mapping.

On 2026-10-29, `make build` and
`python3 scripts/ci/run-unittest.py test_log_cli.py` passed. The process suite
uses isolated temporary homes and the verified oracle checksum recorded in
`tests/test_cli.py`. It checks selected parser diagnostics only; log output,
other CLI combinations, security behavior, the remaining five release
targets, and full parity are unqualified.
