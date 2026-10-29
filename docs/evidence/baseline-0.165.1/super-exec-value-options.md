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
request. Modex's synthetic process test verifies missing, option-looking, and
empty values fail before creating an overlay or launching Codex.

One local characterization on 2026-10-29 used the installed Codex CLI 0.165.0
at `/home/doxa/.local/share/upkit/node/24.22.1/node-v24.22.1-linux-x64/lib/node_modules/@openai/codex/bin/codex.js`.
The temporary harness in `tests/test_super_probe_diagnostic_04392.py` delegated
the release child to that binary and observed the pinned releases exit 2 with
Codex's missing-value diagnostic, while Modex stopped before child launch.
That environment-dependent test was removed from the suite; this observation
is local evidence only. It was invoked as
`PYTHONPATH=tests python3 -m unittest test_super_probe_diagnostic_04392.SuperProbeDiagnostic04392Tests.test_invalid_add_dir_values_are_checked_by_the_release_codex_child`
from commit `cc079d9`; inspect that commit's test source for the temporary
fixture. Codex CLI 0.165.0's `codex exec --help` documents the value-taking
`--add-dir <DIR>` option. No provider request or leftover overlay was observed.

Validation on Linux x86-64 with Mojo 1.2.0:

```text
make build
make unit-build UNIT_BUILD_PROGRAMS=codex_argv_child
PYTHONPATH=tests python3 -m unittest test_super_launch_01651.ActiveSuperLaunchTests.test_supported_exec_flags_match_01651 test_super_probe_diagnostic_04392.SuperProbeDiagnostic04392Tests.test_supported_exec_flags_match_04392 test_super_probe_diagnostic_04392.SuperProbeDiagnostic04392Tests.test_exec_unverified_arguments_remain_fail_closed
make ci-dependencies
python3 scripts/ci/check-test-census.py
git diff --check
```

The removed Codex child characterization is not part of the automated
validation command above.

Other Codex `exec` arguments remain guarded. The synthetic fixture verifies
wrapper argument preservation; the local Codex characterization does not
verify model inference or broader Codex runtime effects.
