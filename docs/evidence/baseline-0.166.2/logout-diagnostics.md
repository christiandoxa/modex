# Offline logout diagnostics

The production Modex executable and checksum-verified Prodex 0.166.2 Linux
oracle were compared in isolated synthetic homes. Unknown flags after an
accepted profile option or positional argument now retain the release's usage
prefix. The profile option and positional name also report the release's
conflict diagnostic. Split repeats defer to a later unknown flag or malformed
help value, while attached repeats retain duplicate-option precedence. A valid
help flag still precedes the profile/name conflict check. The covered parser
diagnostics match with no filesystem mutations.

The active comparison also covers four precedence cases that previously
differed: malformed `--help=value` after a pending `--profile` wins over the
missing-value error; an unknown option after a pending profile is reported as
unknown; attached `--profile=value` is reflected in malformed-help usage while
the separated form keeps `[NAME]`; and a name after `--` still conflicts with
`--profile`.

Valid logout arguments remain behind Modex's unimplemented-command guard;
no account logout was attempted. Other argument combinations, profile state,
and actual logout behavior remain unverified. The existing 0.166.0 logout
help regression also passes. The 0.166.2 oracle SHA-256 is
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`. See
`tests/test_logout_diagnostics_01662.py`.

Reproduce the Linux x86-64 differential with the checksum-pinned oracle:

```sh
PRODEX_ORACLE=/path/to/prodex-0.166.2 \
MODEX_BINARY=/path/to/modex \
python3 scripts/ci/run-unittest.py test_logout_diagnostics_01662.py
```
