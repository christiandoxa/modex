# Prodex 0.166.2 doctor --install read-only inventory

`doctor --install` runs on the production CLI path and reports local tool
availability without launching Codex. The focused process checks compare
Modex with the checksum-verified Prodex 0.166.2 Linux oracle
(`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`).
Each process runs under Bubblewrap with isolated `HOME`, `PRODEX_HOME`,
`PRODEX_SHARED_CODEX_HOME`, and tool roots, an empty or synthetic `PATH`, and
no network access or credential variables.

The empty-tool inventory matches exactly, including exit status, stdout, and
stderr, and creates no files. Further fixtures verify that an empty
`XDG_DATA_HOME` does not make `/prodex-optimizers` a probe root; an empty
`PRODEX_OPTIMIZERS_HOME` does not execute a synthetic `rtk` in the working
directory; and the Playwright check invokes `npx --version` before its
`--no-install @playwright/mcp --version` package probe. A synthetic escaping
`ponytail` symlink is observed but never executed. Modex redacts the synthetic
Authorization value and ANSI controls from probe output.

For a private managed RTK binary and a valid Playwright MCP package found by
the no-install npx probe, Modex now matches Prodex's installed version, binary
path, and SHA-256 digest fields. The exact panel comparison covers both a
managed-root RTK and an RTK found on the synthetic `PATH`; a separate fixture
keeps a decoy RTK in the working directory and confirms it is not executed.
Synthetic path and version strings containing a credential-like value and an
ANSI control compare with the oracle after Modex escapes the control. Digests
use the existing 512 MiB file-size limit; larger binaries are reported invalid.

RTK candidates with an unrecognized version line, an unsupported old version,
invalid UTF-8, no output, or a nonzero probe exit remain `invalid`, matching the
release. A recognized but too-old Playwright MCP version reports `invalid`,
while an unrecognized version reports `missing`, matching the release.

Codebase Memory now follows Prodex's health sequence: a supported version must
pass before the `daemon status` probe runs, and both probes have 5-second and
64 KiB-per-stream limits. A successful `daemon: active` result and a
`daemon: not running` result (including a nonzero exit) report the installed
version, path, and digest. Old, failed, empty, or invalid-UTF-8 version probes
and malformed, failed, or invalid-UTF-8 daemon probes report `invalid`;
unsupported versions never invoke the daemon. Synthetic process comparisons
cover both managed and PATH installations, exact version-floor cases, stdout
and stderr, synthetic environment isolation (including `XDG_CONFIG_HOME`), and
redaction of version and daemon output. A managed symlink escaping its root and
a working-directory decoy are not executed.

One output-size difference remains: when `daemon status` writes over 64 KiB
after an active first line, Prodex truncates the captured output and accepts
that line, while Modex's shared process capture rejects output over its limit
and reports `invalid`. The regression records this conservative mismatch.

Another status difference remains visible: for `PRODEX_OPTIMIZERS_HOME=""`,
Prodex reports `rtk: invalid` while Modex reports `rtk: missing`. Both avoid
executing the working-directory fixture. The regression is asserted explicitly
and does not count as exact parity. Neither remaining difference qualifies as
full `doctor --install` parity.

`tests/test_doctor_install_01662.py` is included in the active Fast and Full
test lanes. The historical 0.166.1 `doctor --install` suite remains separately
pinned. This evidence covers only the listed synthetic, read-only inventory
cases on Linux x86-64; it does not qualify other doctor modes, configured
profiles, other installed tools, or the other five release targets.
