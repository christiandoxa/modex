# Super exec value options

The frozen Prodex 0.165.1 source at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and Prodex 0.439.2 source at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`
keep hyphenated Codex arguments in `SuperArgs.codex_args` with
`allow_hyphen_values = true`. Their Super launch paths append those arguments
after generated Codex settings. Codex CLI 0.165.0 help documents `--add-dir`,
`--enable`, and `--disable`; its parser accepts repeated options, attached
values, and options after the prompt.

Modex now passes those three one-value, repeatable options unchanged through
its guarded DeepSeek `exec` path, in separated or `--option=value` form. The
values stay in child argv and do not alter Modex-generated `-c` configuration.
The guard rejects missing, empty, or option-looking separate values. A lone
dash value remains valid. A `--` separator ends option inspection and keeps
the following prompt literal.

The process tests compare normalized child argv and generated configuration
against both checksum-pinned release binaries. Their isolated homes, synthetic
loopback upstream, synthetic key, and Codex fixture produce no provider
request. A separate fixture delegates only final child execution to the
installed Codex CLI 0.165.0: for missing, option-looking, and empty `--add-dir`
values, both releases launch Codex and Codex exits 2 with its missing-value
diagnostic. Modex rejects these inputs before creating an overlay or launching
Codex, with its generic Super startup guard. This deliberate preflight
diagnostic difference remains visible; no network request or state remains.

Validation on Linux x86-64 with Mojo 1.2.0:

```text
make build
make unit-build UNIT_BUILD_PROGRAMS=codex_argv_child
PYTHONPATH=tests python3 -m unittest test_super_launch_01651.ActiveSuperLaunchTests.test_supported_exec_flags_match_01651 test_super_probe_diagnostic_04392.SuperProbeDiagnostic04392Tests.test_supported_exec_flags_match_04392 test_super_probe_diagnostic_04392.SuperProbeDiagnostic04392Tests.test_exec_unverified_arguments_remain_fail_closed test_super_probe_diagnostic_04392.SuperProbeDiagnostic04392Tests.test_invalid_add_dir_values_are_checked_by_the_release_codex_child
make ci-dependencies
python3 scripts/ci/check-test-census.py
git diff --check
```

Other Codex `exec` arguments remain guarded. The fixture verifies wrapper
argument preservation and Codex CLI parsing, not model inference or broader
Codex runtime effects.
