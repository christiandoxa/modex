# Prodex 0.166.0 Gateway argument diagnostics

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.0 as active describe the original capture.

The reference is Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. The Linux x86-64 executable is
SHA-256 verified as
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

## Source trace

`crates/prodex-cli/src/lib.rs` defines the `Gateway(GatewayArgs)` command and
routes process arguments through `Cli::try_parse_from`. In
`crates/prodex-cli/src/runtime_args.rs`, `GatewayArgs` uses Clap's `Args`
derive; `--listen` is a string value option and `--url` aliases `--base-url`.
Thus hyphen-prefixed tokens are parsed as options unless they are the literal
`-` value.

## Differential result

The 0.166.0 process reports `unexpected argument '-1' found` for
`gateway --listen -1`. Modex previously reported that `--listen` had no value.
The same mismatch affected other unrecognized short or long option tokens
after a value option. Unknown short and positional arguments also need Clap's
`[OPTIONS]` usage form, including after a valid option; unknown long options
retain the parsed option labels in usage.

Modex now advances to the ordinary unexpected-argument parser for those
unrecognized tokens. A recognized option after an incomplete value option,
`--help`, and the bare `--` delimiter retain their missing-value or delimiter
behavior. The process comparison covers split and attached values, unknown
short and long flags, missing values, help order, the delimiter, and a
synthetic API key. Neither process echoed the synthetic key or created state
for these parser cases. Separate post-`exec` Super checks also confirm split
and attached synthetic API-key values are absent from diagnostics.

The process checks use the verified oracle only inside the shared isolated
runner: cleared environment, synthetic `HOME`, empty `PATH`, private tmpfs
storage, and unshared user, mount, and network namespaces with no default
route. These cases make no provider requests and do not start Gateway.

## Reproduction

After building Modex, set `PRODEX_ORACLE` to the checksum-verified 0.166.0
Linux executable and run:

```sh
mojo run -I src tests/test_gateway_cli.mojo
PRODEX_ORACLE=/path/to/verified-0.166.0/prodex-x86_64-unknown-linux-gnu \
MODEX_BINARY=build/modex PYTHONPATH=tests python3 -m unittest \
  test_gateway_default_01660.GatewayDefault01660Tests.test_gateway_parse_diagnostics_match_active_release -v
PRODEX_ORACLE=/path/to/verified-0.166.0/prodex-x86_64-unknown-linux-gnu \
MODEX_BINARY=build/modex PYTHONPATH=tests python3 -m unittest \
  test_super_cli_01660.SuperCli01660Tests.test_post_positional_api_key_errors_do_not_echo_value -v
python3 scripts/ci/check-product-dependencies.py
```

These checks qualify the listed Linux x86-64 argument cases only. They do not
qualify successful Gateway startup, other CLI paths, the remaining release
targets, or overall parity.
