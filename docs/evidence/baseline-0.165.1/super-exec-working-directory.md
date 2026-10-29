# Super exec working-directory arguments

The frozen 0.165.1 source at `10ae15b5d1806302b60f051e4e6fec788044f4c2`
and frozen 0.439.2 source at `72b77478a5198fc5da6b4d2253137f9cdbf43be9`
preserve Codex execution arguments in `SuperArgs.codex_args`, leave unknown
arguments in place during Super-option extraction, and append the retained
arguments to the Codex launch. The relevant `launch_args.rs`,
`super_tail_extract.rs`, and `optional_tools.rs` files are byte-identical in
both releases, with SHA-256 values `02b10b769f2e93c703b5d2c7d3e2e714a61c74a11400964367d15a51e5bd279b`,
`09cafefd76c6d210ac5d9b950895e2a86e264a83b10388fd9b10919d98d554fc`, and
`ee61c41b6ae0472f7e0578576bc053c0524b9f00161f1db0016356dd07f38624`.

The production Modex Super path now forwards the tested `exec --cd PATH`,
`exec --cd=PATH`, `exec -C PATH`, and attached `exec -CPATH` forms. It keeps
missing and separate option-looking values guarded before Codex launch. The
test compares complete normalized child launch arguments and exit status with
both checksum-pinned Linux release binaries. It exercises the real Modex
production route with a synthetic Codex child, isolated temporary homes, and
no provider request or real credentials.

Validation on Linux x86-64 with Mojo 1.2.0:

```text
make build
make unit-build UNIT_BUILD_PROGRAMS=codex_argv_child
PYTHONPATH=tests python3 -m unittest test_super_launch_01651.ActiveSuperLaunchTests.test_supported_exec_flags_match_01651 test_super_probe_diagnostic_04392.SuperProbeDiagnostic04392Tests.test_supported_exec_flags_match_04392 test_super_probe_diagnostic_04392.SuperProbeDiagnostic04392Tests.test_exec_unverified_arguments_remain_fail_closed
make ci-dependencies
python3 scripts/ci/check-test-census.py
git diff --check
```

All three focused process methods pass; the production dependency audit covers
71 Mojo files, and the test census finds 50 native sources and 131 Python
modules. The synthetic Codex child records arguments only. It does not verify
that Codex accepts each path or changes its working directory to that path.
Other Codex arguments, Super startup behavior, and non-Linux targets remain
unqualified.
