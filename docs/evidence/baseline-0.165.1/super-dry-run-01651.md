# DeepSeek Super dry-run report against 0.165.1

The Linux Prodex 0.165.1 and 0.439.2 binaries are checksum-pinned by
`tests/test_cli_01651.py` and `tests/test_cli.py`. Their frozen sources are
`10ae15b5d1806302b60f051e4e6fec788044f4c2` and
`72b77478a5198fc5da6b4d2253137f9cdbf43be9`. Both releases build the
`optional-tools` report from launch arguments, choose a Codex command without
validating or starting it, and perform read-only dry-run work. The 0.165.1
implementation is in `crates/prodex-app/src/runtime_tools/super_dry_run.rs`
and `crates/prodex-app/src/codex_binary.rs`.

Modex now accepts the guarded DeepSeek `super --dry-run ... exec` route and
uses one argument builder for the dry-run report and production Codex launch.
It preserves the live launch's `web_search="live"` setting. Dry-run Codex
selection honors `PRODEX_CODEX_BIN`, otherwise selects a recognized executable
from `PATH`, and falls back to `codex` when none is available. It does not
probe or execute Codex, start the local provider relay, or send provider
traffic. The report redacts prompt credentials and temporary paths.

`tests/test_super_dry_run_01651.py` compares complete stdout, stderr, exit
status, and filesystem snapshots using private temporary HOME/workspace roots
and synthetic inputs. With no managed optional tools available, both releases
and Modex produce byte-identical reports for shared config/history, an omitted
model resolved from config, a CLI model override, a configured Codex command,
an absent Codex executable with an empty PATH, and a malformed synthetic API
key alongside an environment key. The tests verify that the CLI model and
`PRODEX_CODEX_BIN` take precedence, the synthetic Bearer prompt is redacted,
the keys are not printed, and the Codex marker is never created.

Optional-tool reporting covers missing tools and validated RTK commands. A
native Mojo Node fixture makes `node --version` available inside bwrap; with no
`npx`, all three processes report the same skipped Playwright status. Modex
selects RTK from managed roots before `PATH`, runs only its bounded
`--version` probe with a five-second timeout, 64 KiB output limits, and the
same filtered environment as Prodex. A synthetic native RTK fixture confirms
managed-root precedence and that unapproved environment values do not reach the
probe.

Three-process comparisons cover supported and old stable versions, a prerelease
below the minimum, malformed version output, stderr-only and empty output,
nonzero exit, secret redaction, and probe timeout. Version and failure status
reports match both pinned releases. On timeout, the status matches; Prodex
includes the executable path in its diagnostic, while Modex redacts that path.
The RTK parser accepts canonical
`rtk [v]X.Y.Z[-prerelease][+build]` lines and fails closed on other banners.
The standard-library process wrapper can kill the direct child but cannot
terminate a descendant process group, so a misbehaving probe that leaves a
descendant running remains an unverified safety gap.

Installed Caveman, codebase-memory-mcp, Ponytail, or Playwright tools remain
fail-closed. Modex does not run `npx --no-install @playwright/mcp --version`,
which both releases use to decide Playwright readiness.

When both Node and `npx` are available, Modex remains fail-closed. The pinned
release runs `npx --no-install @playwright/mcp --version` to decide Playwright
readiness; that starts locally resolved package code. Modex does not run that
user-local code during dry-run, so installed Playwright readiness remains a
visible safety and parity gap.

Separated and attached sensitive CLI flag values and secret-looking proxy
environment values match both releases. A chained control with
`--api-key --password synthetic-secret-42` exposes the synthetic value in both
release reports; Modex masks both the nested flag and its value. This stricter
redaction is an intentional security non-parity, not a byte-for-byte match.

Profile and recovery state remain fail-closed. Both releases can read a
synthetic active profile without changing its state or auth file; Modex exits
because it cannot reconcile a populated profiles directory. For malformed
state, both releases fail after creating `state.json.lock`; Modex fails without
creating a lock. Compatible process locks and atomic recovery APIs are still
unavailable in the permitted Mojo 1.2.0 standard library, so these differences
are not counted as parity.

Validation on Linux x86-64 used both explicit oracle paths:

```sh
make build BUILD_DIR=/tmp/modex-super-launch-build
make unit-build UNIT_BUILD_PROGRAMS='codex_argv_child node_version_fixture optional_tool_version_fixture' BUILD_DIR=/tmp/modex-super-launch-build
MODEX_BINARY=/tmp/modex-super-launch-build/modex \
  PRODEX_ORACLE_01651=/home/doxa/.cache/modex/oracles/0.165.1/prodex-x86_64-unknown-linux-gnu \
  PRODEX_ORACLE_04392=/home/doxa/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu \
  PRODEX_ORACLE=/home/doxa/.cache/modex/oracles/0.439.2/prodex-x86_64-unknown-linux-gnu \
  PYTHONPATH=tests python3 -m unittest -v \
    test_super_dry_run_01651 test_super_launch_01651 test_super_launch
```

The combined run passed 56 tests, including 15 dry-run tests and the historical
and active Super launch modules. After adding the managed-root symlink control,
the 16-test dry-run module passed again. The module is registered in the
historical Python phase of both `scripts/ci/run-fast.sh` and
`scripts/ci/run-full.sh`; it reads `PRODEX_ORACLE_01651` and
`PRODEX_ORACLE_04392` directly. The production import audit passed for 71 Mojo
files, and the test census passed for 50 native test sources and 145 Python
modules. Full repository tests and Fast/Full CI were not run. This qualifies
selected Linux x86-64 behavior only. Other optional-tool states, managed
profile state, shared-history launch, the six baseline target denominator,
and complete Super parity remain open.
