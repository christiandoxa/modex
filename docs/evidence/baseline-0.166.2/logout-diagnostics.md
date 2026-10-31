# Offline logout diagnostics

The production Modex executable and checksum-verified Prodex 0.166.2 Linux
oracle were compared in isolated synthetic homes. Missing profile option values,
duplicate profile options, unknown flags, and excess positional arguments now
produce the same exit-2 diagnostics in the covered cases, with no filesystem
mutations. The existing 0.166.0 logout help regression also passes.

Valid logout arguments remain behind Modex's unimplemented-command guard;
no account logout was attempted. Other argument combinations, profile state,
and actual logout behavior remain unverified. See
`tests/test_logout_diagnostics_01662.py`.
