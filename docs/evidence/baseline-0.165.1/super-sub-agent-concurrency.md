# Super sub-agent concurrency parser against 0.165.1

The pinned 0.165.1 source declares `--sub-agent-max-concurrency` with a
custom value parser and requires `--sub-agent` in
`crates/prodex-cli/src/runtime_args/launch_args.rs`. The parser is defined in
`crates/prodex-cli/src/sub_agent.rs` at commit
`10ae15b5d1806302b60f051e4e6fec788044f4c2`. The active Linux oracle SHA-256 is
`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`; the
historical 0.439.2 oracle SHA-256 is
`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

In isolated synthetic homes, both releases return exit 2, empty stdout and
the exact Clap invalid-value diagnostic for invalid syntax (`-1`, `+1`, and
`abc`), out-of-range values (`0` and `65`), and overflow (`65536` and a value
above U64 max). The attached `--sub-agent-max-concurrency=-1` form has the same
diagnostic. These cases create no application state.

`default`, `1`, `4`, `8`, `16`, `32`, `64`, and whitespace-surrounded ` 1 `
are accepted when followed by `--help`. Help before an invalid value returns
help; an invalid value before help still returns the parser error. The
pre-tail Modex path now matches those statuses, diagnostics, output controls
and filesystem results. For pre-tail values, Modex stores the trimmed `default`
or canonical decimal number after validation, matching the release's typed
`SubAgentMaxConcurrency` parser. A valid concurrency value still requires
explicit `--sub-agent`; the production guard is covered by a Modex-only
no-mutation test and the native Super parser test.

## Dry-run consumer

The real 0.165.1 binary was run under `bwrap` with an isolated synthetic
HOME and workspace and no network. `super --dry-run` with
`--sub-agent` and `--sub-agent-max-concurrency ' 1 '` exits 0 and reports
`Maximum active sub-agents: 1 (custom)`. The whitespace-surrounded `default`
form also exits 0 and reports `4 (Prodex default)`. Neither run starts Codex or
creates files. The typed downstream consumer therefore accepts and normalizes
both forms.

Modex accepts the same arguments, then exits 1 at its existing Super startup
guard with `Super startup is not implemented`; it creates no files and never
reaches a sub-agent consumer. This is an explicit production startup gap, not
sub-agent launch parity. The retained test compares the consumer report and
side effects while using only a synthetic API key and a dry run.

After positional `exec`, negative input still follows the runtime error path:
Prodex returns exit 1 with the native concurrency error and creates `.prodex`
lock state; Modex retains the same exit-1 text without state mutation. A dry run
also confirms a separate whitespace gap after `exec`: Prodex accepts and
reports both normalized forms, while Modex rejects them with its runtime-style
invalid-value error and creates no files. The parser change only canonicalizes
pre-tail values and does not alter this post-tail path. Tests use no real
credentials, provider traffic or account login. This qualifies only the tested
Linux x86-64 Super parser behavior, not the other release targets or all
concurrency/runtime behavior.
