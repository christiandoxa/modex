# Super exec worktree and configuration arguments

Prodex 0.165.1 at `10ae15b5d1806302b60f051e4e6fec788044f4c2` and
0.439.2 at `72b77478a5198fc5da6b4d2253137f9cdbf43be9` define
`SuperArgs.codex_args` in `crates/prodex-cli/src/runtime_args/launch_args.rs`
as hyphen-valued arguments passed after generated Codex options. Both pinned
Linux binaries forwarded `--strict-config`, `--worktree`, and
`--thread-source=synthetic` to a synthetic Codex child. The previous Modex
build rejected each before starting the child.

Modex now forwards these two switches and a nonempty `--thread-source` value
in separate or attached form through its existing guarded DeepSeek Super exec
path. The selected `--` control keeps later option-looking text literal. Missing,
empty, and option-looking separate thread-source values remain guarded; the
releases defer such Codex argument errors to their child.

`test_super_launch_01651.ActiveSuperLaunchTests.test_supported_exec_flags_match_01651`
and `test_super_probe_diagnostic_04392.SuperProbeDiagnostic04392Tests.test_supported_exec_flags_match_04392`
compare normalized child arguments and generated configuration with both
checksum-pinned binaries. The guarded-invalid test checks that malformed values
do not start a child. Tests use temporary homes, a synthetic key and child, and
loopback fixtures without provider traffic. The synthetic child verifies the
wrapper's argument order and exit behavior; it does not run Codex, create a
worktree, or establish the semantics of Codex's configuration and thread
source. Other exec arguments, the other release targets, and full Super parity
remain unverified.

On Linux x86-64, the production build, both release comparison methods, the
guarded-invalid method, the 71-file production import audit, and the test census
(50 native sources and 140 Python modules) passed. The three process methods
completed in 104.073 seconds. `git diff --check` passed.
