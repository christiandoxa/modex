# DeepSeek Super model catalog

> Historical evidence: the active target is Prodex 0.166.1. References to 0.166.0 as active describe the original capture.

Reference: official Prodex 0.166.0 at
`9f69e1835808f478f59f12a3ae3fa88027d896a4`. Its verified Linux x86-64
oracle SHA-256 is
`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`.

## Baseline trace

The pinned source lists `deepseek-v4-pro`, `deepseek-flash`, and the
compatibility ID `deepseek-v4-flash` in
`crates/prodex-provider-core/catalog/models.json`. `auto` and `pro` alias
`deepseek-v4-pro`; `flash` aliases `deepseek-flash`. The same source's
`catalog/retired-models.json` marks `deepseek-chat` and `deepseek-reasoner` as
retired.

The real 0.166.0 Super launch process emits the Codex model catalog. With the
default `deepseek-v4-pro` selection, its rows are
`deepseek-v4-pro`, `auto`, `pro`, `flash`, `deepseek-v4-flash`, and
`deepseek-flash`. The retired IDs are absent, while `deepseek-flash` retains
priority 8, preserving the source order's two retired positions. Known rows
use reasoning efforts `none`, `low`, `high`, and `max`. The `flash` alias
description names the current DeepSeek Flash model, and `deepseek-flash` is
displayed as `DeepSeek V4.1 Flash`.

## Process comparison

`tests/test_deepseek_catalog_01660.py` starts both checksum-verified Prodex
0.166.0 and Modex through the production Super launch path and compares the
complete parsed catalog. It covers known models, retired aliases, an ASCII
case variant, a Kelvin-sign near-match, and custom model IDs containing quotes
or backslashes. Each case uses the synthetic `exit-seven` Codex fixture and
checks that no upstream request or leftover state is produced. Retired IDs
are excluded case-insensitively; the Unicode near-match and escaped custom
IDs remain intact.

## Checks

- `make build` passed with Mojo 1.2.0.
- Under `unshare -Urnm`, with private tmpfs `/tmp`, loopback as the only
  interface, no IPv4 or IPv6 default route, and a sanitized environment,
  `python3 scripts/ci/run-unittest.py test_deepseek_catalog_01660.py` passed
  one production-process differential test in 10.094 seconds. Its launches
  also run inside the test harness's bubblewrap isolation.
- The test is included in the active Python suites in `scripts/ci/run-fast.sh`
  and `scripts/ci/run-full.sh`; `tests/test_ci_oracle_routing.py` asserts both
  routes.

This qualifies the listed Linux x86-64 launch catalog cases only. It does not
qualify provider traffic, all six release targets, or broader Super behavior.
The 0.439.2 catalog assertions remain historical reference checks; the
required 0.439.2 oracle is currently unavailable to fresh CI runners, so its
regression suite remains fail-closed and was not run here.
