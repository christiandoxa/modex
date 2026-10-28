# Codex CLI minimum version control

The frozen Prodex 0.439.2 source at commit
`72b77478a5198fc5da6b4d2253137f9cdbf43be9` requires Codex `0.153.2` or newer.
It parses the rightmost version-like token from stdout plus stderr before
running `codex app-server --help`.

`tests/test_super_probe_diagnostic_04392.py` compares the verified Linux
x86-64 oracle and Modex with one isolated synthetic Codex executable. A
`0.153.1` response stops after `--version` and matches the oracle's final
minimum-version diagnostic. An exact-minimum `0.153.2` response in stderr,
with a case-insensitive label and trailing punctuation, reaches app-server
help and the synthetic launch in both binaries. Component forms `0.+153.2`
and `0.153.+2` are also accepted. When `--version` exits 7, Modex matches
Prodex's status, path, and install guidance. The tests run in a mode-0700 temp
directory nested below a private temp root. Prodex emits startup progress
before rejection; Modex does not, so the low-version check compares only the
final error line. No provider request or temporary overlay remains.

Hosted Fast CI run `40788779491` exposed a diagnostic normalizer that assumed
fixtures were directly under `/tmp`. The shared normalizer now handles nested
private temp roots; this suite exercises that layout.

Reproduce after `make build` with:

```sh
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu" \
  python3 scripts/ci/run-unittest.py test_super_probe_diagnostic_04392.py
```

The Codex executable and upstream are synthetic. This Linux x86-64 control
does not establish broader startup parity or the other five release targets.
