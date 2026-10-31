# Hidden MCP bridge help precedence

Prodex 0.166.2 declares hidden `__mcp-jsonl-bridge` with a required
`<COMMAND>` positional and trailing `[ARGS]...` that accepts hyphen-prefixed
values. Before a command is selected, Clap processes `-h` in short-flag
clusters as help; help returns before later arguments are checked, while an
unknown option that appears first is an error.

Modex now matches the tested pre-command cases: `-hh`, `-hx`, and
`--help --bogus` print help; `-xh` and `--bogus --help` report the earlier
unknown option; `--help=bad` retains its value error. Unknown long options
with attached values and Unicode short options also match. Missing
`<COMMAND>` (including after a lone `--`) now reports the release's
required-argument diagnostic. After a command, exact `--help` and `-h`-only
clusters still select top-level help, and malformed `--help=value` retains its
diagnostic. A child argument before help, or a literal `--`, stops that scan;
the hidden bridge command remains behind Modex's existing unsupported-command
guard. Child-boundary controls use a nonexistent synthetic executable, so the
oracle's failed lookup does not run a server or mutate fixture state.

`tests/test_mcp_jsonl_bridge_help_precedence_01662.py` compares the production
binary and checksum-verified 0.166.2 Linux oracle in isolated Bubblewrap
processes. Pre- and post-command help/error vectors and both missing-command
cases match exact status, stdout, and stderr. Boundary controls verify that
child arguments and literal `--` do not become bridge help; the Modex command
guard is unchanged. All cases leave their synthetic homes and workspaces
unchanged.

Validation on Linux x86-64: `make build`, all focused test methods, the
production dependency audit, and `git diff --check` passed. This qualifies only
the listed parser cases on this target. Bridge process execution
and the other five platform targets remain unqualified.
