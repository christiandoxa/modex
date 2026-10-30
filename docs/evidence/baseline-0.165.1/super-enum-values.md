# Super enum value diagnostics

The `--cli`, `--web-search`, and `--current-time-clock-source` options use
Clap value enums before a positional Codex command in both pinned Prodex
0.165.1 (`10ae15b5d1806302b60f051e4e6fec788044f4c2`) and 0.439.2
(`72b77478a5198fc5da6b4d2253137f9cdbf43be9`). After a positional command,
`crates/prodex-cli/src/runtime_args/super_tail_extract.rs` parses the values
and supplies different runtime errors. Its web-search and clock-source
classifiers accept ASCII case variants; the pre-command Clap enums do not.

Before this change Modex returned exit 1 with a generic error for invalid
pre-command enum values. It now returns the release's exit-2 diagnostic,
possible-values list and tested similar-value suggestions, and uses the
missing-value error for an empty pre-command value. Post-command invalid
values return the observed runtime error, and accepted ASCII case variants
reach Modex's existing guarded startup rather than being rejected as invalid.

`tests/test_super_enum_values_01651_04392.py` compares checksum-pinned
release and Modex processes for separated and attached values, spelling
suggestions, empty and invalid values, positional extraction, valid help, and
help precedence. It uses isolated synthetic homes and no credentials. For a
valid post-command option without a profile, both releases create application
state and reach their no-profile error; Modex instead retains its unsupported
startup guard without those mutations. That launch and state behavior remains a
known difference; the comparison does not claim full Super parity.

The production build, native Super parser check, four cross-release test
methods, 71-file dependency audit, 151-module test census, workflow policy
validation, and diff check passed on Linux x86-64. Other values, protected state,
security behavior, and the other five release targets remain unqualified.
