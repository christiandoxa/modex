# Token usage event selection

The pinned Prodex 0.165.1 (`10ae15b5d1806302b60f051e4e6fec788044f4c2`) and
0.439.2 (`72b77478a5198fc5da6b4d2253137f9cdbf43be9`) sources share
`info_token_usage_event_from_line_with_event`. For JSON, the helper decodes
the record and requires its `event` value to equal `token_usage`. Unlike
upstream payload selection, it does not require the literal raw substring
`token_usage`: both pinned processes accept an escaped JSON event name
(`token\u005fusage`) with no such substring in the input line.

Before the fix, a synthetic runtime record with event `synthetic_event`,
token-count fields, and a `token_usage` note caused Modex to emit a token usage
event. Both release processes emitted no token usage event. The shared Modex
projection now checks the parsed event name before reading token fields and
retains acceptance of escaped `token_usage` names. Generic operational event
projection remains as in the releases, so the followed-record test counts token
usage projections separately from generic event output.

`tests/test_log_token_selection_01651_04392.py` compares checksum-pinned
Prodex 0.165.1 (`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`),
Prodex 0.439.2 (`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`),
and Modex in JSON and plain modes. It covers `log last`, initial `log stream`
snapshots, and appended runtime events. The fixtures use isolated homes,
runtime directories, and synthetic log records. Fast and Full CI run this
module in the active cross-release lane.

On Linux x86-64, the focused token-selection, upstream-selection, and escaped
stream-event modules passed together: 4 tests in 74.8 seconds. The Modex
executable was built from the isolated `origin/main` worktree with Mojo
1.2.0. `git diff --check`, JSON parsing of `docs/parity.json`, and `bash -n` on
both CI scripts also passed.

The process checks establish these selected file-backed cases on Linux x86-64
only. They do not qualify live log sources, unrelated event families,
security behavior, or the other four release targets.
