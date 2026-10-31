# Prodex 0.166.2 redeem parser diagnostics

`tests/test_redeem_diagnostics_01662.py` compares Modex's production `redeem`
argument parser with the checksum-pinned Linux x86-64 Prodex 0.166.2 binary
(SHA-256 `e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`).
It covers missing profile and URL values, repeated switches, malformed switch
and help values, option-value precedence, unknown arguments, and extra
positionals. Every tested failure returns exit status 2 and leaves the isolated
home unchanged.

Reproduce with:

```bash
make build
PRODEX_ORACLE_01662=/path/to/prodex-x86_64-unknown-linux-gnu \
MODEX_BINARY="$PWD/build/modex" \
python3 scripts/ci/run-unittest.py test_redeem_diagnostics_01662.py
```

The checks use synthetic arguments and isolated HOME/network namespaces. They
do not exercise profile lookup, lifecycle locking, credentials, account login,
or a redeem request. Valid redemption remains guarded in Modex. This is
selected parser evidence on Linux x86-64, not redeem or six-target parity.
