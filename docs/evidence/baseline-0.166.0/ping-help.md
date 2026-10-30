# Ping command help on Prodex 0.166.0

Selected read-only help routes for the top-level `ping` command match the
verified 0.166.0 Linux release. Coverage includes group help, `ping help`,
`help ping`, nested OpenAI help, custom executable names, attached short help,
invalid long help values, and invalid nested operands. The checks compare
stdout, stderr, exit status, and filesystem effects in isolated processes.

Reproduce with `test_root_help_errors_01660.RootHelpErrors01660Tests` after
building with the pinned Mojo compiler. The cases exercise help and parser
diagnostics only; they do not execute a ping request or contact a provider.
The `ping openai` runtime and the other five release targets remain
unverified.
