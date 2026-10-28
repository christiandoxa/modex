# CI lessons

## Pinned source recovery does not restore the oracle

- On 2026-10-28, `git ls-remote https://github.com/christiandoxa/prodex
  refs/tags/0.439.2 'refs/tags/0.439.2^{}'` and the equivalent `0.439.1`
  lookup both exited successfully with empty stdout. The source helper then
  fetched only commits `72b77478a5198fc5da6b4d2253137f9cdbf43be9` and
  `81c1a01933bc33f536a24452c3fd72c3f8d0b1f3`, respectively. It verified each
  checkout's HEAD and every tracked file against the pinned Git tree; the
  second active-source invocation verified the existing cache. No Prodex
  source code was executed and the test cache was temporary.
- Reproduction: `python3 scripts/ci/reference.py source active` and
  `python3 scripts/ci/reference.py source 0.439.1`, with
  `MODEX_REFERENCE_CACHE` set to an empty temporary directory. Focused check:
  `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_ci_reference`
  passed all 27 tests, including absent, moved, malformed and failed lookup
  cases; replace-ref, local URL rewrite, and Git fsmonitor/filter execution
  controls also passed.
- The oracle command with the same empty cache,
  `python3 scripts/ci/reference.py oracle active`, exited 1 with
  `official Prodex tag 0.439.2 is missing; expected frozen commit
  72b77478a5198fc5da6b4d2253137f9cdbf43be9. The baseline reference is
  unavailable; refusing to substitute another version.` No oracle cache entry
  was created. This source-only path does not provide the pinned Linux binary,
  and Fast CI currently checks the oracle before acquiring source. The missing
  official binary remains an open CI blocker and no parity claim follows.
- Captured command results and the exact pinned binary digests are recorded in
  `docs/evidence/reference-source-fallback-20261028.json`.
- Cache verification conservatively rejects tracked symlinks to existing
  directories because `os.walk` classifies them as directories. The recovered
  0.439.2 and 0.439.1 snapshots passed; generic support for this Git-tree edge
  is deferred.
