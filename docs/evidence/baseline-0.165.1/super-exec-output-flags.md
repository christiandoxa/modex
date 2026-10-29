# Super exec output flags

The frozen 0.165.1 and 0.439.2 sources have identical
`crates/prodex-cli/src/runtime_args/optional_tools.rs` (SHA-256
`ee61c41b6ae0472f7e0578576bc053c0524b9f00161f1db0016356dd07f38624`) and
`super_tail_extract.rs` (SHA-256
`09cafefd76c6d210ac5d9b950895e2a86e264a83b10388fd9b10919d98d554fc`).
The former appends Codex arguments after generated provider settings; the latter
preserves the literal `--` boundary while extracting recognized Super options.

The production Super path now forwards selected `exec` arguments: `--json`,
`--color` with `auto`, `always` or `never`, and `--skip-git-repo-check`.
The last flag is forwarded only when explicitly supplied; it tells Codex to
skip its Git-repository check.
The real-process tests compare complete normalized Codex argv and exit status
against each checksum-verified Linux release, including stdin prompt `-` and
literal arguments after `--`. Before the change Modex rejected all six tested
flag combinations before launching. The process fixtures isolate homes, use a
synthetic Codex executable and provider key, make no provider request, and
verify overlay cleanup. They establish launch-argument behavior; they do not
test the actual Codex implementation or the semantics of its output flags.

`-c`, `--config`, `--enable`, `--sandbox` and other unverified arguments remain
fail-closed outside the literal `--` boundary. The tests verify selected
configuration and sandbox overrides do not start a child or provider request.
This is not complete Super argument, tool, startup or platform parity.

Reproduce after `make build` and `make unit-build UNIT_BUILD_PROGRAMS=codex_argv_child`
with `PYTHONPATH=tests python3 -m unittest
test_super_launch_01651.ActiveSuperLaunchTests.test_supported_exec_flags_match_01651
test_super_probe_diagnostic_04392.SuperProbeDiagnostic04392Tests.test_supported_exec_flags_match_04392
test_super_probe_diagnostic_04392.SuperProbeDiagnostic04392Tests.test_exec_unverified_arguments_remain_fail_closed`,
with `PRODEX_ORACLE_01651` and `PRODEX_ORACLE` set to their respective pinned
release binaries.
