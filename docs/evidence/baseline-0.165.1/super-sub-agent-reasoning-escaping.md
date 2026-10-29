# Super reasoning-effort error escaping

Prodex 0.165.1 and frozen Prodex 0.439.2 use identical
`crates/prodex-cli/src/sub_agent.rs` bytes (SHA-256
`b2dca06bae6972c15c9ceb3464c41ac0bd8d69d9dd26ec4b46615f4d3be1c13e`). Invalid
reasoning-effort messages include Rust `Debug` formatting of the normalized
input. Clap also filters most C0 and DEL controls from the outer `invalid
value` field and strips ANSI CSI sequences there.

Before this follow-up, Modex escaped the inner value as JSON (`\u0001`, `\b`,
`\f`) and printed raw control characters in the outer value. Modex now matches
both release processes for every non-NUL C0 and C1 value, DEL, quotes,
backslashes, simple ESC/CSI input, and printable Unicode (including U+0130 and
emoji). The process tests compare return code and complete stdout/stderr with
each release. All cases run in isolated homes and leave no filesystem
mutations.

The probes also identify limits that remain open:

- Rust escapes non-ASCII nonprintables and grapheme extenders, including
  U+0301, U+200B, U+2028, U+E000, and unassigned U+0378. Modex leaves these
  codepoints literal inside the quoted reason because the project has no
  versioned Rust-compatible printability table.
- OSC sequences are not fully stripped from the outer diagnostic. For
  `a\u001b]2;title\u0007b`, both releases display outer value `ab`; Modex
  displays `a2;titleb`.
- NUL cannot be passed in an OS argument, so that input was not process-tested.

The release binaries were verified against their pinned SHA-256 values:

- Prodex 0.165.1: `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
- Prodex 0.439.2: `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`

Validation used Mojo 1.2.0 (`2016d0cd`), the `test_super_cli` native parser
test, and the focused real-process tests in
`test_cli.HistoricalSuperProviderCliTests` and
`test_cli_01651.SuperProviderCli01651Tests`. No credentials, provider traffic,
account login, or real Codex executable were used. This is selected Linux
x86-64 CLI diagnostic behavior, not full Unicode debug-string or Super parity.
