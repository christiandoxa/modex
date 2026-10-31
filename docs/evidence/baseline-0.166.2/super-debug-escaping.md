# Selected Super debug-string escapes

The active baseline is Prodex 0.166.2 at
`b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`; its verified Linux x86-64
binary has SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`.

The pinned source formats invalid `--sub-agent-provider` values with
`{value:?}` in `crates/prodex-cli/src/sub_agent.rs::parse_sub_agent_provider`.
The same Rust debug formatting is used for invalid reasoning effort in
`SubAgentReasoningEffort::from_str`. Modex's shared `_debug_quoted` helper in
`src/modex/super_cli.mojo` serves both diagnostics.

Oracle probes found these selected values escaped by Prodex but printed as raw
scalars by Modex:

| Codepoint | Prodex debug form |
| --- | --- |
| U+00A0 | `\u{a0}` |
| U+202F | `\u{202f}` |
| U+0378 | `\u{378}` |
| U+2063 | `\u{2063}` |
| U+FE0F | `\u{fe0f}` |
| U+E000 | `\u{e000}` |
| U+FFF9 | `\u{fff9}` |

Modex now escapes those seven observed values. U+200E (already covered) and
printable `é` are controls to ensure the change preserves the existing selected
behavior. The regression exercises every value through both parser callers,
compares complete stderr and exit status to the oracle, and confirms neither
process creates files. Both commands use synthetic isolated homes and a
`bwrap --unshare-all` sandbox; each exits 2 with empty stdout and no state
changes. The invalid values are rejected before startup, so the test sends no
provider traffic.

This changes only the inner quoted debug rendering; the outer Clap value field
continues to show the original non-control Unicode scalar as Prodex does.
Terminal-control filtering remains in `_clap_value`. The mismatch affected
diagnostic readability and made invisible or unusual scalars harder to spot;
it did not pass a value to execution or persistent state.

Validation on Linux x86-64 with Mojo 1.2.0 (`2016d0cd`):

- `make BUILD_DIR=build build` — passed, with existing unused-variable warnings.
- `MODEX_BINARY=build/modex PRODEX_ORACLE=/path/to/prodex-0.166.2/prodex-x86_64-unknown-linux-gnu PYTHONPATH=tests python3 -m unittest -v test_super_debug_escaping_01662` — passed (18 value/caller comparisons).
- `mojo run -I src tests/test_super_cli.mojo` — passed.
- `python3 scripts/ci/check-product-dependencies.py` — passed; 74 Mojo files use only standard-library and internal imports.
- `python3 scripts/ci/check-test-census.py` — passed; 50 native sources and 237 Python modules have one suite owner.
- `python3 scripts/ci/run-unittest.py test_ci_oracle_routing.py test_ci_test_census.py` — 30 CI routing/census tests passed, including Fast/Full active-suite registration.

This is limited evidence for the seven listed codepoints on Linux x86-64. It
does not establish complete Rust Unicode `Debug` parity, all six target
platforms, or Super runtime parity. The curated Unicode table remains an
explicit limitation.
