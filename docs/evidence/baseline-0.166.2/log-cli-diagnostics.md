# Prodex 0.166.2 log CLI diagnostics

The connected Modex `log` parser now includes `--help` in unknown-option
suggestions and reconstructs usage with the accepted `--json` and mode prefix.
This matches the pinned Prodex 0.166.2 diagnostics for abbreviated help such as
`log --h=x`, including `log last --json --h=x`. Before the change, Modex
reported the token as an unknown value and omitted the accepted help option
from usage.

`tests/test_log_cli_01662.py` compares exact process status, stdout, and stderr
for 13 isolated cases: full and short help; help under `last` and `upstream`;
help and JSON near-matches; unknown mode/option controls; and attached help and
JSON values. Every case leaves the synthetic home and work directory unchanged.
The test uses the checksum-verified Linux x86-64 oracle at SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`.

Reproduce with:

```sh
PRODEX_ORACLE=/path/to/prodex-0.166.2 \
MODEX_BINARY="$PWD/build/modex" \
python3 scripts/ci/run-unittest.py test_log_cli_01662.py
```

This qualifies selected log CLI help/diagnostics only. File-backed log
projection, live sources, secure app-root repair, and the other five targets
remain unqualified.
