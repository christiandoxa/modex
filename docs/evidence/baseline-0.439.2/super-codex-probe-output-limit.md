# Codex probe output limit

The frozen Prodex 0.439.2 source at commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9` wraps failures from
`probe_codex` with `failed to probe Codex CLI at <path>`. Its shared
`command_probe_output` limit is 1 MiB. The verified Linux x86-64 oracle has
SHA-256 `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.

The focused test gives both real binaries the same isolated synthetic Codex
executable. Its `--version` command emits a `codex-cli ` prefix followed by
1 MiB of bytes, crossing the bounded capture limit. Prodex and Modex both exit
1 before `app-server --help`, app-server RPC or provider traffic, leave no
temporary overlay state, and report the same normalized final diagnostic:

```text
Error: failed to probe Codex CLI at <CODEX>: Codex version probe output exceeded the limit
```

Modex now adds this path context to capture errors from both Codex probes.
Nonzero probe exit diagnostics are unchanged. The change imports only the
existing local capture result type and helper; it adds no dependency or
runtime helper.

Reproduce after `make build` with:

```sh
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu" \
  python3 scripts/ci/run-unittest.py test_super_probe_diagnostic_04392.py
```

This establishes the Linux x86-64 oversized-version-probe diagnostic only.
Other Codex failures, the five other release targets, and broader Super
launch parity remain unverified.
