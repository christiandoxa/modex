# Prodex 0.166.2 session inspection and compressed files

The active reference is the checksum-pinned Prodex 0.166.2 Linux x86-64
binary (`e31b8e281583d12b8db1abc5bc9185c4d297d7c40954770ca19dbb8e83567f00`)
from source commit `b1201b5244ff85fce7fc54c3f7607f2e3bdcf4a7`.

`tests/test_session_inspection_01662.py` compares Modex's connected
`session list` and `session current` JSON paths with the release using synthetic
records only. It covers a compressed archived parent, a compressed child with
nested parent metadata, a `.jsonl.zst.json` compound filename whose final
`.json` suffix selects plain JSON parsing, report ordering, and `--parent-only`
filtering. It also checks that compressed and compound-name session IDs feed
`--resume-command` output. The list, list-parent-only, current-parent-only, and
resume-command outputs match. Additional cases verify that compressed filename
queries select the same report through `session list` and `session current`,
and that equal-timestamp reports with duplicate IDs retain ascending path order.
A compact metadata-conflict case also verifies
that non-string ID, thread-name, cwd, provider, and parent values fall through
to the next string fields used by the release. It checks list JSON, `current`
cwd matching, and parent-only filtering. All fixtures are synthetic and run
each binary in the existing isolated session harness.

Verified on 2026-10-31 with:

```sh
python3 scripts/ci/run-unittest.py test_session_inspection_01662.py
```

All six focused tests passed against the pinned release and Modex.

No production change was made: the inspected session list path already matches
these 0.166.2 cases, so a refactor would not close a demonstrated mismatch. This
does not test 0.166.2's native TUI root-resume selection, which remains behind
Modex's guarded Super launch path. It also does not qualify the other five
release targets or establish full session parity.
