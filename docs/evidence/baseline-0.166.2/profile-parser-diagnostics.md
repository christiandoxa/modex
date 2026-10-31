# Profile parser usage diagnostics

The active reference is Prodex 0.166.2 at source commit
`b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`. The isolated Linux x86-64
oracle has SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`.

`tests/test_profile_diagnostics_01662.py` compares parser failures after valid
profile options and positionals against that oracle. Prodex's usage line keeps
the recognized options and renders already consumed positionals as their
argument labels. Modex previously replaced those details with the generic
`[OPTIONS]` usage. The parser now constructs the reported usage from the parsed
prefix; repeated `--profile` filters in export appear once, matching Clap.

Fifteen isolated inputs cover `add`, `export`, `import`, `remove`, and `use`,
including options before and after a positional. They also cover unknown flags
where a preceding value-taking option has no value; that incomplete option is
omitted from the usage line. An extra positional control continues to use the
command-level usage. All diagnostics and exit codes match after mapping the
executable name. Both processes leave the synthetic home and workspace
unchanged. These inputs fail before profile operations run; this does not
qualify successful profile management, lifecycle locks, or the other five
release targets.

Verified on 2026-10-31 with:

```sh
make build
PRODEX_ORACLE=/path/to/verified/prodex-0.166.2 \
python3 scripts/ci/run-unittest.py test_profile_diagnostics_01662.py
```

The oracle checksum is checked by the test. The run uses no credentials,
provider traffic, or external network access.
