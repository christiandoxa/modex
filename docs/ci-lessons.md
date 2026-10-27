# CI lessons

## GitHub Ubuntu sandbox setup

- Source: `d4a50b3c1822d189aba94d53ce4db24beefa75bd`. Fast CI run
  [40564880852](https://github.com/christiandoxa/modex/actions/runs/40564880852),
  attempt 1, job `122403376018`, and Full CI run
  [40564952057](https://github.com/christiandoxa/modex/actions/runs/40564952057),
  attempt 1, job `122403639164`, failed during bootstrap. Both reported
  `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`; sanitized
  evidence was uploaded by each run.
- Classification: runner sandbox setup. Ubuntu 24.04 mediates unprivileged
  user namespaces through AppArmor; extracting the Bubblewrap binary did not
  install or load its restricted profile.
- Correction: before checkout, both workflows install Ubuntu's Bubblewrap and
  AppArmor profiles and load `bwrap-userns-restrict`, following the
  [documented Ubuntu sandbox setup](https://github.com/openai/codex-security/blob/main/github-action/README.md#ubuntu-sandbox-setup).
  The profile retains child capability restrictions and the mandatory
  filesystem and network namespace probes remain in place.
- Regression: `tests/test_ci_sandbox_setup.py` checks setup order, literal
  commands, read-only permissions and the namespace probe. Actionlint and
  the focused test pass locally. GitHub Fast CI run
  [40566529600](https://github.com/christiandoxa/modex/actions/runs/40566529600),
  attempt 1, passed on corrective commit `8b15ace3593f6fc808ce23cbf2bbf9f32f6370fc`.
  The exact-SHA Full CI run `40566557490` is still in progress.

## Unsafe-directory fixture and private umask

- Source: exact `d4a50b3c1822d189aba94d53ce4db24beefa75bd` in an isolated
  worktree. Local full validation passed all native tests and 383 of 384
  Python tests. `test_unsafe_existing_app_root_reports_known_repair_gap` failed.
- Root cause: the new private scratch sets umask `077`, so a fixture requested
  as mode `0755` was actually created as `0700` and did not exercise the
  intended unsafe-directory case.
- Correction and regression: the test explicitly sets and asserts `0755`
  before invoking both real binaries. It passes under the private umask and
  continues to check the known Modex permission-repair gap.
- GitHub Full CI run [40566557490](https://github.com/christiandoxa/modex/actions/runs/40566557490),
  attempt 1 on `8b15ace`, reproduced the same failure; the focused correction
  was pushed as `c5cde1cd19bc2f0072b2f1f1507f429d61bf4593`. The correction
  passed in exact-SHA Full CI run
  [40570838793](https://github.com/christiandoxa/modex/actions/runs/40570838793)
  after the later width-memory measurement fix; the earlier exact-SHA run
  `40569480632` failed only the width-memory check described below.

## GitHub width-memory threshold

- Source: Full CI run `40566557490`, attempt 1, Linux job, on `8b15ace`.
  The width working-set test also failed: ASCII measured 1,572,864 bytes of
  normalized growth against 193,331 allowed bytes. The detailed width RSS
  JSON was not included in the uploaded evidence, but the failure summary and
  samples are retained in the run log.
- Classification: measurement-harness error. The old check subtracted logical
  string bytes from RSS, even though allocator residency can change with input
  size. On a pinned optimized build, an input-construction-only control showed
  the same growth without calling `text_width`.
- Correction: the same native driver measures input construction alone and
  compares its growth with the width run. Width and control results remain
  asserted, with the original noise and 1% bound. Full CI now uploads the
  detailed RSS JSON. The pre-correction Full CI run
  [40569480632](https://github.com/christiandoxa/modex/actions/runs/40569480632)
  on `c5cde1c` reproduced the old check's ASCII failure: 1,523,712 bytes of
  normalized growth against 394,035 allowed. The input-only control was added
  afterward.
- Verification: exact-SHA Fast CI run
  [40570794170](https://github.com/christiandoxa/modex/actions/runs/40570794170)
  and Full CI run
  [40570838793](https://github.com/christiandoxa/modex/actions/runs/40570838793)
  passed on `62b554cb93c477655581ea93d4f2d78a8b042fc4`; Full CI passed all 387
  tests. Its artifact includes `width-rss.json`: ASCII normalized auxiliary
  growth was 172,032 bytes against 611,123 allowed, and all four other patterns
  were within their recorded limits. All five patterns and a current-oracle
  mixed session comparison also pass locally.

## Initial 0.439.5 local full run

- Source: uncommitted integration work based on `0eacd2cb8da155a4bf418186e1bcdac5f27d4138`;
  no GitHub run existed. The Linux full entrypoint built production and all
  native units, then reported 138 Python failures and two errors in 382 tests.
- First actionable failure: the oracle rejected a synthetic runtime capability
  file before any upstream POST. The run's inherited temporary parent was
  group-writable (`0775`); the frozen secret backend rejects non-sticky writable
  parent directories. Multiple downstream failures shared this condition.
- Correction: fast and full CI now create a private scratch tree beneath the
  root-owned sticky `/tmp`; they isolate HOME, temporary and XDG paths without
  changing existing directory permissions. A real-oracle regression starts
  from an unsafe inherited temporary directory and requires the synthetic
  request to complete. The original failing annotation case passes with the
  same compiler and verified reference under the corrected scratch setup.
- Six session CLI fixture cases also depended on temporary path length and
  terminal wrapping. They now compare the current oracle and Modex at the same
  short and long paths, retaining the historical fixture. Two follow-on
  comparison errors now report an explicit missing observation count.
- Verification: focused regressions passed locally. Full validation of the
  corrected checkpoint passed in Full CI run
  [40570838793](https://github.com/christiandoxa/modex/actions/runs/40570838793)
  on `62b554cb93c477655581ea93d4f2d78a8b042fc4`: all 387 tests and capability
  probes passed.

## Fast bootstrap Python selection

- Source: the same uncommitted integration work. The first local fast run failed
  its `compression.zstd` prerequisite even though the selected Python had it.
- Root cause: adding the bubblewrap directory to PATH selected the system
  `python3` instead of the previously selected interpreter.
- Correction: resolve the selected interpreter before changing PATH, and test
  both entrypoints with a deliberately shadowing `python3`.
- Verification: the shadowing regression and corrected local `make ci-fast`
  pass, including the production build, native units, and 13 focused Python
  tests. Exact-SHA Fast CI run
  [40570794170](https://github.com/christiandoxa/modex/actions/runs/40570794170)
  passed on `62b554cb93c477655581ea93d4f2d78a8b042fc4`.
