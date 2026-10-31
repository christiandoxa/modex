# Doctor install inventory against Prodex 0.166.1

The reference is the official `0.166.1` tag at commit
`4951b813ca308fb0ba7148dbc6d6aeb74b93cd32`. Its official `SHA256SUMS` asset
has SHA-256 `2abb8f2854fdc369a06286d55508d0bdf2a1324bd79d78f6015f6e24137b3e60`;
the Linux x86-64 release binary matches the listed and GitHub asset digest
`d9c3232ca504548c473ad06e4be001bb307256e00d35f888676e9512c62e4c3a` and
reports `prodex 0.166.1`.

`test_doctor_install_01661.py` compares the no-tool `doctor --install` panel
with empty `PATH` and synthetic homes. Both processes report the four automatic
tool rows (`rtk`, `codebase-memory-mcp`, `playwright-mcp`, and `ponytail`) as
missing, omit the retired Caveman row, exit successfully, and leave the test
home empty. A second isolated case supplies Node 18 and fake npx, confirms the
Playwright probe uses `--no-install @playwright/mcp --version`, and places a
marker script behind an escaping managed Ponytail symlink. Neither release nor
Modex executes that script. Further cases cover Node 17, repeated `v` prefixes,
invalid UTF-8 and nonzero Node probes, old and unrecognized package versions,
and secret/control output. They verify the package check is skipped for an
unsupported Node, old or unknown packages fail closed, and displayed probe
output is redacted and escaped. No provider credential, real Codex executable,
or network access is available to these subprocesses.

Validation used Mojo `1.2.0 (2016d0cd)`: `make build` passed, all four focused
process tests passed, and `git diff --check` passed. The pre-change Modex binary
failed the inventory test and the new version/output cases.

This is a limited diagnostic slice, not full 0.166.1 Doctor health parity.
Modex checks Node 18+, enforces Playwright MCP 0.0.79 minimum-version semantics,
and bounds and sanitizes the package probe, but does not verify its package
integrity. RTK and Codebase Memory still use PATH version probes without
managed-file integrity or all release health checks. A managed Ponytail path
is reported as degraded without validating its plugin tree; the status is
intentionally not called installed. Other install states and all non-Linux
release targets remain unverified.
