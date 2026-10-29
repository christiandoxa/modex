# Codex path selection against Prodex 0.439.2

The frozen reference is Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Its
`crates/prodex-app/src/codex_binary.rs` returns an explicit
`PRODEX_CODEX_BIN` spelling for child launches, searches `PATH` otherwise,
skips Prodex wrappers and known legacy binaries, and resolves the selected
executable to a canonical path for probes. Modex uses the same selected-path
and probe behavior in `src/modex/super_launch.mojo`.

The real-process test runs six selection modes with an isolated synthetic
shebang Codex script: relative path, symlink, command name, default `PATH`,
relative `PATH`, and `PATH` with a Prodex wrapper before Codex. Both binaries
return exit 7 after the synthetic child starts; stdout, normalized diagnostics,
probe arguments, process-role sequence, and zero upstream requests match.
Probes see the canonical path in all six modes.

Linux shebang scripts expose an interpreter-visible `sys.argv[0]` difference
for the explicit relative path, symlink, and command-name modes. Prodex's child
script sees the selected spelling or PATH candidate. Modex spawns the
canonical executable and passes the selected spelling as `argv[0]`; Linux
uses the executable pathname for the shebang script, so its interpreter sees
the canonical path. Default `PATH`, relative `PATH`, and wrapper-skipping
child paths match. This test records the known shebang gap; it does not run a
real Codex binary or qualify native-binary behavior against 0.439.2.

Reproduce after `make build` with:

```sh
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu" \
PYTHONPATH=tests python3 -m unittest \
  test_super_launch.SuperLaunchTests.test_codex_binary_selection_against_04392_records_shebang_path_gap
```

This covers selected Linux x86-64 path modes only. Legacy-binary rejection,
the five other release targets, and complete Super launch parity remain
unverified.
