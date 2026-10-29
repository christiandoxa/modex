# Super sub-agent reasoning-effort CLI behavior

Prodex 0.165.1 source at `10ae15b5d1806302b60f051e4e6fec788044f4c2` and frozen
Prodex 0.439.2 source at `72b77478a5198fc5da6b4d2253137f9cdbf43be9` contain the
same `crates/prodex-cli/src/sub_agent.rs` bytes (SHA-256
`b2dca06bae6972c15c9ceb3464c41ac0bd8d69d9dd26ec4b46615f4d3be1c13e`). Its
`SubAgentReasoningEffort::from_str` trims surrounding whitespace, folds ASCII
uppercase to lowercase, accepts `none`, `minimal`, `low`, `medium`, `high`,
`xhigh`, `max`, and `ultra`, and includes the normalized invalid value in its
error.

Before this change, Modex accepted only the exact lowercase spellings and
returned exit 1 with `Error: invalid sub-agent reasoning effort` for invalid
input. It now normalizes accepted values and returns the same exit-2 Clap error
as both releases. Real-process comparisons cover `HIGH` with help, whitespace
around a valid or invalid value, `--option=value`, and a non-ASCII uppercase
character that must not receive Unicode case folding. The error text, exit
status, and empty isolated-home mutation inventory match both release
processes.

The release binaries were verified against their pinned SHA-256 values:

- Prodex 0.165.1: `dd5a4354e067cbbb44e00a2fd1f59843aeb267d17db116e37896d5e305279a51`
- Prodex 0.439.2: `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`

Validation used Mojo 1.2.0 (`2016d0cd`), the native `test_super_cli` parser
check, 26 focused Super CLI process tests against both release binaries, and
all 17 `test_super_launch_01651` process tests with a synthetic Codex fixture.
No credential, provider request, account login, or real Codex executable was
used. This establishes selected Linux x86-64 argument parsing only; it does
not establish sub-agent execution or parity on the other five release targets.
