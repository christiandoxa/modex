# Hidden MCP bridge help (Prodex 0.166.0)

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The active reference is official Prodex 0.166.0 at commit
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64 oracle
SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

`crates/prodex-cli/src/lib.rs` registers the hidden `__mcp-jsonl-bridge`
command. `crates/prodex-cli/src/runtime_args.rs::McpJsonlBridgeArgs` defines
the required `COMMAND` and trailing `ARGS` values and their help text. The
release prints this static help for `help __mcp-jsonl-bridge`, direct `--help`,
and direct `-h`. It reports a nested extra operand and `--help=bad` as exit-2
argument errors.

Before this change, Modex sent all of these requests to its generic
unimplemented-command error. Modex now matches the tested help and diagnostic
forms without entering the hidden bridge command. The regression runs both
real executables through the isolated process helper with synthetic homes,
empty workspaces, and networking disabled; it verifies output, exit status, and
that neither process creates files. It does not start a JSON-lines server or
pass through any command or arguments.

Focused checks passed on Linux x86-64 with Mojo 1.2.0:

- `python3 scripts/ci/run-unittest.py test_root_help_errors_01660.py` — 9 tests.
- `python3 scripts/ci/check-product-dependencies.py` — 74 production Mojo files
  use only standard-library or internal imports.
- `git diff --check`.

This covers the listed help and parser forms only. The MCP bridge itself and
the other five release targets remain unqualified; no parity-denominator or
security behavior changed.
