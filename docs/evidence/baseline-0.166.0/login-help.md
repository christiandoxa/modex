# Login help against Prodex 0.166.0

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The pinned 0.166.0 Linux oracle has SHA-256
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

`tests/test_login_help_01660.py` compares the active oracle with the production
Modex CLI for direct and nested login help, accepted `--profile` forms, custom
`argv[0]`, and parser errors. The process harness gives both binaries a private
HOME and workspace, clears PATH and provider environment, disables networking,
and checks that the help cases create no files. All three focused tests passed.

This covers the static help routes only. Modex keeps login execution fail-closed
and verifies that a synthetic profile request creates no state. It does not
claim parity for login flows, profile storage, credentials, or provider access.