- Fast run [40641725411](https://github.com/christiandoxa/modex/actions/runs/40641725411),
  attempt 1 on `6baf72fd1c2bece878a5e2024ac3a7f039653b86`, passed workflow
  validation, the dependency audit, and all 27 reference-helper tests. It then
  failed acquiring the missing 0.439.2 oracle before source acquisition or
  build; artifact consumers were skipped. Evidence artifact `12795867683`
  and logs are preserved under `/tmp/modex-ci-40641725411/`. The hosted run
  does not validate the source fallback with the official remote.

## Frozen release disappeared and width-control calibration

- Fast run [40628355469](https://github.com/christiandoxa/modex/actions/runs/40628355469),
  attempt 1, job `122618621832`, failed on `2b6fe89`: the read-only
  `git ls-remote` tag check returned no `0.439.2` ref. GitHub's release and
  tag APIs and the recorded SHA256SUMS URL independently return 404, while
  the frozen source commit archive remains available. The artifact-consumer
  jobs did not run. Previously acquired official local bytes still match
  SHA-256 `a545b602bddfbbc2b4455d8dd7e97263e9c49747fa9d1d6b94011e73971d2a5e`.
  Reference acquisition remains fail-closed; a durable verified source for
  those same official bytes and hosted verification are unresolved. Logs and
  uploaded evidence were retained under `/tmp/modex-ci-failures-20261028/`.
  Fast run [40629714742](https://github.com/christiandoxa/modex/actions/runs/40629714742),
  attempt 1, job `122623006721`, failed the same check on `f1b8181`;
  the artifact consumers again did not run. The historical `0.439.1` tag is
  also absent. Fast run
  [40631003222](https://github.com/christiandoxa/modex/actions/runs/40631003222),
  attempt 1, producer job `122627098427`, failed the same lookup on exact SHA
  `84e4777e033742d3637bbfe0b8e3cd1d3d1ad668`; consumer job `122628130127` was
  skipped. A focused diagnostic now distinguishes an absent tag from a moved
  tag or remote lookup error without changing fail-closed behavior. Ten local
  reference tests pass, and a clean-snapshot invocation reproduces the
  explicit unavailable-baseline failure. Run logs and uploaded evidence are
  retained under `/tmp/modex-ci-40631003222/`; the earlier run's evidence is
  under `/tmp/modex-ci-40628355469/`.
- A read-only investigation recovered the exact official Linux executables
  from Prodex's successful standalone-release Actions runs. Artifact
  `12641885680` from run `40300566491`, source commit `72b77478a5198fc5da6b4d2253137f9cdbf43be9`,
  contains a binary matching the recorded 0.439.2 SHA-256 above; the artifact
  ZIP SHA-256 is `db47114338b74ab058ce2ee2ae029f1d1b85216acfb24c59cacedc9f1b196f6c`.
  Artifact `12593400004` from run `40177799086`, source commit
  `81c1a01933bc33f536a24452c3fd72c3f8d0b1f3`, contains a binary matching the
  historical 0.439.1 SHA-256
  `b4511d679dd6da53f706400dba5b368ffc5b5663f8764fa0c8f148b358b9255a`;
  its ZIP SHA-256 is `7287a1236e2db47ab55c9856032608de7779533ec031fc0df1267ccbfc0d6adc`.
  Both artifacts were downloaded read-only into the local failure-evidence
  directory. Their reported expiration dates are 2026-11-02 and 2026-11-01,
  respectively. Anonymous artifact download returns HTTP 401, so this does
  not establish a durable, credential-free CI bootstrap.
- Full run [40625731794](https://github.com/christiandoxa/modex/actions/runs/40625731794),
  attempt 1, job `122610058523`, failed on `865815c`: 458 of 459 Python tests
  passed, while the width-memory test's transient minor-fault positive control
  observed 2 events for Kirat against 3 required, and 2 for emoji-tag against
  4 required. Raw measurements were uploaded and retained locally. This is a
  test-calibration failure, not proof of a product memory regression; the
  positive-control sensitivity must be repaired and revalidated without
  weakening the actual memory bound.
- The 4-byte-per-input-unit control is retained. The test harness now disables
  transparent huge pages only in each measurement child, verifies the kernel
  reports `THP_enabled: 0` at both samples, and fails if it cannot establish
  that condition. The noise threshold and width bounds are unchanged. A local
  exact-size control produced 513–514 minor-fault events for Kirat and emoji
  against zero for input-only samples; all ten `test_text_memory.py` tests
  passed with the pinned compiler and actual 0.439.2 oracle. This measures
  base-page behavior and does not qualify allocation behavior with THP enabled.
  Hosted verification of the correction is pending.

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

- Fast run [40606177561](https://github.com/christiandoxa/modex/actions/runs/40606177561)
  on `78472bb` failed the fault positive-control check on all five patterns.
  All width and anonymous-control checks passed. For large Tifinagh, the
  control grew 4,194,304 bytes in `AnonHugePages` while minor faults increased
  by two; multiplying by the 4 KiB base page size cannot measure that growth.
  ASCII's control measured 61,440 bytes of fault equivalents against an 86,835
  byte allowance, and the other four measured 8,192 bytes each against bounds
  of 65,536–90,112 bytes. The artifact is retained locally under
  `/tmp/modex-ci-failure-40606177561/`. The previous 49 Fast focused tests
  passed. A control passing only anonymous residency does not validate the
  ability to catch huge-page allocations freed before the post-operation sample.
  Full run [40606182672](https://github.com/christiandoxa/modex/actions/runs/40606182672)
  on the same SHA passed all 429 Python tests. Its controls showed no
  `AnonHugePages` growth, so that pass does not resolve the Fast failure.
- The staged harness failed Fast run
  [40603196899](https://github.com/christiandoxa/modex/actions/runs/40603196899)
  and Full run [40603202733](https://github.com/christiandoxa/modex/actions/runs/40603202733)
  on `0267116`; the other 428 Full tests passed. The Fast artifact shows that
  large Tifinagh width samples gained 1.28–1.43 MiB of total peak RSS, but
  anonymous RSS grew 4 KiB and minor faults increased by one. File-backed
  pages accounted for most of the resident growth. The transient control
  instead gained about 2.1 MiB of anonymous RSS and roughly 514 minor faults.
  Both runs uploaded detailed measurements. Local copies are retained under
  `/tmp/modex-ci-failure-40603196899/` and `/tmp/modex-ci-failure-40603202733/`.
- A follow-up checks anonymous-residency growth and minor-fault page equivalents
  independently, with the existing allowance applied to each and a transient
  positive control required for both. Local tests and replay of both hosted
  artifacts passed; hosted validation is pending. The metrics can miss reused
  resident allocator pages, huge pages change fault-to-byte ratios, and minor
  faults can also count file or code pages. They do not prove allocation-free
  execution.
- The revised `/proc` harness failed Full run
  [40597916331](https://github.com/christiandoxa/modex/actions/runs/40597916331)
  on `610236a`. Tifinagh width growth was 3,342,336 bytes against a 2,392,064
  bound; the 4-byte-per-unit control was below the sample-noise bounds for
  mixed and Kirat. All other 428 tests passed. Samples are preserved in the
  uploaded `width-rss.json` and locally under
  `/tmp/modex-ci-failure-40597916331/`. This does not establish the cause or
  rule out a real production allocation.
- Local probes show that VmHWM can include 2 MiB huge-page steps and file-backed
  pages and can undercount brief allocations; the hosted artifact has no RSS
  category data to identify the source. Source review and local allocator
  variations found no input-scaled Tifinagh allocation, but did not reproduce
  the hosted environment. A follow-up same-process baseline and post-operation
  harness with a touched and freed allocation control passed locally across
  all five patterns, including with a 96 MiB parent. It records VmHWM, minor
  faults and optional memory-map diagnostics; the allowance formula is
  unchanged. An independent reuse probe showed that both VmHWM and minor
  faults can miss allocations served from resident allocator pages. The test
  measures additional resident high-water, not all allocations, and needs
  hosted validation.
- Exact-SHA Full run [40593599708](https://github.com/christiandoxa/modex/actions/runs/40593599708)
  on `b046394` also failed the earlier Tifinagh check, measuring 1,384,448
  bytes against 507,904 allowed; the other 427 tests passed.
- Full run [40591839335](https://github.com/christiandoxa/modex/actions/runs/40591839335)
  on `663926f` failed the same Tifinagh check: normalized growth was
  3,125,248 bytes against 2,658,304 allowed. A later local probe showed that
  Linux `wait4` can report a child's inherited Python-parent peak after exec.
  A 96 MiB touched parent gave `/bin/sleep` a 104.5 MiB `wait4` peak while
  its post-exec `/proc` VmHWM was 400 KiB. This mechanism can mask input-only
  growth and distort the subtraction; it has not been proven to explain every
  hosted sample.
- The revised harness samples `/proc/<pid>/status` VmHWM after confirming the
  driver executable and holds the driver until the sample is taken. A
  4-byte-per-unit positive control exceeds the existing bound for all five
  patterns locally, both normally and with a 96 MiB touched parent. The bound
  is unchanged. The control demonstrates coarse sensitivity, not detection
  of a 1% allocation; hosted stability remains to be verified.

- Follow-up: exact-SHA Full run
  [40587024590](https://github.com/christiandoxa/modex/actions/runs/40587024590)
  attempt 1 on `216d494` failed `test_auxiliary_rss_does_not_scale_with_non_ascii_input`.
  Tifinagh normalized auxiliary growth was 1,048,576 bytes against 544,768
  allowed. The uploaded `width-rss.json` records all samples; sanitized logs
  and the artifact are preserved locally under `/tmp/modex-ci-failure-40587024590/`.
  Five isolated local runs with the same pinned compiler and driver passed;
  Tifinagh normalized growth ranged from -90,112 to 102,400 bytes. The result
  is under investigation; a later pass does not resolve it.
- Exact-SHA Fast run `40587184826` and Full run `40587202764` passed on
  `5e92613dea9e18b1587b6a1d9cde07b8b052a0b2`, with 421 Python tests in Full.
  Exact-SHA Full run `40588594792` also passed on `d9cd6c9` with 422 Python
  tests. These passes confirm their runs, not the cause of the RSS failure.

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

## Fault events and huge pages

Fast run `40611230270` on `68446d6` and Full run `40610499704` on
`3f82f0d` failed the prior minor-fault control. On a transparent-huge-page
host, a single minor fault can account for much more than one base page.
The revised harness treats faults as events, uses separately required anonymous
RSS and transient VmHWM controls, and measures the allocation control without
calling width. Synthetic cases and replay of all five Fast-run measurements
pass. Hosted Fast run `40619037675` on `863585a` passed the revised check.
Resident page reuse, transient peaks below the prior VmHWM and host noise remain
limits.
