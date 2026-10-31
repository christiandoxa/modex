# Static help command names against Prodex 0.166.2

The verified Linux x86-64 Prodex 0.166.2 binary
(`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`)
keeps literal `prodex` command names in static help prose even when invoked
with `argv0=modex`. The executable name remains dynamic in each `Usage:` line.

Modex now follows that output for root help, `session`, `doctor`, `quota`,
`super`, and the `s` alias. This corrects only rendered help strings; it does
not qualify the commands' runtime behavior. The focused test also checks short
help forms for root, session, doctor, and quota, custom executable names,
`help <command>` routes, and no filesystem mutations.

Reproduce after building:

```sh
PRODEX_ORACLE=/path/to/verified/prodex-0.166.2 \
MODEX_BINARY="$PWD/build/modex" \
python3 scripts/ci/run-unittest.py test_static_help_names_01662.py
```

This comparison covers Linux x86-64 help output only. All six release targets
remain in the parity denominator.
