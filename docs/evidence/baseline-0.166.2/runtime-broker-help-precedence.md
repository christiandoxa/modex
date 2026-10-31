# Hidden runtime broker help precedence

Prodex 0.166.2 declares hidden `__runtime-broker` with an empty
`RuntimeBrokerArgs` type. Clap therefore treats any argument other than help as
an error; `-h` in a short-flag cluster prints help before later tokens are
checked, while an unknown token before help fails first.

Modex now matches tested `-hh`, `-hx`, and `--help --bogus` help cases, plus
the `-xh`, `--bogus --help`, unexpected positional, `--help=bad`, and
`--bad=foo` diagnostics. Unknown short flags preserve their full Unicode
codepoint. A final `--` with no following token reaches Modex's existing
unsupported-command guard; a token after `--` is an unexpected positional and
is reported literally. No runtime broker startup was added.

`tests/test_runtime_broker_help_precedence_01662.py` compares the production
binary with the checksum-verified 0.166.2 Linux oracle in isolated Bubblewrap
processes. All twelve help/parser cases match exact status, stdout, and stderr,
and create no fixture state. Modex-only no-argument and lone-`--` controls
confirm the runtime entry remains guarded and leaves synthetic homes and
workspaces unchanged.

Validation on Linux x86-64: `make build`, both focused test methods, the
production dependency audit, and `git diff --check` passed. This qualifies only
the listed parser cases on this target. Runtime broker startup and the other
five platform targets remain unqualified.
