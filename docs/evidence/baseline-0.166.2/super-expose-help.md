# Super expose help routes

Prodex 0.166.2 reassembles `super expose` (including the `s` alias) into the
hidden `__super-expose` CLI command before Clap parses its arguments. Its static
help is therefore available without preparing or starting an expose endpoint.
The frozen `SuperExposeArgs` declaration supplies the help fixture at
`docs/evidence/baseline-0.166.2/help/__super-expose.txt`.

Modex now prints that help for direct `__super-expose --help` and `-h`,
`help __super-expose`, and `super expose` / `s expose` followed by either help
flag. It preserves the executable basename in the usage line. No expose runtime
or launcher path was added; non-help execution remains unsupported.

`tests/test_super_expose_help_01662.py::SuperExposeHelp01662Tests.test_hidden_and_super_alias_help_match_without_mutations`
compares the production Modex binary with the checksum-verified Prodex 0.166.2
Linux oracle in isolated Bubblewrap processes. The five tested direct, alias,
and custom-name cases match exact stdout, exit status, and empty stderr, and
create no state in their synthetic homes or workspaces.

Validation on Linux x86-64: `make build`, the focused differential test, the
production dependency audit, and `git diff --check` passed. This qualifies only
the listed help routes on this target. Super expose execution, its lifecycle,
and the other five platform targets remain unqualified.
