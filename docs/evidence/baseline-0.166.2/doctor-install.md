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

One status difference remains visible: for `PRODEX_OPTIMIZERS_HOME=""`,
Prodex reports `rtk: invalid` while Modex reports `rtk: missing`. Both avoid
executing the working-directory fixture. The regression is asserted explicitly
and does not count as exact parity.

`tests/test_doctor_install_01662.py` is included in the active Fast and Full
test lanes. The historical 0.166.1 `doctor --install` suite remains separately
pinned and unchanged. This evidence covers only the listed synthetic,
read-only inventory cases on Linux x86-64; it does not qualify other doctor
modes, configured profiles, installed tools, or the other five release
targets.
