# Inspection CLI unknown short-option usage

Verified against the checksum-pinned Prodex 0.166.0 Linux oracle
(`349f6ca8cd437297d2d0c59ca0c1385cd91992de41e65be8e97934a471d09735`). In
`info --json -V --help` and `status --interval=60 -V --help`, Prodex reports
the unknown short option with the command's full `[OPTIONS]` usage. Modex used
only the previously accepted option in usage. Unknown long options still use
the release's narrowed usage and suggestion behavior.

`tests/test_inspection_cli_01660.py` compares both processes in separate
bubblewrap namespaces with empty synthetic homes and workspaces, no network,
and no filesystem changes. The focused active test also covers `current`,
both `info` options, both `status` options, and preserves long-option typo
usage. The six-vector test passed after a Modex build and runs in both active
Fast CI and Full CI lanes.

Separate probes found a remaining status-value precedence gap:
`status --interval bad --unknown --help` and
`status --interval bad -- --interval --help` report the later unknown argument
in Prodex, while Modex reports the invalid interval first. This behavior is
not covered by the fix or claimed as parity.
