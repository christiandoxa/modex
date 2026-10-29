# Session limit error precedence

The read-only source trace in Prodex 0.165.1 places `limit: Option<usize>` in
`crates/prodex-cli/src/session_context.rs` for both `SessionListArgs` and
`SessionCurrentArgs`. The production `session` command receives Clap's parsed
arguments before `load_session_reports` applies the limit.

Differential probes found that a split invalid value followed immediately by
an unknown argument reports that argument first. For example,
`session list --limit bad extra` reports `unexpected argument 'extra' found`;
an unknown option or a token after `--` follows the same precedence. An
attached invalid value (`--limit=bad`), a recognized next option, or a bare
`--` still reports the invalid limit. Both official releases show these
results.

The production Mojo parser now applies the same narrow precedence rule. It
checks only the argument immediately after a split `--limit` value. No state
files or session data are read or changed by these parser errors.

`tests/test_session_cli.py::SessionCliTests::test_split_limit_error_precedence_matches_both_releases`
checks 12 cases against the checksum-pinned Prodex 0.165.1 Linux binary
(`dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`) and
0.439.2 Linux binary
(`a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`).
Fixtures use isolated temporary homes and workspaces; no credentials,
accounts, or provider traffic are used.

Validation passed on Linux x86-64 with Mojo 1.2.0:

```text
make build
python3 scripts/ci/run-unittest.py test_session_cli.py
mojo build -O3 --target-cpu=x86-64-v3 -I src tests/test_session_cli.mojo -o build/tests/test_session_cli
build/tests/test_session_cli
make ci-dependencies
python3 scripts/ci/check-test-census.py
git diff --check
```

The Python session CLI suite passed 4 tests; the native parser check passed;
the dependency audit covered 71 Mojo files; the census found 50 native test
sources and 129 Python modules with one owner each. This is a CLI parsing
slice, not full session parity. Other release targets remain unqualified.
