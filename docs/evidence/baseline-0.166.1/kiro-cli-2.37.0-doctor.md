# Kiro CLI 2.37.0 Doctor probe

> Historical evidence: the active target is Prodex 0.166.2. References to 0.166.1 as active describe the original capture.

Prodex 0.166.1's `doctor --install` calls `kiro_bin()` with `--version`.
`crates/prodex-app/src/lib.rs` selects `PRODEX_KIRO_BIN` when set, otherwise
prefers `kiro-cli-chat`, falls back to `kiro-cli`, and defaults to
`kiro-cli-chat`. The official release's
`migration/kiro-cli-2.37.0-source-evidence.json` records successful isolated
`--version` probes for both official launchers and qualifies the Linux archive
from the current stable manifest.

Modex's connected `doctor --install` path uses the same override, preferred
launcher, and fallback order. `test_kiro_cli_2370_01661.py` compares that
production path with the checksum-pinned 0.166.1 oracle using synthetic
`--version` commands that report `kiro-cli 2.37.0`. It verifies launcher
preference, fallback, explicit override, the displayed version row, and no
home-state mutation. The tests use an isolated HOME, synthetic environment,
and network namespace; they do not install, update, or log into Kiro.

This slice covers only the Doctor version probe on Linux x86-64. It does not
qualify Kiro runtime routing, ACP behavior, or execution on other targets.
