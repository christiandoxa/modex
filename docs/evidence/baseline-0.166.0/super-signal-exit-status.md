# Super child signal exit status (Prodex 0.166.0)

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

The reference is official Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`.

The source path in `crates/prodex-app/src/runtime_launch/execution.rs` returns
the completed child through `exit_with_status`. In
`crates/prodex-app/src/app_commands/child_process.rs`, `child_exit_code` returns
the ordinary exit code or, on Unix, `128 + signal`, with 1 as a final fallback.
Modex already uses the same conversion for probe failures, but its Super
runtime launch returned 1 whenever the child lacked an ordinary exit code.
`_exec` now uses `_child_exit_code` for the reaped child status too.

The process comparison uses a synthetic Codex executable that sends SIGTERM to
itself. Before the fix, Prodex returned 143 and Modex returned 1. The focused
regression now compares the checksum-verified Prodex process and Modex binary:
both return 143 for SIGTERM and 7 for an ordinary exit-seven control. The
fixture uses private temporary HOME, config and storage directories and a
synthetic loopback peer, which receives no requests. No real Codex account or
provider traffic is used.

Validation on Linux x86-64:

- `make BUILD_DIR=<isolated-build-dir> build` — passed.
- `MODEX_BINARY=<built-modex> PRODEX_ORACLE=<verified-0.166.0-linux-binary> PYTHONPATH=tests python3 -m unittest -v test_super_launch_01660` — 1 test passed with signal and ordinary-exit controls.
- `python3 scripts/ci/check-product-dependencies.py` — passed.
- `git diff --check` — passed.

This qualifies Unix child signal-to-exit-code propagation for the tested
SIGTERM case, with ordinary exit-seven behavior as a control. Other signals
and non-Linux targets remain unqualified; approval and sandbox arguments, child
cleanup and provider routing are unchanged.
