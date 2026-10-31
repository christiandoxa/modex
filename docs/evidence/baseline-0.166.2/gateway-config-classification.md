# Gateway profileless config classification — Prodex 0.166.2

The active reference is Prodex 0.166.2 at
`b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`. The checksum-pinned Linux x86-64
oracle has SHA-256
`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`.

With a synthetic profileless shared Codex config and explicit
`gateway --provider deepseek`, the release treats root
`model_provider = "prodex-deepseek"` as a provider without an
OpenAI-compatible proxy, ignoring ASCII letter case. Leading or trailing
spaces do not match. Every other tested root value, including an ordinary
provider ID, an empty string, an integer, and an array, returns the no-active-
profile diagnostic.

Before this change, Modex matched the lowercase ID only and returned a generic
unsupported-config error for case variants. It also returned that generic
error for non-DeepSeek root values whenever `--provider deepseek` was explicit.
Modex now uses the existing ASCII lowercase helper for exact matching and
reports the observed no-profile diagnostic for all other profileless configs.
Whitespace remains significant. Existing application-state, policy, config
ownership, size, and secure-file checks are unchanged.

`tests/test_gateway_config_classification_01662.py` compares ten synthetic
configurations with the release and Modex. Each process runs in a Bubblewrap
`--unshare-all` network namespace with isolated HOME, app storage, shared Codex
config, and workspace. No API key is supplied and no provider request can
leave the namespace. The test compares exit status and exact stdout/stderr;
it does not claim filesystem-lock parity. Gateway startup, lifecycle locks,
housekeeping, populated profiles, other runtime providers, and the other five
release targets remain unqualified.

Validation on Linux x86-64 used Mojo 1.2.0 (`2016d0cd`): `make build` passed,
the focused test passed its ten oracle/Modex process comparisons, `make unit`
passed, the test census assigned all 240 Python modules to one suite owner,
and the production import audit passed for 74 Mojo files:

```sh
MODEX_BINARY=build/modex \
PRODEX_ORACLE_01662=/path/to/prodex-0.166.2/prodex-x86_64-unknown-linux-gnu \
python3 scripts/ci/run-unittest.py test_gateway_config_classification_01662.py
```

The built Modex binary used for the focused run had SHA-256
`9eacf14be63458e7bbe65ea7808dca6ca1ef122f0ba7f7293dbe217512cf358b`.
