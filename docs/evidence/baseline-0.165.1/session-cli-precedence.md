# Session CLI edge diagnostics

The frozen Prodex 0.439.2 source commit is
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`; the historical Prodex 0.165.1
commit is `10ae15b5d1806302b60f051e4e6fec788044f4c2`. In both sources,
`crates/prodex-cli/src/session_context.rs` declares `SessionListArgs.limit` as
an optional `usize` and the remaining session flags as Clap arguments. Their
generated help-subcommand parser also omits Clap's generic help footer for an
invalid child of `session help help`.

Before the fix, these isolated process inputs reproduced two mismatches:

```text
session current --profile foo --limit main --json= --limit
```

Both releases return exit 2 with `unexpected value '' for '--json' found`;
Modex returned `invalid value 'main' for '--limit <N>'` before reaching the
malformed switch.

```text
session help help --help=x
```

Both releases return exit 2 with `unrecognized subcommand '--help=x'` and end
after `Usage: prodex session help [COMMAND]...`. Modex appended
`For more information, try '--help'.`.

The session parser now preserves the release's immediate-next-option
precedence for a split invalid `--limit` value and its help-subcommand
diagnostic. Attached invalid `--limit=...` and invalid limits followed by a
value-taking option retain their prior diagnostics. `tests/test_session_cli.py`
compares six limit sequences and three nested-help sequences through the real
0.165.1 and 0.439.2 binaries and Modex. The fixtures use only temporary homes,
workspaces, and a synthetic session; the tests verify no file mutations.

Validation on Linux x86-64:

- `PYTHONPATH=tests MODEX_BINARY=build/modex python3 scripts/ci/run-unittest.py test_session_cli.py` — 7 tests passed.
- A separate seeded 608-sequence three-process session CLI sweep — 0 mismatches.
- `python3 scripts/ci/check-product-dependencies.py` — 71 Mojo files passed.
- `python3 scripts/ci/check-test-census.py` — 50 native sources and 155 Python modules.

This qualifies only the listed session CLI diagnostics on Linux x86-64. It does
not establish complete session CLI behavior, state locking/recovery, security
equivalence, or any of the other five release targets.
