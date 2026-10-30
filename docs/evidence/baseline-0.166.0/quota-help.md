# Quota command help on Prodex 0.166.0

The pinned source at `9f69e1835808f478f59f12a3ae3fa88027d896a4` declares the
top-level `Quota(QuotaArgs)` command in `crates/prodex-cli/src/lib.rs` and its
flags in `crates/prodex-cli/src/profile.rs`. The release exposes expanded
`--help`, compact `-h`, and the built-in `help quota` route. Modex now serves
both static help forms without entering quota execution.

`tests/test_root_help_errors_01660.py::RootHelpErrors01660Tests.test_quota_help_matches_release_without_quota_execution`
compares the checksum-verified Linux x86-64 oracle with Modex in isolated
filesystem, HOME, and network namespaces. It covers both help layouts, custom
`argv0`, value options before help, help precedence, duplicate or malformed
options before help, and the built-in help alias. The Modex-only non-help
control confirms that `quota --profile synthetic-profile` stays behind the
existing unimplemented-command guard and creates no files. No quota endpoint,
credential, or account login is used.

Reproduce after building Modex:

```sh
PYTHONPATH=tests MODEX_BINARY=build/modex \
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.166.0/prodex-x86_64-unknown-linux-gnu" \
python3 -m unittest -v \
  test_root_help_errors_01660.RootHelpErrors01660Tests.test_quota_help_matches_release_without_quota_execution
```

This qualifies only quota help parsing and rendering on Linux x86-64. Quota
execution and the other five release targets remain unqualified.
