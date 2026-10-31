# Prodex 0.166.2 session current `--cwd` diagnostics

The checksum-pinned Prodex 0.166.2 Linux x86-64 release (source commit
`b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`, SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`) reports
a later unknown argument before the missing-value error for a split empty
`session current --cwd ""`. Modex previously stopped at the empty path and
reported the missing value first.

The connected parser now preserves this precedence for later unknown flags,
unknown positionals, arguments after `--`, and malformed attached flag values.
Controls confirm that a valid following option, `--help`, an invalid recognized
`--limit` value, help aliases, an attached empty `--cwd=`, and a truly missing
`--cwd` value still report the missing path. The parser returns an error before
session inspection in every case; the change does not allow an empty path to
reach the production session reader.

`tests/test_session_cwd_precedence_01662.py` compares eleven exact diagnostics
between the pinned oracle and Modex in isolated homes with no filesystem
effects. The same precedence and controls also matched the pinned 0.165.1
historical Linux binary. This qualifies these parser cases on Linux x86-64
only; it does not change session inspection, recovery, or resume behavior.

Reproduce with:

```sh
PRODEX_ORACLE=/path/to/prodex-0.166.2 \
MODEX_BINARY="$PWD/build/modex" \
python3 scripts/ci/run-unittest.py test_session_cwd_precedence_01662.py
```
