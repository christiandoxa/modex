# Codex reasoning effort through Super

Prodex 0.165.1 (`10ae15b5d1806302b60f051e4e6fec788044f4c2`) and frozen
Prodex 0.439.2 (`72b77478a5198fc5da6b4d2253137f9cdbf43be9`) retain Codex tail
arguments in `SuperArgs.codex_args`. Their tail scanner consumes recognized
Super overrides and leaves `--reasoning-effort` for Codex. Real-process probes
confirmed both releases preserve separate and attached forms, including when
the flag follows the prompt or the literal `--` delimiter.

Modex now admits `--reasoning-effort VALUE` and `--reasoning-effort=VALUE` in
the guarded DeepSeek `exec` path. It forwards the original argument tokens to
Codex and leaves value validation to Codex, matching both references for
normal, empty, malformed, missing, option-looking and delimiter-separated
values. Captured app-server argv and generated settings match both pinned
releases. A synthetic API key supplied as a tail `--api-key` remains a Super
override; it does not enter Codex argv, config, environment, auth or runtime
config.

Tests use isolated synthetic homes and a synthetic Codex child. The launch
matrix exits through the fixture with status 7 and records no upstream request.
The dry-run matrix compares complete stdout across both releases and Modex,
checks the filesystem snapshot is unchanged, and verifies the Codex marker was
not created. No real credentials, provider traffic or account login are used.

Validation was on Linux x86-64 only. Invalid and missing values are verified
as pass-through tokens; the synthetic child does not validate Codex's own
diagnostics. Other Codex options, the remaining release targets, and full
Super parity remain open.

Reproduce after building Modex and the native fixtures:

```sh
make build BUILD_DIR=/tmp/modex-super-parity-build-20261030
make unit-build UNIT_BUILD_PROGRAMS='codex_argv_child node_version_fixture optional_tool_version_fixture' BUILD_DIR=/tmp/modex-super-parity-build-20261030
MODEX_BINARY=/tmp/modex-super-parity-build-20261030/modex \
  PRODEX_ORACLE_01651=/home/doxa/.cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu \
  PRODEX_ORACLE_04392=/home/doxa/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu \
  PRODEX_ORACLE=/home/doxa/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu \
  PYTHONPATH=tests python3 -m unittest -v \
    test_super_dry_run_01651.SuperDryRun01651Tests.test_codex_reasoning_effort_is_preserved_in_dry_run \
    test_super_launch_01651.ActiveSuperLaunchTests.test_supported_exec_flags_match_01651 \
    test_super_launch_01651.ActiveSuperLaunchTests.test_reasoning_effort_keeps_provider_key_out_of_codex_launch \
    test_super_launch.SuperLaunchTests.test_deepseek_api_key_environment_resolution_and_child_scrubbing
```
