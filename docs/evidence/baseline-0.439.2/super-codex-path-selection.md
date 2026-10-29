# Codex path selection against Prodex 0.439.2

The frozen reference is Prodex 0.439.2 at
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Its
`crates/prodex-app/src/codex_binary.rs` returns an explicit
`PRODEX_CODEX_BIN` spelling for child launches, searches `PATH` otherwise,
skips Prodex wrappers and known legacy binaries, and resolves the selected
executable to a canonical path for probes. Modex uses the same selected-path
and probe behavior in `src/modex/super_launch.mojo`.

The real-process test runs six selection modes with an isolated synthetic
shebang Codex script: relative path, symlink, command name, an empty `PATH`
entry, default `PATH`, relative `PATH`, and `PATH` with a Prodex wrapper before Codex. Both binaries
return exit 7 after the synthetic child starts; stdout, normalized diagnostics,
probe arguments, process-role sequence, and zero upstream requests match.
Probes see the canonical path in all six modes.

Both binaries now execute the selected spelling or PATH candidate for child
launches while probing the canonical executable. Linux shebang interpreters
therefore receive the same script path in the tested modes. A separate native
fixture verifies raw `argv[0]` against 0.165.1. Neither test runs real Codex.
The selected path can be replaced or a symlink retargeted after the probe;
the executable is not pinned by file descriptor.

Reproduce after `make build` with:

```sh
PRODEX_ORACLE="$HOME/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu" \
PYTHONPATH=tests python3 -m unittest \
  test_super_launch.SuperLaunchTests.test_codex_binary_selection_against_04392_matches_shebang_paths
```

This covers selected Linux x86-64 path modes only. Legacy-binary rejection,
the five other release targets, and complete Super launch parity remain
unverified.
