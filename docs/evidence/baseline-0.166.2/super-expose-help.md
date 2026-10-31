# Super expose help routes

Prodex 0.166.2 reassembles `super expose` (including the `s` alias) into the
hidden `__super-expose` CLI command before Clap parses its arguments. Its static
help is therefore available without preparing or starting an expose endpoint.
The frozen `SuperExposeArgs` declaration supplies the help fixture at
`docs/evidence/baseline-0.166.2/help/__super-expose.txt`.

Modex prints that help for direct `__super-expose --help` and `-h`,
`help __super-expose`, and `super expose` / `s expose` followed by either help
flag. It preserves the executable basename in the usage line. A diagnostic-only
pre-MODE parser now also matches unknown long and short options, missing values,
attached values on switches, duplicate non-repeatable options, retained-option
usage lines, and help/unknown ordering for the hidden command and public aliases.
Valid expose execution remains behind the existing Super startup guard.

`tests/test_super_expose_help_01662.py` compares the production Modex binary
with the checksum-verified Prodex 0.166.2 Linux oracle in isolated Bubblewrap
processes. Help and malformed pre-MODE cases match exact output and exit status
and create no state in their synthetic homes or workspaces. A syntactically
valid public `super expose --listen 127.0.0.1:0` remains guarded in Modex and
creates no state; the oracle was not invoked for a valid expose request.
Semantic option validation remains incomplete: for `__super-expose --tool one
--help`, Prodex rejects the unknown optional tool with exit 2 before help,
while Modex prints help with exit 0. The test records this mismatch explicitly.

Validation on Linux x86-64: `make build`, the focused differential test, the
production dependency audit, and `git diff --check` passed. Other semantic
option values, expose execution and lifecycle behavior, and the other five
platform targets remain unqualified.
