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
Modex executes that script. Another process test places escaping RTK and
Codebase Memory symlinks in the managed root and PATH; both processes report
them as invalid without running either marker. Further cases cover Node 17,
repeated `v` prefixes, invalid UTF-8 and nonzero Node probes, old and
unrecognized package versions, and secret/control output. They verify the
package check is skipped for an unsupported Node, old or unknown packages fail
closed, and displayed probe output is redacted and escaped. No provider
credential, real Codex executable, or network access is available to these
subprocesses.

An empty explicit `PRODEX_OPTIMIZERS_HOME` with an executable `./rtk` in the
working directory is also covered. Prodex reports `invalid` without running
the marker; Modex skips the blank managed root, reports `missing` with PATH set
to a separate empty directory, and leaves the marker absent. A trailing-slash
explicit override that is a symlink to a directory exposes a reference
difference: Prodex follows the root symlink, runs the target RTK, and reports
it installed; Modex rejects the root and does not run the target. Prodex also
follows and runs explicit symlink roots ending in `/.` and `/..`; Modex rejects
the symlink component before probing. With an empty `XDG_DATA_HOME`, both
processes report RTK missing and leave a synthetic tool bound at
`/prodex-optimizers` untouched; Modex skips the blank XDG value instead of
adding that absolute root. Modex-only controls confirm private managed paths
work while group/other-writable roots, non-sticky ancestors, writable
executables, and setuid/setgid managed executables fail closed. Managed path
directories and executables must be owned by the current user or root. Sticky
shared ancestors such as `/tmp` are allowed; a sticky managed root is rejected.
Super dry-run process controls cover the same empty-root handling and reject
writable or setuid/setgid managed RTK/Codebase probes before marker scripts run.
Oracle controls show Prodex 0.165.1 and 0.439.2 report a Codebase tool resolved
under a group-writable `0770` root; Modex intentionally skips it as unsafe.
Modex also rejects a non-executable managed candidate before spawn, while those
Prodex versions report their attempted execution failure.

Validation used Mojo `1.2.0 (2016d0cd)`: `make build
BUILD_DIR=/tmp/modex-probe-01661-build` passed, all ten focused 0.166.1 Doctor
tests, all seven historical 0.166.0 Doctor tests, all 30 Super dry-run
differential tests, and all five managed-root confinement tests passed; `git
diff --check` passed. The pre-change Modex binary failed the inventory test and
the new version/output cases.

This is a limited diagnostic slice, not full 0.166.1 Doctor health parity.
Modex checks Node 18+, enforces Playwright MCP 0.0.79 minimum-version semantics,
and bounds and sanitizes the package probe, but does not verify its package
integrity. RTK and Codebase Memory candidates under managed roots are resolved
before PATH and checked for symlink path components, real-root containment,
current-user/root ownership, safe POSIX mode bits, and safe ancestor directories
before probing; PATH fallback still does not
implement all release health checks. These checks do not make validation and
execution atomic: `capture_with_env` ultimately calls path-based
`posix_spawnp`, so a concurrent process with the same user ID and write access
to the managed path can replace an executable after validation and before
spawn. Mojo 1.2's standard library exposes no descriptor-pinned executable
path, and the tests do not exercise this race. The path-component check also
rejects symlinked operating-system ancestors; valid macOS roots reached through
`/tmp` or `/var` aliases can therefore fail closed. This conservative behavior
has not been qualified on non-Linux targets. The checks do not inspect ACL
policy separately from mode bits. A managed Ponytail path is reported as degraded without validating
its plugin tree; the status is intentionally not called installed. Other
install states and all non-Linux release targets remain unverified.
