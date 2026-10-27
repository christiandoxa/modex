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
  the focused test pass locally. Verification on the corrective GitHub commit
  is pending; the failed runs are not passes.

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
  corrected commit and the first GitHub run remain pending.

## Fast bootstrap Python selection

- Source: the same uncommitted integration work. The first local fast run failed
  its `compression.zstd` prerequisite even though the selected Python had it.
- Root cause: adding the bubblewrap directory to PATH selected the system
  `python3` instead of the previously selected interpreter.
- Correction: resolve the selected interpreter before changing PATH, and test
  both entrypoints with a deliberately shadowing `python3`.
- Verification: the shadowing regression and corrected local `make ci-fast`
  pass, including the production build, native units, and 13 focused Python
  tests. GitHub verification of the checkpoint remains pending.
